"""Chat guidance endpoint. Owner: Dev A. Handler mỏng — logic nằm trong src/agents."""

from fastapi import APIRouter, Depends, HTTPException

from src.agents.graph import run_guidance
from src.models import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ChatStarterResponse,
    TokenClaims,
)
from src.services.chat_experience import starter_experience
from src.services import cases as case_service
from src.services.auth import optional_current_claims, require_role
from src.services.cases import CaseNotFoundError, ConcurrentCaseUpdateError

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/starter", response_model=ChatStarterResponse)
async def starter() -> ChatStarterResponse:
    return await starter_experience()


@router.get("/{case_id}/messages", response_model=ChatHistoryResponse)
async def chat_messages(
    case_id: str,
    claims: TokenClaims = Depends(require_role("citizen")),
) -> ChatHistoryResponse:
    """Return the signed-in citizen's transcript for reload/resume."""
    try:
        return await case_service.get_chat_history(case_id, claims.user_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    claims: TokenClaims | None = Depends(optional_current_claims),
) -> ChatResponse:
    """Một lượt hội thoại guidance: clarify / identify / checklist / answer."""
    try:
        citizen_id = claims.user_id if claims and "citizen" in claims.roles else None
        if citizen_id:
            return await run_guidance(payload, citizen_id=citizen_id)
        return await run_guidance(payload)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy case: {exc}") from exc
    except ConcurrentCaseUpdateError as exc:
        raise HTTPException(
            status_code=409,
            detail="Case vừa được cập nhật bởi một request khác; vui lòng gửi lại.",
        ) from exc
