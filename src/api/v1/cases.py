"""Case lifecycle. Owner: Dev C."""

from fastapi import APIRouter

from src.models import Case, CaseCreate, CaseUpdate, ValidationReport

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=Case)
async def create_case(payload: CaseCreate) -> Case:
    raise NotImplementedError  # TODO(C)


@router.get("/{case_id}", response_model=Case)
async def get_case(case_id: str) -> Case:
    raise NotImplementedError  # TODO(C)


@router.patch("/{case_id}", response_model=Case)
async def update_case(case_id: str, payload: CaseUpdate) -> Case:
    raise NotImplementedError  # TODO(C)


@router.post("/{case_id}/validate", response_model=ValidationReport)
async def validate_case(case_id: str) -> ValidationReport:
    """Chạy rule engine + AI checker, cập nhật readiness_score."""
    # TODO(B): services.validation.run_validation(case_id)
    raise NotImplementedError


@router.post("/{case_id}/submit", response_model=Case)
async def submit_case(case_id: str) -> Case:
    """Handoff sang cổng DVC (mock ở MVP). Chặn nếu còn blocking error."""
    raise NotImplementedError  # TODO(C): services.portal_gateway
