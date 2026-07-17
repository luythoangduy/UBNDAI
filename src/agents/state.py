"""LangGraph state cho guidance agent. Owner: Dev A.

Giữ state typed và explicit (AGENTS.md §6). Pattern copy từ C2-App-108/src/agents/state.py.
"""

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from src.models.chat import IntentName


class GuidanceState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    case_id: str
    # Kết quả planner (1 LLM call structured: intent + rewrite + route)
    route: Literal["clarify", "identify", "checklist", "answer", "fallback"]
    rewritten_query: str
    primary_intent: IntentName
    detected_intents: list[IntentName]
    # Nhận diện thủ tục
    candidate_procedures: list[dict[str, Any]]  # [{procedure_id, score}]
    selected_procedure_id: str | None
    identify_confidence: float
    # Làm rõ
    answers: dict[str, Any]  # tích luỹ từ các lượt clarify, ghi về Case.answers
    pending_questions: list[str]
    pending_action: Literal[
        "select_procedure", "answer_clarification", "confirm_switch_procedure"
    ] | None
    pending_procedure_ids: list[str]
    pending_question_keys: list[str]
    pending_switch_query: str | None
    reset_procedure: bool
    # Retrieval + citation
    retrieved_chunks: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    # Checklist sinh ra trong lượt này (ChecklistItem.model_dump), persist về Case
    checklist: list[dict[str, Any]]
    # Output
    reply: str
    reply_kind: Literal["clarify", "checklist", "answer", "fallback"]
