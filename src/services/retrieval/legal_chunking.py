"""Chuẩn hóa/chunk văn bản luật tải từ Hugging Face cho Chroma và BM25."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from src.services.retrieval.common import RetrievedChunk

DATASET_URL = "https://huggingface.co/datasets/YuITC/Vietnamese-Legal-Documents"
SOURCE_TYPE = "huggingface_dataset"


def chunks_from_legal_record(
    record_id: str | int,
    text: str,
    *,
    dataset_id: str = "YuITC/Vietnamese-Legal-Documents",
    dataset_revision: str = "main",
    max_chars: int = 1400,
    overlap_chars: int = 180,
) -> list[RetrievedChunk]:
    """Cắt văn bản theo ranh giới Điều/Khoản gần nhất và gắn provenance đầy đủ."""
    normalized = _normalize(text)
    if not normalized:
        return []
    record_key = str(record_id)
    source_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    parts = list(_split_text(normalized, max_chars=max_chars, overlap_chars=overlap_chars))
    return [
        RetrievedChunk(
            content=part,
            metadata={
                "chunk_id": f"legal::{record_key}::{index}",
                # Giữ tương thích Citation hiện hữu; đây không phải procedure_id nghiệp vụ.
                "procedure_id": f"legal:{record_key}",
                "procedure_name": f"Văn bản pháp luật #{record_key}",
                "section": "van_ban_phap_luat",
                "source_type": SOURCE_TYPE,
                "dataset_id": dataset_id,
                "dataset_revision": dataset_revision,
                "legal_record_id": record_key,
                "source_hash": source_hash,
                "source_url": DATASET_URL,
            },
        )
        for index, part in enumerate(parts)
    ]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _split_text(
    text: str, *, max_chars: int, overlap_chars: int
) -> Iterable[str]:
    if len(text) <= max_chars:
        yield text
        return
    boundaries = [match.start() for match in re.finditer(r"\b(?:Điều|Khoản)\s+\d+", text)]
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            candidates = [point for point in boundaries if start + max_chars // 2 <= point <= end]
            if candidates:
                end = candidates[-1]
            else:
                sentence = text.rfind(". ", start + max_chars // 2, end)
                if sentence > start:
                    end = sentence + 1
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)
