"""Cập nhật ChecklistItem sau khi OCR xong một giấy tờ. Owner: Dev B.

Generic theo catalog: giấy tờ có ``doc_type`` nằm trong ``accepted_doc_types``
của requirement nào thì item tương ứng chuyển trạng thái. Không hardcode thủ tục.
"""

from __future__ import annotations

from src.models import Case, ChecklistItem, ExtractedDocument, Procedure


def status_after_document(doc_type: str, needs_human_review: bool) -> str:
    return "uncertain" if needs_human_review else "uploaded"


def codes_satisfied_by(procedure: Procedure, doc_type: str) -> set[str]:
    """Các requirement code mà một giấy tờ ``doc_type`` này đáp ứng."""
    return {
        req.code for req in procedure.requirements if doc_type in req.accepted_doc_types
    }


def apply_document_to_checklist(
    case: Case, procedure: Procedure, document: ExtractedDocument
) -> list[ChecklistItem]:
    """Trả checklist mới (không mutate Case — caller persist).

    - doc_type khớp ``accepted_doc_types`` → item thành ``uploaded`` (hoặc
      ``uncertain`` nếu OCR đánh dấu needs_human_review) + gắn document_id.
    - Item đã ``verified`` giữ nguyên (rule engine đã xác nhận, OCR lại không hạ cấp).
    """
    satisfied = codes_satisfied_by(procedure, document.doc_type)
    new_status = status_after_document(document.doc_type, document.needs_human_review)

    updated: list[ChecklistItem] = []
    for item in case.checklist:
        if item.requirement_code in satisfied and item.status != "verified":
            updated.append(
                item.model_copy(
                    update={"status": new_status, "document_id": document.id}
                )
            )
        else:
            updated.append(item.model_copy())
    return updated


def apply_document_to_checklist_map(
    checklist: dict[str, str], procedure: Procedure, doc_type: str, needs_human_review: bool
) -> dict[str, str]:
    """Bản dict-shaped của ``apply_document_to_checklist`` cho ApplicationCase.checklist."""
    satisfied = codes_satisfied_by(procedure, doc_type)
    new_status = status_after_document(doc_type, needs_human_review)
    return {
        code: (
            new_status
            if code in satisfied and status not in {"verified", "not_applicable"}
            else status
        )
        for code, status in checklist.items()
    } | {
        code: new_status
        for code in satisfied
        if code not in checklist
    }
