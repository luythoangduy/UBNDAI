"""Chat guidance endpoint. Owner: Dev A. Handler mỏng — logic nằm trong src/agents."""

from fastapi import APIRouter, HTTPException

from src.agents.graph import run_guidance
from src.models import ChatRequest, ChatResponse
from src.services.cases import CaseNotFoundError, ConcurrentCaseUpdateError

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    """Một lượt hội thoại guidance: clarify / identify / checklist / answer."""
    try:
        return await run_guidance(payload)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy case: {exc}") from exc
    except ConcurrentCaseUpdateError as exc:
        raise HTTPException(
            status_code=409,
            detail="Case vừa được cập nhật bởi một request khác; vui lòng gửi lại.",
        ) from exc
