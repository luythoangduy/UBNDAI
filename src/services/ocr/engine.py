"""OCR engine adapters. Owner: Dev B. Chọn engine qua env OCR_ENGINE."""

from typing import Protocol


class OcrResult:
    """Raw OCR: text + boxes + confidence. TODO(B): định nghĩa dataclass cụ thể."""


class OcrEngine(Protocol):
    def extract(self, image_bytes: bytes) -> OcrResult: ...


class PaddleOcrEngine:
    """Local, mặc định cho dev/demo. Cần paddleocr trong extras [ocr-local]."""

    def extract(self, image_bytes: bytes) -> OcrResult:
        raise NotImplementedError  # TODO(B) Sprint 1


class GoogleVisionEngine:
    """Cloud, production. Cần GOOGLE_APPLICATION_CREDENTIALS."""

    def extract(self, image_bytes: bytes) -> OcrResult:
        raise NotImplementedError  # TODO(B) Sprint 3


def get_engine() -> OcrEngine:
    """Factory theo settings.ocr_engine."""
    raise NotImplementedError  # TODO(B)
