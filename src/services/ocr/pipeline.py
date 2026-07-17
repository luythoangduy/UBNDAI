"""Pipeline OCR đầy đủ: file → doc_type → fields → ExtractedDocument. Owner: Dev B.

Bước:
1. Tiền xử lý ảnh (EXIF, làm phẳng/deskew, chính diện/perspective, CLAHE) — ``preprocessing.py``.
2. ``engine.extract`` (chạy trong thread — engine sync theo Protocol).
3. doc_type: hint từ engine (vision LLM tự nhận diện) cross-check với
   ``classifier.classify(raw_text)`` (keyword matching): khớp nhau → tin cậy hơn;
   lệch nhau khi classifier chắc chắn → needs_human_review.
4. Trường/doc_type dưới ngưỡng OCR_CONFIDENCE_THRESHOLD → needs_human_review=True
   (AGENTS §5: confidence thấp bắt buộc needs_human_review, không im lặng điền form).
5. TODO(B) Sprint 1: lưu file qua upload_storage (port từ C2) → file_id thật.
6. TODO(B) Sprint 2: form_filler.autofill(case) + cập nhật ChecklistItem khớp
   accepted_doc_types → status='uploaded'.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from src.config import settings
from src.models import ExtractedDocument, ExtractedField
from src.services.ocr.classifier import classify
from src.services.ocr.engine import OcrResult, VisionLlmEngine, get_engine
from src.services.ocr.preprocessing import preprocess_document_image

_CLASSIFIER_STRONG_CONFIDENCE = 0.8
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}


def _resolve_doc_type(result: OcrResult) -> tuple[str, float, bool]:
    """Cross-check doc_type giữa engine hint và keyword classifier.

    Trả (doc_type, confidence, conflicting). Hai nguồn khớp nhau → lấy confidence
    cao hơn; engine không biết → dùng classifier; lệch nhau khi classifier chắc
    chắn → giữ hint của engine nhưng đánh dấu conflicting để bắt human review.
    """
    cls_type, cls_confidence = classify(result.raw_text)
    engine_type = result.doc_type_hint

    if engine_type == "unknown":
        return cls_type, cls_confidence, False
    if cls_type == "unknown" or cls_type == engine_type:
        return engine_type, max(result.doc_type_confidence, cls_confidence), False
    if cls_confidence >= _CLASSIFIER_STRONG_CONFIDENCE:
        return engine_type, result.doc_type_confidence, True
    return engine_type, result.doc_type_confidence, False


async def process(
    case_id: str,
    filename: str,
    content: bytes,
    field_keys: list[str] | None = None,
) -> ExtractedDocument:
    """Chạy OCR một file ảnh giấy tờ và trả ExtractedDocument (chưa persist).

    ``field_keys``: danh sách trường chuẩn hoá cần trích (vd từ FormField.ocr_sources
    của thủ tục) — hiện chỉ VisionLlmEngine tận dụng được.
    """
    if len(content) > _MAX_UPLOAD_BYTES:
        raise ValueError("File too large; maximum is 10 MB")
    if Path(filename).suffix.casefold() not in _ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported document extension")

    preprocessed = preprocess_document_image(content)
    image_bytes = preprocessed.content if preprocessed.mime_type else content

    engine = get_engine()
    if isinstance(engine, VisionLlmEngine):
        result = await asyncio.to_thread(engine.extract, image_bytes, field_keys)
    else:
        result = await asyncio.to_thread(engine.extract, image_bytes)

    doc_type, doc_type_confidence, conflicting = _resolve_doc_type(result)

    threshold = settings.ocr_confidence_threshold
    fields = [
        ExtractedField(key=f.key, value=f.value, confidence=f.confidence)
        for f in result.fields
    ]
    needs_human_review = (
        conflicting
        or doc_type == "unknown"
        or doc_type_confidence < threshold
        or any(f.confidence < threshold for f in fields)
    )

    return ExtractedDocument(
        id=f"doc_{uuid4().hex}",
        case_id=case_id,
        file_id=f"file_{uuid4().hex}",  # TODO(B) Sprint 1: id thật từ upload_storage
        doc_type=doc_type,
        doc_type_confidence=doc_type_confidence,
        fields=fields,
        raw_text=result.raw_text or None,
        needs_human_review=needs_human_review,
        ocr_engine=result.engine or settings.ocr_engine,
        created_at=datetime.now(UTC),
    )
