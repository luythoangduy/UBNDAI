"""Pipeline OCR đầy đủ: file → doc_type → fields → ExtractedDocument. Owner: Dev B.

Bước:
1. Lưu file (dùng upload_storage port từ C2).
2. classifier.classify(image) → (doc_type, confidence).
3. Trích trường theo template của doc_type (templates/*.yaml — vị trí + regex + chuẩn hoá).
4. Trường/doc_type dưới ngưỡng OCR_CONFIDENCE_THRESHOLD → needs_human_review=True.
5. form_filler.autofill(case) — map field vào Case.form_data qua FormField.ocr_sources.
6. Cập nhật ChecklistItem khớp accepted_doc_types → status='uploaded'.
"""

from src.models import ExtractedDocument


async def process(case_id: str, filename: str, content: bytes) -> ExtractedDocument:
    raise NotImplementedError  # TODO(B) Sprint 1
