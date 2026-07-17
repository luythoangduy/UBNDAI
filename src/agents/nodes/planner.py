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
from src.models import IntentName
from src.services import catalog
from src.services.clarification import (
    extract_answers,
    is_correction_message,
    unresolved_questions,
)
from src.services.intent import IntentDetection, detect_intents
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
    route: Literal["clarify", "identify", "checklist", "answer", "fallback"]
    rewritten_query: str = ""
    primary_intent: IntentName = "unknown"
    detected_intents: list[IntentName] = Field(default_factory=list)
    extracted_answers: list[ExtractedAnswer] = Field(default_factory=list)


async def run(state: GuidanceState) -> dict[str, Any]:
    message = _last_human_text(state)
    procedure = catalog.get_procedure(state.get("selected_procedure_id"))
    answers = dict(state.get("answers") or {})
    detection = detect_intents(message, has_selected_procedure=procedure is not None)

    if state.get("pending_action") == "confirm_switch_procedure":
        confirmation = _confirmation_value(message)
        if confirmation is True:
            switch_query = state.get("pending_switch_query") or message
            return _switch_procedure_result(switch_query)
        if confirmation is False:
            return {
                "route": "answer",
                "rewritten_query": message,
                "answers": answers,
                "primary_intent": "switch_confirmation",
                "detected_intents": ["switch_confirmation"],
                "pending_action": None,
                "pending_procedure_ids": [],
                "pending_question_keys": [],
                "pending_switch_query": None,
            }
        return {
            "route": "clarify",
            "rewritten_query": message,
            "answers": answers,
            "primary_intent": "switch_confirmation",
            "detected_intents": ["switch_confirmation"],
            "pending_action": "confirm_switch_procedure",
            "pending_procedure_ids": [],
            "pending_question_keys": [],
            "pending_switch_query": state.get("pending_switch_query"),
        }

    if (
        procedure
        and detection.primary == "switch_procedure"
        and not _message_affirms_current_procedure(message, procedure)
    ):
        has_uploaded_documents = any(
            item.get("document_id") for item in state.get("checklist") or []
        )
        if has_uploaded_documents:
            return {
                "route": "clarify",
                "rewritten_query": message,
                "answers": answers,
                "primary_intent": "switch_procedure",
                "detected_intents": ["switch_procedure"],
                "pending_action": "confirm_switch_procedure",
                "pending_procedure_ids": [],
                "pending_question_keys": [],
                "pending_switch_query": message,
            }
        return _switch_procedure_result(message)

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
                "primary_intent": "clarification_answer",
                "detected_intents": ["clarification_answer"],
                "pending_action": "answer_clarification" if remaining else None,
                "pending_procedure_ids": [],
                "pending_question_keys": [question.key for question in remaining],
            }
        return {
            "route": "clarify",
            "rewritten_query": message,
            "answers": answers,
            "primary_intent": "unknown",
            "detected_intents": ["unknown"],
            "pending_action": "select_procedure",
            "pending_procedure_ids": candidate_ids,
            "pending_question_keys": [],
        }
    pending = unresolved_questions(procedure, answers) if procedure else []
    unresolved = [question.key for question in pending]

    deterministic = extract_answers(message, pending)
    if procedure:
        all_questions = procedure.clarifying_questions
        correction_answers = extract_answers(
            message,
            all_questions,
            allow_standalone=is_correction_message(message),
        )
        deterministic.update(correction_answers)
    if deterministic:
        answers.update(deterministic)
        remaining = unresolved_questions(procedure, answers)
        intents = (
            []
            if detection.intents in (["general_question"], ["unknown"])
            else list(detection.intents)
        )
        if "clarification_answer" not in intents:
            intents.append("clarification_answer")
        if detection.primary not in {"general_question", "unknown"} or not llm_is_configured():
            return {
                "route": _route_for_intents(
                    intents,
                    procedure_exists=True,
                    has_remaining_questions=bool(remaining),
                    default_route="clarify",
                ),
                "rewritten_query": message,
                "answers": answers,
                "primary_intent": (
                    "clarification_answer"
                    if intents == ["clarification_answer"]
                    else detection.primary
                ),
                "detected_intents": intents,
                "pending_action": "answer_clarification" if remaining else None,
                "pending_procedure_ids": [],
                "pending_question_keys": [question.key for question in remaining],
            }
        pending = remaining
        unresolved = [question.key for question in pending]

    decision = await _llm_decision(state, message, procedure, answers, unresolved)
    if decision is None:
        decision = _rule_decision(message, procedure, detection)

    allowed_keys = set(unresolved)
    accepted_answers = len(deterministic)
    for extracted in decision.extracted_answers:
        if extracted.key in allowed_keys:
            answers[extracted.key] = _coerce(extracted.value)
            accepted_answers += 1

    remaining = unresolved_questions(procedure, answers) if procedure else []
    llm_intents = [
        intent for intent in decision.detected_intents if intent != "unknown"
    ]
    use_llm_intents = (
        detection.primary in {"general_question", "unknown"} and bool(llm_intents)
    )
    base_intents = llm_intents if use_llm_intents else list(detection.intents)
    primary_intent = (
        decision.primary_intent if use_llm_intents else detection.primary
    )
    intents = (
        []
        if accepted_answers
        and base_intents in (["general_question"], ["unknown"])
        else base_intents
    )
    if accepted_answers and "clarification_answer" not in intents:
        intents.append("clarification_answer")
    decision.route = _route_for_intents(
        intents,
        procedure_exists=procedure is not None,
        has_remaining_questions=bool(remaining),
        default_route=decision.route,
    )

    return {
        "route": decision.route,
        "rewritten_query": decision.rewritten_query.strip() or message,
        "answers": answers,
        "primary_intent": (
            "clarification_answer"
            if primary_intent in {"general_question", "unknown"}
            and intents == ["clarification_answer"]
            else primary_intent
        ),
        "detected_intents": intents,
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


def _rule_decision(
    message: str, procedure: Any, detection: IntentDetection
) -> PlannerDecision:
    """Fallback deterministic sau khi answer extraction không tìm thấy dữ liệu."""
    route = _route_for_intents(
        detection.intents,
        procedure_exists=procedure is not None,
        has_remaining_questions=False,
        default_route="answer" if procedure else "fallback",
    )
    return PlannerDecision(
        route=route,
        rewritten_query=message,
        primary_intent=detection.primary,
        detected_intents=detection.intents,
    )


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


def _route_for_intents(
    intents: list[IntentName],
    *,
    procedure_exists: bool,
    has_remaining_questions: bool,
    default_route: Literal["clarify", "identify", "checklist", "answer", "fallback"],
) -> Literal["clarify", "identify", "checklist", "answer", "fallback"]:
    non_procedural = {
        "greeting", "thanks", "capabilities", "out_of_scope", "status_tracking",
        "submission", "document_upload",
    }
    informational = {
        "fee", "processing_time", "agency", "legal_basis", "forms",
        "general_question",
    }
    if any(intent in non_procedural for intent in intents):
        return "answer"
    if not procedure_exists:
        if "legal_basis" in intents:
            return "answer"
        if "procedure_discovery" in intents:
            return "identify"
        if any(intent in informational or intent == "checklist" for intent in intents):
            return "clarify"
        return default_route
    if any(intent in informational for intent in intents):
        return "answer"
    if "checklist" in intents:
        return "checklist"
    if "clarification_answer" in intents:
        return "clarify" if has_remaining_questions else "checklist"
    return default_route


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


def _confirmation_value(message: str) -> bool | None:
    folded = fold_ascii(message).strip()
    if folded in {"co", "dong y", "xac nhan", "dung", "yes"}:
        return True
    if folded in {"khong", "huy", "giu nguyen", "no"}:
        return False
    return None


def _switch_procedure_result(query: str) -> dict[str, Any]:
    return {
        "route": "identify",
        "rewritten_query": query,
        "selected_procedure_id": None,
        "reset_procedure": True,
        "answers": {},
        "checklist": [],
        "primary_intent": "switch_procedure",
        "detected_intents": ["switch_procedure"],
        "pending_action": None,
        "pending_procedure_ids": [],
        "pending_question_keys": [],
        "pending_switch_query": None,
    }


def _message_affirms_current_procedure(message: str, procedure: Any) -> bool:
    folded = fold_ascii(message)
    for name in [procedure.name, *procedure.aliases]:
        phrase = fold_ascii(name)
        if phrase in folded and not any(
            prefix + phrase in folded
            for prefix in ("khong lam ", "khong phai ", "bo ")
        ):
            return True
    return False
