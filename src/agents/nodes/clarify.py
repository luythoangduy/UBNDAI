"""Clarify node — sinh câu hỏi làm rõ từ catalog (không LLM, không bịa câu hỏi)."""

from __future__ import annotations

from typing import Any

from src.agents.state import GuidanceState
from src.services import catalog
from src.services.clarification import unresolved_questions
from src.services.retrieval import citations_from_chunks, retrieve


async def run(state: GuidanceState) -> dict[str, Any]:
    procedure = catalog.get_procedure(state.get("selected_procedure_id"))
    if procedure is None:
        return {
            "reply": (
                "Bạn mô tả giúp mình nhu cầu cụ thể (ví dụ: đăng ký khai sinh cho con, "
                "làm lại CCCD...) để mình xác định đúng thủ tục nhé."
            ),
            "reply_kind": "clarify",
            "pending_questions": ["Bạn đang cần làm thủ tục hành chính nào?"],
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
        "citations": citations,
    }
