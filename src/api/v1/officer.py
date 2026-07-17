"""Thin FastAPI routes for the officer portal."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.models import TokenClaims
from src.services.auth import issue_token, require_role, verify_credentials
from src.services.officer_store import store
from src.services.storage import StorageError, storage

router = APIRouter(tags=["auth", "officer"])


def _masked_case(case):
    payload = case.model_dump(mode="json")
    payload["citizen_id"] = "***"
    payload.pop("form_data", None)
    payload.pop("checklist", None)
    return payload


def _masked_document(document):
    payload = document.model_dump(mode="json")
    # Storage locations are never returned to the browser. A later signed-view
    # endpoint will authorize access before issuing a short-lived URL.
    payload.pop("file_uri", None)
    payload.pop("object_key", None)
    return payload


def _assert_case_mutation(case_id: str, claims: TokenClaims) -> None:
    case = store.get_case(case_id, claims.organization_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.assigned_to and case.assigned_to != claims.user_id and not ({"specialist", "supervisor"} & claims.roles):
        raise HTTPException(status_code=403, detail="Case is assigned to another officer")


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=200)


class DecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class TransitionRequest(BaseModel):
    target_status: str = Field(min_length=1, max_length=64)
    reason: str | None = Field(default=None, max_length=1000)


class SupplementRequestPayload(BaseModel):
    public_message: str = Field(min_length=1, max_length=5000)
    finding_ids: list[str] = Field(min_length=1, max_length=20)


class FieldEditRequest(BaseModel):
    normalized_value: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/auth/login")
async def login(payload: LoginRequest):
    identity = verify_credentials(payload.username, payload.password)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {"success": True, "data": {"access_token": issue_token(identity), "token_type": "bearer", "expires_in": 1800}}


@router.get("/officer/cases")
async def list_cases(
    q: str | None = Query(default=None, max_length=100),
    case_status: str | None = Query(default=None, alias="status", max_length=64),
    sort: str = Query(default="priority_desc", pattern="^(priority_desc|newest|oldest)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor")),
):
    cases = store.list_cases(claims.organization_id)
    if case_status:
        cases = [case for case in cases if case.status == case_status]
    if q:
        needle = q.casefold().strip()
        cases = [case for case in cases if needle in case.case_code.casefold() or needle in case.procedure_id.casefold()]
    if sort == "priority_desc":
        cases.sort(key=lambda item: (item.priority, item.updated_at), reverse=True)
    elif sort == "newest":
        cases.sort(key=lambda item: item.updated_at, reverse=True)
    else:
        cases.sort(key=lambda item: item.updated_at)
    total = len(cases)
    start = (page - 1) * page_size
    cases = cases[start:start + page_size]
    return {"success": True, "data": [_masked_case(case) for case in cases], "pagination": {"page": page, "page_size": page_size, "total": total}}


@router.get("/officer/cases/{case_id}")
async def get_case(case_id: str, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    case = store.get_case(case_id, claims.organization_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    findings = store.findings_for(case_id, claims.organization_id)
    timeline = store.timeline(case_id, claims.organization_id)
    submission = store.submission_for(case_id)
    documents = [
        _masked_document(document)
        for document in store.documents.values()
        if document.case_id == case_id
    ]
    return {"success": True, "data": {"case": _masked_case(case), "submission": submission.model_dump(mode="json"), "documents": documents, "findings": [item.model_dump(mode="json") for item in findings], "timeline": [item.model_dump(mode="json") for item in timeline]}}


@router.get("/officer/cases/{case_id}/timeline")
async def case_timeline(case_id: str, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    if store.get_case(case_id, claims.organization_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"success": True, "data": [item.model_dump(mode="json") for item in store.timeline(case_id, claims.organization_id)]}


@router.post("/officer/cases/{case_id}/claim")
async def claim_case(case_id: str, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    try:
        case = store.claim(case_id, claims.organization_id, claims.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Case is already claimed") from exc
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"success": True, "data": _masked_case(case)}


@router.post("/officer/cases/{case_id}/transition")
async def transition_case(case_id: str, payload: TransitionRequest, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    _assert_case_mutation(case_id, claims)
    if payload.target_status == "closed" and "supervisor" not in claims.roles:
        raise HTTPException(status_code=403, detail="Only supervisor can close a case")
    try:
        case = store.transition(case_id, claims.organization_id, claims.user_id, payload.target_status, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"success": True, "data": _masked_case(case)}


@router.get("/officer/cases/{case_id}/findings")
async def list_findings(case_id: str, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    if store.get_case(case_id, claims.organization_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    findings = store.findings_for(case_id, claims.organization_id)
    return {"success": True, "data": [item.model_dump(mode="json") for item in findings]}


@router.post("/officer/findings/{finding_id}/accept")
async def accept_finding(finding_id: str, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    case = store.case_for_finding(finding_id, claims.organization_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    _assert_case_mutation(case.id, claims)
    try:
        finding = store.decide(finding_id, claims.organization_id, claims.user_id, "accepted")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc
    return {"success": True, "data": finding.model_dump(mode="json")}


@router.post("/officer/findings/{finding_id}/dismiss")
async def dismiss_finding(finding_id: str, payload: DecisionRequest, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    case = store.case_for_finding(finding_id, claims.organization_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    _assert_case_mutation(case.id, claims)
    try:
        finding = store.decide(finding_id, claims.organization_id, claims.user_id, "dismissed", payload.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "data": finding.model_dump(mode="json")}


@router.post("/officer/findings/{finding_id}/escalate")
async def escalate_finding(finding_id: str, payload: DecisionRequest, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    case = store.case_for_finding(finding_id, claims.organization_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    _assert_case_mutation(case.id, claims)
    try:
        finding = store.decide(finding_id, claims.organization_id, claims.user_id, "escalated", payload.reason)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "data": finding.model_dump(mode="json")}


@router.get("/officer/documents/{document_id}/fields")
async def document_fields(document_id: str, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    try:
        fields = store.fields_for_document(document_id, claims.organization_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    return {"success": True, "data": [item.model_dump(mode="json") for item in fields]}


@router.get("/officer/documents/{document_id}/content")
async def document_content(document_id: str, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    document = store.documents.get(document_id)
    case = store.get_case(document.case_id, claims.organization_id) if document else None
    if document is None or case is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        content = storage.get(document.object_key or "")
    except StorageError as exc:
        raise HTTPException(status_code=404, detail="Document content is unavailable") from exc
    return Response(
        content=content,
        media_type=document.content_type or "application/octet-stream",
        headers={"Content-Disposition": "inline", "Cache-Control": "private, no-store"},
    )


@router.patch("/officer/extracted-fields/{field_id}")
async def edit_field(field_id: str, payload: FieldEditRequest, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    field_record = store.extracted_fields.get(field_id)
    document = store.documents.get(field_record.document_id) if field_record else None
    if document is None:
        raise HTTPException(status_code=404, detail="Field not found")
    _assert_case_mutation(document.case_id, claims)
    try:
        field = store.update_field(field_id, claims.organization_id, claims.user_id, payload.normalized_value, payload.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Field not found") from exc
    return {"success": True, "data": field.model_dump(mode="json")}


@router.post("/officer/cases/{case_id}/rerun-validation")
async def rerun_validation(case_id: str, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    _assert_case_mutation(case_id, claims)
    try:
        findings = store.rerun_validation(case_id, claims.organization_id, claims.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    return {"success": True, "data": [item.model_dump(mode="json") for item in findings]}


@router.post("/officer/cases/{case_id}/supplement-requests")
async def create_supplement(case_id: str, payload: SupplementRequestPayload, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    _assert_case_mutation(case_id, claims)
    try:
        request = store.create_supplement(case_id, claims.organization_id, claims.user_id, payload.public_message, payload.finding_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "data": request.model_dump(mode="json")}


@router.get("/officer/cases/{case_id}/supplement-requests")
async def list_supplements(case_id: str, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    try:
        requests = store.supplements_for(case_id, claims.organization_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    return {"success": True, "data": [item.model_dump(mode="json") for item in requests]}


@router.get("/officer/dashboard/summary")
async def dashboard_summary(claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    cases = store.list_cases(claims.organization_id)
    case_ids = {case.id for case in cases}
    documents = [document for document in store.documents.values() if document.case_id in case_ids]
    return {"success": True, "data": {
        "total": len(cases),
        "awaiting_review": sum(case.status == "awaiting_officer_review" for case in cases),
        "in_review": sum(case.status == "in_officer_review" for case in cases),
        "needs_citizen_update": sum(case.status == "needs_citizen_update" for case in cases),
        "document_total": len(documents),
        "document_ready": sum(document.ocr_status == "ready" for document in documents),
        "document_manual_review": sum(document.ocr_status == "manual_review_required" for document in documents),
        "document_processing": sum(document.ocr_status in {"upload_pending", "uploaded", "scanning", "ocr_processing"} for document in documents),
        "document_rejected": sum(document.ocr_status == "rejected" for document in documents),
    }}
