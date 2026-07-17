"""Chat guidance endpoint. Owner: Dev A. Handler mỏng — logic nằm trong src/agents."""

from fastapi import APIRouter

from src.models import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    """Một lượt hội thoại guidance: clarify / identify / checklist / answer."""
    # TODO(A): gọi src.agents.graph.run_guidance(payload)
    raise NotImplementedError
