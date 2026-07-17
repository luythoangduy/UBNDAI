"""Autofill biểu mẫu từ kết quả OCR. Owner: Dev B.

Generic theo khai báo — KHÔNG hardcode theo thủ tục:
với mỗi FormField của thủ tục, tìm giá trị đầu tiên trong ocr_sources
khớp ExtractedDocument.field_map() của case; ghi vào Case.form_data.
Không ghi đè trường người dân đã sửa tay (edited_by_user).
"""

from src.models import Case, ExtractedDocument, Procedure


def autofill(case: Case, procedure: Procedure, documents: list[ExtractedDocument]) -> dict:
    """Trả form_data mới (chưa persist — caller cập nhật Case)."""
    raise NotImplementedError  # TODO(B) Sprint 2
