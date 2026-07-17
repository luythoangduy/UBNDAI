"""Pipeline OCR đầy đủ: file → doc_type → fields → ExtractedDocument. Owner: Dev B.

Bước:
1. Tiền xử lý ảnh (EXIF, làm phẳng/deskew, chính diện/perspective, CLAHE) — ``preprocessing.py``.
2. ``engine.extract`` (chạy trong thread — engine sync theo Protocol).
3. doc_type: dùng hint từ engine (vision LLM tự nhận diện); TODO(B) đối chiếu
   ``classifier.classify(raw_text)`` khi PaddleOCR vào — keyword matching làm cross-check.
4. Trường/doc_type dưới ngưỡng OCR_CONFIDENCE_THRESHOLD → needs_human_review=True
   (AGENTS §5: confidence thấp bắt buộc needs_human_review, không im lặng điền form).
5. TODO(B) Sprint 1: lưu file qua upload_storage (port từ C2) → file_id thật.
6. TODO(B) Sprint 2: form_filler.autofill(case) + cập nhật ChecklistItem khớp
   accepted_doc_types → status='uploaded'.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from src.config import settings
from src.models import ExtractedDocument, ExtractedField
from src.services.ocr.engine import VisionLlmEngine, get_engine
from src.services.ocr.preprocessing import preprocess_document_image


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
    preprocessed = preprocess_document_image(content)
    image_bytes = preprocessed.content if preprocessed.mime_type else content

    engine = get_engine()
    if isinstance(engine, VisionLlmEngine):
        result = await asyncio.to_thread(engine.extract, image_bytes, field_keys)
    else:
        result = await asyncio.to_thread(engine.extract, image_bytes)

    threshold = settings.ocr_confidence_threshold
    fields = [
        ExtractedField(key=f.key, value=f.value, confidence=f.confidence)
        for f in result.fields
    ]
    needs_human_review = (
        result.doc_type_hint == "unknown"
        or result.doc_type_confidence < threshold
        or any(f.confidence < threshold for f in fields)
    )

    return ExtractedDocument(
        id=f"doc_{uuid4().hex}",
        case_id=case_id,
        file_id=f"file_{uuid4().hex}",  # TODO(B) Sprint 1: id thật từ upload_storage
        doc_type=result.doc_type_hint,
        doc_type_confidence=result.doc_type_confidence,
        fields=fields,
        raw_text=result.raw_text or None,
        needs_human_review=needs_human_review,
        ocr_engine=result.engine or settings.ocr_engine,
        created_at=datetime.now(UTC),
    )
