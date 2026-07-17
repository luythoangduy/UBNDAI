"""Cập nhật ChecklistItem sau khi OCR xong một giấy tờ. Owner: Dev B.

Generic theo catalog: giấy tờ có ``doc_type`` nằm trong ``accepted_doc_types``
của requirement nào thì item tương ứng chuyển trạng thái. Không hardcode thủ tục.
"""

from __future__ import annotations

from src.models import Case, ChecklistItem, ExtractedDocument, Procedure


def apply_document_to_checklist(
    case: Case, procedure: Procedure, document: ExtractedDocument
) -> list[ChecklistItem]:
    """Trả checklist mới (không mutate Case — caller persist).

    - doc_type khớp ``accepted_doc_types`` → item thành ``uploaded`` (hoặc
      ``uncertain`` nếu OCR đánh dấu needs_human_review) + gắn document_id.
    - Item đã ``verified`` giữ nguyên (rule engine đã xác nhận, OCR lại không hạ cấp).
    """
    accepted_by_code = {
        req.code: set(req.accepted_doc_types) for req in procedure.requirements
    }
    new_status = "uncertain" if document.needs_human_review else "uploaded"

    updated: list[ChecklistItem] = []
    for item in case.checklist:
        accepted = accepted_by_code.get(item.requirement_code, set())
        if document.doc_type in accepted and item.status != "verified":
            updated.append(
                item.model_copy(
                    update={"status": new_status, "document_id": document.id}
                )
            )
        else:
            updated.append(item.model_copy())
    return updated
