"""Guidance graph: planner → (clarify | identify | checklist | answer).

Owner: Dev A. Bài học từ C2-App-108: planner LLM-first + rule-based fallback,
few-shot cho follow-up routing (trong prompts/planner.py).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from src.agents.nodes import answer, checklist, clarify, identify, planner
from src.agents.state import GuidanceState
from src.models import ChatRequest, ChatResponse, ChecklistItem, Citation
from src.services import cases
from src.services.guidance_bridge import resolve_case_id, sync_to_portal
from src.services.chat_experience import build_experience
from src.services.retrieval import NO_SOURCE_WARNING


def build_graph() -> Any:
    """Lắp graph LangGraph — planner định tuyến, mỗi node nghiệp vụ kết thúc lượt."""
    graph = StateGraph(GuidanceState)
    graph.add_node("planner", planner.run)
    graph.add_node("clarify", clarify.run)
    graph.add_node("identify", identify.run)
    graph.add_node("checklist", checklist.run)
    graph.add_node("answer", answer.run)

    graph.set_entry_point("planner")
    graph.add_conditional_edges(
        "planner",
        lambda state: state.get("route") or "answer",
        {
            "clarify": "clarify",
            "identify": "identify",
            "checklist": "checklist",
            "answer": "answer",
            "fallback": "answer",
        },
    )
    graph.add_conditional_edges(
        "identify",
        lambda state: "answer" if state.get("route") == "answer" else "end",
        {"answer": "answer", "end": END},
    )
    for node in ("clarify", "checklist", "answer"):
        graph.add_edge(node, END)
    return graph.compile()


@lru_cache(maxsize=1)
def _compiled_graph() -> Any:
    return build_graph()


async def run_guidance(
    payload: ChatRequest,
    citizen_id: str | None = None,
) -> ChatResponse:
    """Entrypoint cho src/api/v1/chat.py: load Case, chạy graph, persist state về Case."""
    case_id = await resolve_case_id(payload.case_id, citizen_id)

    async with cases.case_lock(case_id):
        case = await cases.get(case_id)
        response = await _run_locked_turn(case, payload.message)
        await sync_to_portal(case_id, citizen_id)
        return response


async def _run_locked_turn(case: Any, message: str) -> ChatResponse:
    """Chạy và commit trọn một lượt trong critical section của case."""

    history = await cases.get_messages(case.id)
    messages: list[Any] = [
        HumanMessage(content=m["content"])
        if m["role"] == "user"
        else AIMessage(content=m["content"])
        for m in history
    ]
    messages.append(HumanMessage(content=message))

    initial: GuidanceState = {
        "messages": messages,
        "case_id": case.id,
        "answers": dict(case.answers),
        "selected_procedure_id": case.procedure_id,
        "pending_action": case.pending_action,
        "pending_procedure_ids": list(case.pending_procedure_ids),
        "pending_question_keys": list(case.pending_question_keys),
        "pending_switch_query": case.pending_switch_query,
        "checklist": [item.model_dump() for item in case.checklist],
    }
    final = await _compiled_graph().ainvoke(initial)

    updates: dict[str, Any] = {
        "answers": final.get("answers", case.answers),
        "procedure_id": (
            final.get("selected_procedure_id")
            or (None if final.get("reset_procedure") else case.procedure_id)
        ),
        "pending_action": final.get("pending_action"),
        "pending_procedure_ids": final.get("pending_procedure_ids") or [],
        "pending_question_keys": final.get("pending_question_keys") or [],
        "pending_switch_query": final.get("pending_switch_query"),
    }
    checklist_items = [
        ChecklistItem.model_validate(item) for item in final.get("checklist") or []
    ]
    if checklist_items:
        updates["checklist"] = checklist_items
        if case.status == "draft":  # draft → collecting: đã có checklist
            updates["status"] = "collecting"
    elif final.get("reset_procedure"):
        updates["checklist"] = []
        updates["status"] = "draft"
    reply = final.get("reply") or NO_SOURCE_WARNING
    case = await cases.commit_turn(
        case.model_copy(update=updates),
        message,
        reply,
    )
    experience = await build_experience(case.procedure_id, message)

    return ChatResponse(
        case_id=case.id,
        reply=reply,
        kind=final.get("reply_kind") or "fallback",
        primary_intent=final.get("primary_intent") or "unknown",
        detected_intents=final.get("detected_intents") or [],
        clarifying_questions=final.get("pending_questions") or [],
        citations=[
            Citation.model_validate(item) for item in final.get("citations") or []
        ],
        procedure_id=experience.procedure_id,
        actions=experience.actions,
        templates=experience.templates,
        evidence=experience.evidence,
        cache=experience.cache,
    )
