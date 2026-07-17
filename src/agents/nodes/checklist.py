"""Checklist node — áp answers vào DocumentRequirement (deterministic, AGENTS.md §6).

Mọi item trace về DocumentRequirement.code trong catalog; citation về thủ tục.
"""

from __future__ import annotations

from typing import Any

from src.agents.state import GuidanceState
from src.services import catalog, checklist as checklist_service
from src.services.clarification import unresolved_questions
from src.services.retrieval.chunking import chunks_from_procedure
from src.services.retrieval.common import citations_from_chunks


async def run(state: GuidanceState) -> dict[str, Any]:
    procedure = catalog.get_procedure(state.get("selected_procedure_id"))
    if procedure is None:
        return {
            "reply": (
                "Mình chưa xác định được bạn cần thủ tục nào. Bạn mô tả nhu cầu "
                "cụ thể để mình nhận diện thủ tục trước khi lên checklist nhé."
            ),
            "reply_kind": "clarify",
            "pending_questions": ["Bạn đang cần làm thủ tục hành chính nào?"],
            "citations": [],
        }

    answers = state.get("answers") or {}
    items = checklist_service.build_checklist(procedure, answers)
    unanswered = unresolved_questions(procedure, answers)

    lines = [f"Checklist hồ sơ cho thủ tục {procedure.name}:"]
    order = 0
    for item in items:
        requirement = checklist_service.requirement_by_code(
            procedure, item.requirement_code
        )
        name = requirement.name if requirement else item.requirement_code
        if item.status == "not_applicable":
            continue
        order += 1
        line = f"{order}. {name}"
        if requirement and requirement.original_required:
            line += " (bản chính)"
        if requirement and requirement.copies:
            line += f" + {requirement.copies} bản sao"
        if item.note:
            line += f" — {item.note}"
        lines.append(line)

    skipped = [i for i in items if i.status == "not_applicable"]
    if skipped:
        names = []
        for item in skipped:
            requirement = checklist_service.requirement_by_code(
                procedure, item.requirement_code
            )
            names.append(requirement.name if requirement else item.requirement_code)
        lines.append(f"Không áp dụng cho trường hợp của bạn: {'; '.join(names)}.")

    pending_questions: list[str] = []
    if unanswered:
        lines.append(
            "Một số mục còn tuỳ trường hợp — bạn trả lời thêm để checklist chính xác hơn:"
        )
        pending_questions = [question.text for question in unanswered]

    citations = citations_from_chunks(chunks_from_procedure(procedure))
    return {
        "checklist": [item.model_dump() for item in items],
        "pending_questions": pending_questions,
        "reply": "\n".join(lines),
        "reply_kind": "checklist",
        "citations": [c.model_dump() for c in citations],
    }
