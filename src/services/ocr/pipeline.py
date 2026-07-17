"""Pipeline OCR đầy đủ: file → doc_type → fields → ExtractedDocument. Owner: Dev B.

Bước:
1. Lưu file (dùng upload_storage port từ C2).
2. classifier.classify(image) → (doc_type, confidence).
3. Trích trường theo template của doc_type (templates/*.yaml — vị trí + regex + chuẩn hoá).
4. Trường/doc_type dưới ngưỡng OCR_CONFIDENCE_THRESHOLD → needs_human_review=True.
5. form_filler.autofill(case) — map field vào Case.form_data qua FormField.ocr_sources.
6. Cập nhật ChecklistItem khớp accepted_doc_types → status='uploaded'.
"""

from datetime import datetime, timezone
from uuid import uuid4

from src.config import settings
from src.models import ExtractedDocument, ExtractedField
from src.services.ocr.classifier import classify
from src.services.ocr.engine import get_engine


async def process(case_id: str, filename: str, content: bytes) -> ExtractedDocument:
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("File too large; maximum is 10 MB")
    allowed = {".jpg", ".jpeg", ".png", ".pdf"}
    if not any(filename.casefold().endswith(ext) for ext in allowed):
        raise ValueError("Unsupported document extension")
    result = get_engine().extract(content)
    doc_type, type_confidence = classify(result.raw_text)
    return ExtractedDocument(id=str(uuid4()), case_id=case_id, file_id=str(uuid4()), doc_type=doc_type, doc_type_confidence=type_confidence, fields=[ExtractedField(key="raw_text", value=result.raw_text, confidence=result.confidence)], raw_text=result.raw_text, needs_human_review=type_confidence < settings.ocr_confidence_threshold or result.confidence < settings.ocr_confidence_threshold, ocr_engine=settings.ocr_engine, created_at=datetime.now(timezone.utc))
