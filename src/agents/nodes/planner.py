"""Planner node — 1 LLM call structured (route + rewrite + extract answers).

LLM-first, rule-based fallback khi LLM lỗi/thiếu key (AGENTS.md §6).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.agents.prompts import PLANNER_SYSTEM, planner_context
from src.agents.state import GuidanceState
from src.services import catalog
from src.services.clarification import extract_answers, unresolved_questions
from src.services.llm import get_llm, llm_is_configured
from src.services.retrieval.common import fold_ascii

logger = logging.getLogger(__name__)

_CHECKLIST_KEYWORDS = [
    "giay to gi", "can giay to", "ho so gom", "thanh phan ho so",
    "chuan bi gi", "can chuan bi", "checklist", "danh sach giay to",
]


class ExtractedAnswer(BaseModel):
    key: str
    value: str = Field(description='"true"/"false" hoặc giá trị nguyên văn')


class PlannerDecision(BaseModel):
    route: Literal["clarify", "identify", "checklist", "answer"]
    rewritten_query: str = ""
    extracted_answers: list[ExtractedAnswer] = Field(default_factory=list)


async def run(state: GuidanceState) -> dict[str, Any]:
    message = _last_human_text(state)
    procedure = catalog.get_procedure(state.get("selected_procedure_id"))
    answers = dict(state.get("answers") or {})

    if procedure is None and state.get("pending_action") == "select_procedure":
        candidate_ids = state.get("pending_procedure_ids") or []
        selected_id = _parse_candidate_selection(message, candidate_ids)
        selected = catalog.get_procedure(selected_id)
        if selected:
            remaining = unresolved_questions(selected, answers)
            return {
                "route": "clarify" if remaining else "checklist",
                "rewritten_query": message,
                "selected_procedure_id": selected.id,
                "answers": answers,
                "pending_action": "answer_clarification" if remaining else None,
                "pending_procedure_ids": [],
                "pending_question_keys": [question.key for question in remaining],
            }
        return {
            "route": "clarify",
            "rewritten_query": message,
            "answers": answers,
            "pending_action": "select_procedure",
            "pending_procedure_ids": candidate_ids,
            "pending_question_keys": [],
        }
    pending = unresolved_questions(procedure, answers) if procedure else []
    unresolved = [question.key for question in pending]

    deterministic = extract_answers(message, pending)
    if deterministic:
        answers.update(deterministic)
        remaining = unresolved_questions(procedure, answers)
        explicit_route = _explicit_response_route(message)
        return {
            "route": explicit_route or ("clarify" if remaining else "checklist"),
            "rewritten_query": message,
            "answers": answers,
            "pending_action": "answer_clarification" if remaining else None,
            "pending_procedure_ids": [],
            "pending_question_keys": [question.key for question in remaining],
        }

    decision = await _llm_decision(state, message, procedure, answers, unresolved)
    if decision is None:
        decision = _rule_decision(message, procedure)

    # Invariant của graph: chưa có thủ tục thì mọi route nghiệp vụ khác đều
    # thiếu context. LLM có thể hiểu "cần làm rõ" theo nghĩa hội thoại và trả
    # clarify, nhưng lượt này bắt buộc phải qua retrieval để identify trước.
    if procedure is None:
        decision.route = "identify"

    allowed_keys = set(unresolved)
    accepted_answers = 0
    for extracted in decision.extracted_answers:
        if extracted.key in allowed_keys:
            answers[extracted.key] = _coerce(extracted.value)
            accepted_answers += 1

    explicit_route = _explicit_response_route(message)
    if explicit_route and procedure:
        decision.route = explicit_route
    elif accepted_answers and procedure:
        decision.route = (
            "clarify" if unresolved_questions(procedure, answers) else "checklist"
        )

    remaining = unresolved_questions(procedure, answers) if procedure else []

    return {
        "route": decision.route,
        "rewritten_query": decision.rewritten_query.strip() or message,
        "answers": answers,
        "pending_action": "answer_clarification" if remaining else None,
        "pending_procedure_ids": [],
        "pending_question_keys": [question.key for question in remaining],
    }


async def _llm_decision(
    state: GuidanceState,
    message: str,
    procedure: Any,
    answers: dict[str, Any],
    unresolved: list[str],
) -> PlannerDecision | None:
    if not llm_is_configured():
        return None
    try:
        summary = "\n".join(
            f"- {p.id}: {p.name} ({p.agency})" for p in catalog.load_catalog().values()
        )
        history_lines = [
            f"{m.type}: {m.content}" for m in (state.get("messages") or [])[-6:-1]
        ]
        context = planner_context(
            catalog_summary=summary,
            selected_procedure=procedure.id if procedure else None,
            answered_keys=sorted(answers),
            unresolved_keys=unresolved,
            history="\n".join(history_lines),
            message=message,
        )
        llm = get_llm().with_structured_output(PlannerDecision)
        decision = await llm.ainvoke(
            [SystemMessage(content=PLANNER_SYSTEM), HumanMessage(content=context)]
        )
        if isinstance(decision, PlannerDecision):
            return decision
        return PlannerDecision.model_validate(decision)
    except Exception:
        logger.warning("Planner LLM lỗi — dùng rule-based fallback", exc_info=True)
        return None


def _rule_decision(message: str, procedure: Any) -> PlannerDecision:
    """Fallback deterministic sau khi answer extraction không tìm thấy dữ liệu."""
    if procedure is None:
        return PlannerDecision(route="identify", rewritten_query=message)
    folded = fold_ascii(message)
    if any(keyword in folded for keyword in _CHECKLIST_KEYWORDS):
        return PlannerDecision(route="checklist", rewritten_query=message)
    return PlannerDecision(route="answer", rewritten_query=message)


def _coerce(value: str) -> Any:
    lowered = value.strip().casefold()
    if lowered in {"true", "có", "co", "yes"}:
        return True
    if lowered in {"false", "không", "khong", "no"}:
        return False
    if lowered.lstrip("-").isdigit():
        return int(lowered)
    return value.strip()


def _last_human_text(state: GuidanceState) -> str:
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", "") == "human":
            return str(message.content)
    return ""


def _explicit_response_route(message: str) -> Literal["answer", "checklist"] | None:
    folded = fold_ascii(message)
    if any(keyword in folded for keyword in _CHECKLIST_KEYWORDS):
        return "checklist"
    answer_keywords = (
        "le phi", "bao nhieu tien", "thoi han", "may ngay", "bao lau",
        "co quan", "noi nop", "nop o dau",
    )
    if any(keyword in folded for keyword in answer_keywords):
        return "answer"
    return None


def _parse_candidate_selection(message: str, candidate_ids: list[str]) -> str | None:
    folded = fold_ascii(message).strip()
    numeric = re.fullmatch(r"(?:so\s*)?(\d+)", folded)
    if numeric:
        index = int(numeric.group(1)) - 1
        return candidate_ids[index] if 0 <= index < len(candidate_ids) else None
    if folded in {"thu tuc dau tien", "dau tien"} and candidate_ids:
        return candidate_ids[0]
    for procedure_id in candidate_ids:
        procedure = catalog.get_procedure(procedure_id)
        if procedure and any(
            fold_ascii(name) in folded
            for name in [procedure.name, *procedure.aliases]
        ):
            return procedure_id
    return None
