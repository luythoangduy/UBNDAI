"""Clarify node — sinh câu hỏi làm rõ từ catalog (không LLM, không bịa câu hỏi)."""

from __future__ import annotations

from typing import Any

from src.agents.state import GuidanceState
from src.services import catalog
from src.services.clarification import unresolved_questions
from src.services.retrieval import citations_from_chunks, retrieve


async def run(state: GuidanceState) -> dict[str, Any]:
    procedure = catalog.get_procedure(state.get("selected_procedure_id"))
    if state.get("pending_action") == "confirm_switch_procedure":
        return {
            "reply": (
                "Case hiện đã có tài liệu được tải lên. Đổi thủ tục sẽ xoá answers và "
                "checklist hiện tại. Bạn có chắc muốn đổi không?"
            ),
            "reply_kind": "clarify",
            "pending_questions": ["Bạn có chắc muốn đổi thủ tục không?"],
            "pending_action": "confirm_switch_procedure",
            "pending_procedure_ids": [],
            "pending_question_keys": [],
            "pending_switch_query": state.get("pending_switch_query"),
            "citations": [],
        }
    if procedure is None:
        candidate_ids = state.get("pending_procedure_ids") or []
        if state.get("pending_action") == "select_procedure" and candidate_ids:
            lines = ["Bạn chọn giúp mình một thủ tục trong danh sách sau:"]
            for index, procedure_id in enumerate(candidate_ids, start=1):
                candidate = catalog.get_procedure(procedure_id)
                if candidate:
                    lines.append(f"{index}. {candidate.name} — {candidate.agency}")
            lines.append("Bạn có thể trả lời bằng số thứ tự hoặc tên thủ tục.")
            return {
                "reply": "\n".join(lines),
                "reply_kind": "clarify",
                "pending_questions": ["Bạn chọn thủ tục số mấy?"],
                "pending_action": "select_procedure",
                "pending_procedure_ids": candidate_ids,
                "pending_question_keys": [],
                "citations": [],
            }
        return {
            "reply": (
                "Bạn mô tả giúp mình nhu cầu hành chính cụ thể và điều bạn muốn biết "
                "để mình tìm đúng thủ tục và nguồn nhé."
            ),
            "reply_kind": "clarify",
            "pending_questions": ["Bạn đang cần làm thủ tục hành chính nào?"],
            "pending_action": None,
            "pending_procedure_ids": [],
            "pending_question_keys": [],
            "citations": [],
        }

    answers = state.get("answers") or {}
    unanswered = unresolved_questions(procedure, answers)
    proc_chunks = [
        c for c in retrieve(procedure.name) if c.procedure_id == procedure.id
    ]
    citations = [c.model_dump() for c in citations_from_chunks(proc_chunks)]

    if not unanswered:
        return {
            "reply": (
                f"Mình đã đủ thông tin cho thủ tục {procedure.name}. "
                "Bạn hỏi 'cần chuẩn bị giấy tờ gì' để xem checklist nhé."
            ),
            "reply_kind": "clarify",
            "pending_questions": [],
            "pending_action": None,
            "pending_procedure_ids": [],
            "pending_question_keys": [],
            "citations": citations,
        }

    questions = [question.text for question in unanswered]
    return {
        "reply": (
            f"Để lên checklist đúng trường hợp của bạn cho thủ tục {procedure.name}, "
            "mình cần làm rõ thêm:"
        ),
        "reply_kind": "clarify",
        "pending_questions": questions,
        "pending_action": "answer_clarification",
        "pending_procedure_ids": [],
        "pending_question_keys": [question.key for question in unanswered],
        "citations": citations,
    }
