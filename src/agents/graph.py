"""Guidance graph: ingest → planner → (clarify | identify | checklist | answer).

Owner: Dev A. Bài học từ C2-App-108: planner LLM-first + rule-based fallback,
few-shot cho follow-up routing, decompose query trước khi RRF.
"""

from src.agents.state import GuidanceState
from src.models import ChatRequest, ChatResponse


def build_graph():
    """Lắp graph LangGraph. TODO(A) Sprint 1."""
    # from langgraph.graph import StateGraph, END
    # g = StateGraph(GuidanceState)
    # g.add_node("planner", nodes.planner.run)        # route + rewrite, 1 LLM call structured
    # g.add_node("clarify", nodes.clarify.run)        # sinh câu hỏi làm rõ từ catalog
    # g.add_node("identify", nodes.identify.run)      # hybrid retrieval → chọn thủ tục
    # g.add_node("checklist", nodes.checklist.run)    # DocumentRequirement + answers → checklist
    # g.add_node("answer", nodes.answer.run)          # hỏi đáp kèm citation
    raise NotImplementedError


async def run_guidance(payload: ChatRequest) -> ChatResponse:
    """Entrypoint cho src/api/v1/chat.py: load Case, chạy graph, persist state về Case."""
    raise NotImplementedError  # TODO(A)
