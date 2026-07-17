"""Legacy case lifecycle API used by the guidance flow."""

from fastapi import APIRouter, HTTPException

from src.config import settings
from src.models import Case, CaseCreate, CaseUpdate, ValidationReport
from src.services import cases as case_service
from src.services.cases import CaseNotFoundError, ConcurrentCaseUpdateError
from src.services.validation.rule_engine import RuleFileError, run as run_rules

router = APIRouter(prefix="/cases", tags=["cases"])


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail="Case not found")


@router.post("", response_model=Case)
async def create_case(payload: CaseCreate) -> Case:
    return await case_service.create(payload)


@router.get("/{case_id}", response_model=Case)
async def get_case(case_id: str) -> Case:
    try:
        return await case_service.get(case_id)
    except CaseNotFoundError as exc:
        raise _not_found(exc) from exc


@router.patch("/{case_id}", response_model=Case)
async def update_case(case_id: str, payload: CaseUpdate) -> Case:
    try:
        return await case_service.update(case_id, payload)
    except CaseNotFoundError as exc:
        raise _not_found(exc) from exc
    except ConcurrentCaseUpdateError as exc:
        raise HTTPException(status_code=409, detail="Case was updated by another request") from exc


@router.post("/{case_id}/validate", response_model=ValidationReport)
async def validate_case(case_id: str) -> ValidationReport:
    """Run deterministic rules over currently persisted form/checklist data."""
    try:
        case = await case_service.get(case_id)
        report = run_rules(case, [])
        await case_service.save(case.model_copy(update={"readiness_score": report.readiness_score}))
        return report
    except CaseNotFoundError as exc:
        raise _not_found(exc) from exc
    except RuleFileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ConcurrentCaseUpdateError as exc:
        raise HTTPException(status_code=409, detail="Case was updated by another request") from exc


@router.post("/{case_id}/submit", response_model=Case)
async def submit_case(case_id: str) -> Case:
    """Mark a validated legacy case submitted to the local P0 gateway."""
    try:
        case = await case_service.get(case_id)
        if case.status != "ready" or case.readiness_score < settings.readiness_submit_threshold:
            raise HTTPException(status_code=422, detail="Case is not ready for submission")
        return await case_service.update(case_id, CaseUpdate(status="submitted"))
    except CaseNotFoundError as exc:
        raise _not_found(exc) from exc
    except ConcurrentCaseUpdateError as exc:
        raise HTTPException(status_code=409, detail="Case was updated by another request") from exc
