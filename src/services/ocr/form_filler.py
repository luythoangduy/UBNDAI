"""Autofill biểu mẫu từ kết quả OCR. Owner: Dev B.

Generic theo khai báo — KHÔNG hardcode theo thủ tục:
với mỗi FormField của thủ tục, tìm giá trị đầu tiên trong ocr_sources
khớp ExtractedDocument.field_map() của case; ghi vào Case.form_data.
Không ghi đè trường người dân đã sửa tay (edited_by_user).

Quy tắc confidence (AGENTS §5): trường OCR dưới ngưỡng OCR_CONFIDENCE_THRESHOLD
không được im lặng điền vào form — bỏ qua, trừ khi người dân đã sửa tay giá trị
đó (edited_by_user=True → coi như đã xác nhận).
"""

from __future__ import annotations

from src.config import settings
from src.models import Case, ExtractedDocument, Procedure


def _usable_field_map(documents: list[ExtractedDocument]) -> dict[str, str]:
    """Gộp field_map của các giấy tờ, chỉ giữ trường đủ tin cậy hoặc đã sửa tay.

    Giấy tờ upload sau ghi đè giấy tờ trước (cùng key) — bản mới nhất thắng.
    """
    threshold = settings.ocr_confidence_threshold
    merged: dict[str, str] = {}
    for doc in sorted(documents, key=lambda d: d.created_at):
        for extracted in doc.fields:
            if not extracted.value.strip():
                continue
            if extracted.confidence < threshold and not extracted.edited_by_user:
                continue
            merged[f"{doc.doc_type}.{extracted.key}"] = extracted.value
    return merged


def autofill(case: Case, procedure: Procedure, documents: list[ExtractedDocument]) -> dict:
    """Trả form_data mới (chưa persist — caller cập nhật Case).

    Giá trị đã có trong ``case.form_data`` (người dân nhập/sửa trên form) được
    giữ nguyên — autofill chỉ điền vào chỗ trống.
    """
    ocr_values = _usable_field_map(documents)
    form_data: dict = dict(case.form_data)

    for template in procedure.form_templates:
        for form_field in template.fields:
            existing = form_data.get(form_field.key)
            if existing is not None and str(existing).strip():
                continue
            for source in form_field.ocr_sources:
                value = ocr_values.get(source)
                if value:
                    form_data[form_field.key] = value
                    break

    return form_data
