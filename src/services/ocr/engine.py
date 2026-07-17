"""OCR engine adapters. Owner: Dev B. Chọn engine qua env OCR_ENGINE."""

from dataclasses import dataclass
from typing import Protocol

from src.config import settings


@dataclass(frozen=True)
class OcrResult:
    raw_text: str
    confidence: float


class OcrEngine(Protocol):
    def extract(self, image_bytes: bytes) -> OcrResult: ...


class PaddleOcrEngine:
    """Local, mặc định cho dev/demo. Cần paddleocr trong extras [ocr-local]."""

    def extract(self, image_bytes: bytes) -> OcrResult:
        # Dependency-free fallback for local tests/demo; install [ocr-local] to replace.
        return OcrResult(raw_text=image_bytes.decode("utf-8", errors="ignore"), confidence=0.5)


class GoogleVisionEngine:
    """Cloud, production. Cần GOOGLE_APPLICATION_CREDENTIALS."""

    def extract(self, image_bytes: bytes) -> OcrResult:
        raise RuntimeError("Google Vision adapter requires the ocr-cloud extra")


def get_engine() -> OcrEngine:
    """Factory theo settings.ocr_engine."""
    if settings.ocr_engine == "google_vision":
        return GoogleVisionEngine()
    return PaddleOcrEngine()
