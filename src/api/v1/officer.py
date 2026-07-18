"""Thin FastAPI routes for the officer portal."""

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.models import TokenClaims
from src.models.application_management import ApplicationDecisionRequest, project_application_status
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


def _application_summary(case, claims: TokenClaims) -> dict:
    findings = store.findings_for(case.id, claims.organization_id)
    projected = project_application_status(case.status, has_caution=bool(findings))
    return {
        "id": case.id,
        "application_code": case.case_code,
        "case_code": case.case_code,
        "citizen_name": case.form_data.get("ho_ten_con") or case.form_data.get("citizen_name"),
        "citizen_id": "***",
        "application_type_code": case.procedure_id,
        "application_type_name": case.procedure_id,
        "classification_confidence": None,
        "status": projected,
        "application_status": projected,
        "internal_status": case.status,
        "anomaly_count": len(findings),
        "assigned_officer_name": case.assigned_to,
        "submitted_at": case.submitted_at,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "version": case.version,
    }


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


@router.get("/applications")
async def list_applications(
    q: str | None = Query(default=None, max_length=100),
    application_status: str | None = Query(default=None, alias="status", max_length=64),
    procedure_id: str | None = Query(default=None, max_length=100),
    application_type_code: str | None = Query(default=None, max_length=100),
    has_anomaly: bool | None = Query(default=None),
    severity: str | None = Query(default=None, pattern="^(error|warning|info)$"),
    assigned_to: str | None = Query(default=None, max_length=100),
    assigned_officer_id: str | None = Query(default=None, max_length=100),
    submitted_from: date | None = Query(default=None, alias="from"),
    submitted_to: date | None = Query(default=None, alias="to"),
    submitted_from_alt: date | None = Query(default=None, alias="submitted_from"),
    submitted_to_alt: date | None = Query(default=None, alias="submitted_to"),
    sort: str = Query(default="updated_desc", pattern="^(updated_desc|updated_asc|priority_desc)$"),
    sort_by: str | None = Query(default=None, max_length=32),
    sort_order: str | None = Query(default=None, pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor")),
):
    """Canonical application-management list; legacy /officer/cases remains supported."""
    procedure_id = procedure_id or application_type_code
    assigned_to = assigned_to or assigned_officer_id
    submitted_from = submitted_from or submitted_from_alt
    submitted_to = submitted_to or submitted_to_alt
    if sort_by:
        sort = "priority_desc" if sort_by == "priority" else ("updated_asc" if sort_order == "asc" else "updated_desc")
    items = store.list_cases(claims.organization_id)
    if q:
        needle = q.casefold().strip()
        items = [item for item in items if needle in item.case_code.casefold() or needle in item.procedure_id.casefold()]
    if application_status:
        items = [item for item in items if project_application_status(item.status, has_caution=bool(store.findings_for(item.id, claims.organization_id))) == application_status]
    if procedure_id:
        items = [item for item in items if item.procedure_id == procedure_id]
    if assigned_to:
        items = [item for item in items if item.assigned_to == assigned_to]
    if submitted_from:
        lower = datetime.combine(submitted_from, time.min, timezone.utc)
        items = [item for item in items if (item.submitted_at or item.created_at) >= lower]
    if submitted_to:
        upper = datetime.combine(submitted_to, time.max, timezone.utc)
        items = [item for item in items if (item.submitted_at or item.created_at) <= upper]
    if has_anomaly is not None or severity:
        filtered = []
        for item in items:
            findings = store.findings_for(item.id, claims.organization_id)
            matches = [finding for finding in findings if not severity or finding.severity == severity]
            if (has_anomaly is None and matches) or (has_anomaly is True and matches) or (has_anomaly is False and not matches):
                filtered.append(item)
        items = filtered
    if sort == "priority_desc":
        items.sort(key=lambda item: (item.priority, item.updated_at), reverse=True)
    else:
        items.sort(key=lambda item: item.updated_at, reverse=sort == "updated_desc")
    total = len(items)
    start = (page - 1) * page_size
    return {"success": True, "data": [_application_summary(item, claims) for item in items[start:start + page_size]], "pagination": {"page": page, "page_size": page_size, "total": total}}


@router.get("/applications/{application_id}")
async def get_application(application_id: str, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    case = store.get_case(application_id, claims.organization_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Application not found")
    findings = store.findings_for(application_id, claims.organization_id)
    summary = _application_summary(case, claims)
    anomalies = [{**item.model_dump(mode="json"), "code": item.type, "severity": item.severity.upper(), "detected_by": item.source} for item in findings]
    events = [item.model_dump(mode="json") for item in store.timeline(application_id, claims.organization_id)]
    documents = [_masked_document(document) for document in store.documents.values() if document.case_id == application_id]
    return {"success": True, "data": {**summary, "citizen_id": "***", "documents": documents, "extracted_fields": [], "anomalies": anomalies, "events": events, "form_data": case.form_data, "checklist": case.checklist, "application": {**_masked_case(case), "application_status": summary["application_status"]}, "findings": anomalies, "timeline": events}}


@router.post("/applications/{application_id}/decisions")
async def decide_application(application_id: str, payload: ApplicationDecisionRequest, claims: TokenClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))):
    case = store.get_case(application_id, claims.organization_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Application not found")
    _assert_case_mutation(application_id, claims)
    key = (application_id, payload.idempotency_key)
    if key in store.idempotency_results:
        return {"success": True, "data": store.idempotency_results[key], "idempotent": True}
    if payload.expected_version != case.version:
        raise HTTPException(status_code=409, detail="Application version has changed")
    target = "in_officer_review" if payload.decision == "CONTINUE_PROCESSING" else "needs_citizen_update"
    try:
        updated = store.transition(application_id, claims.organization_id, claims.user_id, target, payload.note or payload.citizen_message)
        if updated is None:
            raise HTTPException(status_code=404, detail="Application not found")
        result = {"application": {**_masked_case(updated), "application_status": project_application_status(updated.status, has_caution=bool(store.findings_for(application_id, claims.organization_id)))}, "decision": payload.decision}
        store.idempotency_results[key] = result
        return {"success": True, "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
