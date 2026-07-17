"""OCR engine adapters. Owner: Dev B. Chọn engine qua env OCR_ENGINE.

Ba adapter:
- ``VisionLlmEngine`` — vision LLM, mạnh nhất với chữ VIẾT TAY tiếng Việt; trả luôn
  fields + confidence + doc_type hint. Provider ``anthropic`` dùng official SDK với
  structured outputs (JSON schema được API đảm bảo); ``gemini`` dùng REST qua httpx.
- ``PaddleOcrEngine`` — local, chữ in (TODO Sprint 1).
- ``GoogleVisionEngine`` — cloud, production (TODO Sprint 3).

Lưu ý model Claude 4.7+ / Sonnet 5 / Opus 4.8: KHÔNG gửi temperature/top_p/top_k
(API trả 400 với giá trị khác mặc định) — steer bằng prompt.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

import anthropic
import httpx

from src.agents.prompts.ocr import (
    VISION_OCR_DEFAULT_TASK,
    VISION_OCR_SYSTEM_PROMPT,
    build_field_instruction,
)
from src.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Structured output schema cho OCR — API đảm bảo JSON hợp lệ theo schema này.
# Không dùng numerical constraints (min/max) — không được hỗ trợ; clamp phía client.
OCR_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "raw_text": {"type": "string"},
        "doc_type": {
            "type": "string",
            "enum": [
                "cccd",
                "giay_chung_sinh",
                "giay_dang_ky_ket_hon",
                "giay_xac_nhan_cu_tru",
                "don_viet_tay",
                "unknown",
            ],
        },
        "doc_type_confidence": {"type": "number"},
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "confidence": {"type": "number"},
                    "note": {"type": "string"},
                },
                "required": ["key", "value", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["raw_text", "doc_type", "doc_type_confidence", "fields"],
    "additionalProperties": False,
}


class OcrEngineError(Exception):
    """OCR engine failed to produce a usable result."""


@dataclass(frozen=True)
class OcrField:
    key: str
    value: str
    confidence: float  # 0.0–1.0, contract của ExtractedField
    note: str = ""


@dataclass(frozen=True)
class OcrResult:
    """Raw OCR output, engine-agnostic. Pipeline maps this onto ExtractedDocument."""

    raw_text: str
    fields: list[OcrField] = field(default_factory=list)
    doc_type_hint: str = "unknown"
    doc_type_confidence: float = 0.0
    engine: str = ""


class OcrEngine(Protocol):
    def extract(self, image_bytes: bytes) -> OcrResult: ...


def _clamp_confidence(value: object) -> float:
    try:
        return min(1.0, max(0.0, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _parse_json_object(raw_text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.IGNORECASE)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise OcrEngineError("Vision LLM did not return a JSON object")
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise OcrEngineError("Vision LLM returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise OcrEngineError("Vision LLM returned a non-object JSON value")
    return parsed


class VisionLlmEngine:
    """OCR qua vision LLM. Sync (pipeline gọi qua ``asyncio.to_thread``).

    ``field_keys`` cho phép caller yêu cầu đúng các trường chuẩn hoá cần trích
    (vd lấy từ ``FormField.ocr_sources`` của thủ tục).
    """

    name = "vision_llm"

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: httpx.Client | None = None,
        anthropic_client: anthropic.Anthropic | None = None,
        timeout_s: float = 60.0,
    ) -> None:
        # Dùng bộ setting OCR_LLM_* — TÁCH RIÊNG với LLM chatbot (LLM_*).
        self._provider = (provider or settings.ocr_llm_provider).strip().lower()
        self._api_key = api_key if api_key is not None else settings.ocr_llm_api_key
        self._model = model or settings.ocr_llm_model
        self._client = client
        self._anthropic_client = anthropic_client
        self._timeout_s = timeout_s

    def _extract_anthropic_text(self, task: str, image_b64: str) -> str:
        client = self._anthropic_client or anthropic.Anthropic(
            api_key=self._api_key, timeout=self._timeout_s
        )
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=16000,
                system=VISION_OCR_SYSTEM_PROMPT,
                output_config={"format": {"type": "json_schema", "schema": OCR_OUTPUT_SCHEMA}},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": task},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_b64,
                                },
                            },
                        ],
                    }
                ],
            )
        except anthropic.APIStatusError as exc:
            logger.exception("Anthropic OCR request failed: %s %s", exc.status_code, exc.message)
            raise OcrEngineError("Vision LLM request failed") from exc
        except anthropic.APIConnectionError as exc:
            logger.exception("Anthropic OCR connection failed")
            raise OcrEngineError("Vision LLM request failed") from exc

        if response.stop_reason == "refusal":
            raise OcrEngineError("Vision LLM declined the request (refusal)")
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text:
            raise OcrEngineError("Unexpected Vision LLM response shape")
        return text

    def _extract_gemini_text(self, task: str, image_b64: str) -> str:
        payload = {
            "system_instruction": {"parts": [{"text": VISION_OCR_SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": task},
                        {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    ],
                }
            ],
            "generationConfig": {"temperature": 0.0, "response_mime_type": "application/json"},
        }
        url = f"{GEMINI_API_BASE}/models/{self._model}:generateContent"

        client = self._client or httpx.Client(timeout=self._timeout_s)
        try:
            response = client.post(url, params={"key": self._api_key}, json=payload)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPError as exc:
            logger.exception("Gemini OCR request failed")
            raise OcrEngineError("Vision LLM request failed") from exc
        finally:
            if self._client is None:
                client.close()

        try:
            return body["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OcrEngineError("Unexpected Vision LLM response shape") from exc

    def extract(self, image_bytes: bytes, field_keys: list[str] | None = None) -> OcrResult:
        if not image_bytes:
            raise OcrEngineError("Empty image")
        if not self._api_key:
            raise OcrEngineError("OCR_LLM_API_KEY is not configured for vision_llm OCR")
        if self._provider not in ("anthropic", "gemini"):
            raise OcrEngineError(
                f"Unsupported OCR_LLM_PROVIDER '{self._provider}'. Supported: anthropic, gemini"
            )

        task = build_field_instruction(field_keys) if field_keys else VISION_OCR_DEFAULT_TASK
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        if self._provider == "anthropic":
            text = self._extract_anthropic_text(task, image_b64)
        else:
            text = self._extract_gemini_text(task, image_b64)

        parsed = _parse_json_object(text)
        fields = [
            OcrField(
                key=str(item.get("key", "")).strip(),
                value=str(item.get("value") or ""),
                confidence=_clamp_confidence(item.get("confidence")),
                note=str(item.get("note") or ""),
            )
            for item in (parsed.get("fields") or [])
            if isinstance(item, dict) and str(item.get("key", "")).strip()
        ]
        return OcrResult(
            raw_text=str(parsed.get("raw_text") or ""),
            fields=fields,
            doc_type_hint=str(parsed.get("doc_type") or "unknown"),
            doc_type_confidence=_clamp_confidence(parsed.get("doc_type_confidence")),
            engine=self.name,
        )


class PaddleOcrEngine:
    """Local, mặc định cho dev/demo. Cần paddleocr trong extras [ocr-local]."""

    name = "paddleocr"

    def extract(self, image_bytes: bytes) -> OcrResult:
        raise NotImplementedError  # TODO(B) Sprint 1


class GoogleVisionEngine:
    """Cloud, production. Cần GOOGLE_APPLICATION_CREDENTIALS."""

    name = "google_vision"

    def extract(self, image_bytes: bytes) -> OcrResult:
        raise NotImplementedError  # TODO(B) Sprint 3


_ENGINES: dict[str, type] = {
    "vision_llm": VisionLlmEngine,
    "paddleocr": PaddleOcrEngine,
    "google_vision": GoogleVisionEngine,
}


def get_engine(name: str | None = None) -> OcrEngine:
    """Factory theo ``settings.ocr_engine`` (hoặc override qua ``name``)."""
    engine_name = (name or settings.ocr_engine).strip().lower()
    engine_cls = _ENGINES.get(engine_name)
    if engine_cls is None:
        raise OcrEngineError(
            f"Unknown OCR engine '{engine_name}'. Supported: {sorted(_ENGINES)}"
        )
    return engine_cls()
