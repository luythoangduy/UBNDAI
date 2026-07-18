"""Embedding providers cho dense retrieval. Port rút gọn từ C2-App-108. Owner: Dev A.

Provider phải khớp giữa lúc index (scripts/index_procedures.py) và lúc query —
tên provider/model được ghi vào metadata của collection để đối chiếu.
'fake' là hash deterministic, chỉ dùng dev/test (không có ý nghĩa ngữ nghĩa).
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import Any

from huggingface_hub import InferenceClient

from src.config import settings
from src.services.retrieval.common import tokenize

_LOCAL_MODEL_CACHE: dict[str, Any] = {}
_FAKE_DIMENSION = 32


def has_real_api_key(value: str | None) -> bool:
    normalized = (value or "").strip().casefold()
    if not normalized or "your-key" in normalized or "your_" in normalized:
        return False
    return normalized not in {
        "changeme", "change-me", "dummy", "fake", "placeholder", "test", "test-key",
    }


def google_api_key() -> str:
    """Key riêng cho embedding Google — KHÔNG dùng llm_api_key (đó là key Anthropic)."""
    return os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")


def huggingface_api_token() -> str:
    return os.environ.get("HF_TOKEN", "") or os.environ.get(
        "HUGGINGFACE_API_TOKEN", ""
    )


class FakeEmbeddingModel:
    """Hash deterministic — dev/test only, để pipeline chạy không cần model thật."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.casefold().encode("utf-8")).digest()
        values = [
            int.from_bytes(digest[i : i + 2], "big") / 65535.0 - 0.5
            for i in range(0, _FAKE_DIMENSION * 2, 2)
        ]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


class HashingEmbeddingModel:
    """Embedding lexical offline, deterministic cho corpus lớn khi chưa có model thật.

    Đây không phải embedding semantic. Nó dùng feature hashing trên token để Chroma
    có thể vận hành không cần tải model/khóa API; BM25 vẫn là tín hiệu chính trong
    chế độ này. Collection luôn ghi rõ provider ``hashing`` để không bị nhầm với
    vector semantic khi triển khai production.
    """

    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        values = [0.0] * self.dimension
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            raw = int.from_bytes(digest, "big")
            index = raw % self.dimension
            sign = 1.0 if raw & 1 else -1.0
            values[index] += sign
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


class BgeM3EmbeddingModel:
    """Wrapper sentence-transformers cho BGE-M3 local (pattern từ C2)."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        encoded = self._model().encode(
            texts, normalize_embeddings=True, convert_to_numpy=True
        )
        return encoded.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def _model(self) -> Any:
        if self.model_name not in _LOCAL_MODEL_CACHE:
            if settings.local_embedding_offline:
                # Bảo đảm model đã cache không phát sinh HTTP request khi chạy index/chat.
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "BGE-M3 cần sentence-transformers: pip install sentence-transformers"
                ) from exc
            _LOCAL_MODEL_CACHE[self.model_name] = SentenceTransformer(
                self.model_name, local_files_only=settings.local_embedding_offline
            )
        return _LOCAL_MODEL_CACHE[self.model_name]


class HuggingFaceInferenceEmbeddingModel:
    """Remote feature-extraction adapter for BGE-M3 via HF Inference Providers."""

    def __init__(self, model_name: str) -> None:
        token = huggingface_api_token()
        if not has_real_api_key(token):
            raise RuntimeError(
                "Cần HF_TOKEN/HUGGINGFACE_API_TOKEN hợp lệ cho Hugging Face embedding."
            )
        self.model_name = model_name
        self.client = InferenceClient(
            provider=settings.huggingface_inference_provider,
            api_key=token,
            timeout=settings.huggingface_inference_timeout_s,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        encoded = self.client.feature_extraction(
            texts,
            model=self.model_name,
            normalize=True,
            truncate=True,
        )
        values = encoded.tolist() if hasattr(encoded, "tolist") else encoded
        return [[float(value) for value in row] for row in values]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def resolve_embedding_provider(provider: str | None = None) -> str:
    chosen = (provider or settings.embedding_provider or "auto").strip()
    if chosen != "auto":
        return chosen
    if has_real_api_key(google_api_key()):
        return "google"
    return "bge-m3"


def get_embedding_model(provider: str | None = None) -> Any:
    resolved = resolve_embedding_provider(provider)
    if resolved == "fake":
        return FakeEmbeddingModel()
    if resolved == "hashing":
        return HashingEmbeddingModel(settings.hash_embedding_dimension)
    if resolved == "bge-m3":
        return BgeM3EmbeddingModel(settings.local_embedding_model_name)
    if resolved in {"huggingface", "hf-inference"}:
        return HuggingFaceInferenceEmbeddingModel(
            settings.huggingface_embedding_model_name
        )
    if resolved == "google":
        key = google_api_key()
        if not has_real_api_key(key):
            raise RuntimeError("Cần GOOGLE_API_KEY/GEMINI_API_KEY hợp lệ cho embedding Google.")
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
        except ImportError as exc:
            raise RuntimeError(
                "Cần langchain-google-genai cho embedding Google: pip install langchain-google-genai"
            ) from exc
        return GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001", google_api_key=key
        )
    raise RuntimeError(f"Embedding provider không hỗ trợ: {resolved}")
