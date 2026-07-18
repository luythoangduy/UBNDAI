"""Canonical application workflow and officer dashboard endpoints."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.models import TokenClaims
from src.models.application_management import project_application_status
from src.services.auth import require_role
from src.services.application_management_service import (
    ApplicationConflict,
    ApplicationNotFound,
    application_management_service,
)
from src.services.officer_store import store

router = APIRouter(tags=["applications", "officer-dashboard"])
OfficerClaims = Depends(require_role("officer_reviewer", "specialist", "supervisor"))


class CreateApplicationRequest(BaseModel):
    procedure_id: str = Field(min_length=1, max_length=100)
    locality_code: str = Field(min_length=1, max_length=30)
    citizen_id: str = Field(min_length=1, max_length=100)


class AssignmentRequest(BaseModel):
    assigned_to: str | None = Field(default=None, max_length=100)
    expected_version: int = Field(ge=1)


class DocumentMetadataRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(pattern=r"^(application/pdf|image/(png|jpeg))$")
    size_bytes: int = Field(gt=0, le=20 * 1024 * 1024)


class ResubmitRequest(BaseModel):
    expected_version: int = Field(ge=1)
    form_data: dict = Field(default_factory=dict)


def _case_or_404(application_id: str, claims: TokenClaims):
    try:
        return application_management_service.get(application_id, claims.organization_id)
    except ApplicationNotFound as exc:
        raise HTTPException(404, "Application not found") from exc


@router.post("/applications", status_code=201)
async def create_application(payload: CreateApplicationRequest, claims: TokenClaims = OfficerClaims):
    if payload.citizen_id == "***":
        raise HTTPException(422, "A real citizen identifier is required")
    case = application_management_service.create(claims.organization_id, claims.user_id, payload.citizen_id, payload.procedure_id, payload.locality_code)
    return {"success": True, "data": {"id": case.id, "case_code": case.case_code, "version": case.version}}


@router.patch("/applications/{application_id}/assignment")
async def assign_application(application_id: str, payload: AssignmentRequest, claims: TokenClaims = OfficerClaims):
    try:
        case = application_management_service.assign(application_id, claims.organization_id, claims.user_id, payload.assigned_to, payload.expected_version)
    except ApplicationNotFound as exc:
        raise HTTPException(404, "Application not found") from exc
    except ApplicationConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"success": True, "data": {"id": case.id, "assigned_to": case.assigned_to, "version": case.version}}


@router.post("/applications/{application_id}/documents", status_code=201)
async def add_document(application_id: str, payload: DocumentMetadataRequest, claims: TokenClaims = OfficerClaims):
    try:
        document = application_management_service.register_document(application_id, claims.organization_id, claims.user_id, payload.filename, payload.content_type, payload.size_bytes)
    except ApplicationNotFound as exc:
        raise HTTPException(404, "Application not found") from exc
    return {"success": True, "data": {"id": document.id, "ocr_status": document.ocr_status}}


@router.post("/applications/{application_id}/analyze", status_code=202)
async def analyze_application(application_id: str, claims: TokenClaims = OfficerClaims):
    try:
        findings = application_management_service.analyze(application_id, claims.organization_id, claims.user_id)
    except ApplicationNotFound as exc:
        raise HTTPException(404, "Application not found") from exc
    except ApplicationConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"success": True, "data": {"status": "completed", "finding_count": len(findings)}}


@router.post("/applications/{application_id}/resubmit")
async def resubmit_application(application_id: str, payload: ResubmitRequest, claims: TokenClaims = OfficerClaims):
    try:
        case = application_management_service.resubmit(application_id, claims.organization_id, claims.user_id, payload.expected_version, payload.form_data)
    except ApplicationNotFound as exc:
        raise HTTPException(404, "Application not found") from exc
    except ApplicationConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"success": True, "data": {"id": case.id, "version": case.version, "submission_version": case.current_submission_version}}


@router.get("/applications/{application_id}/events")
async def application_events(application_id: str, claims: TokenClaims = OfficerClaims):
    _case_or_404(application_id, claims)
    return {"success": True, "data": [item.model_dump(mode="json") for item in store.timeline(application_id, claims.organization_id)]}


def _period(from_date: date | None, to_date: date | None, timezone_name: str):
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, "Unknown timezone") from exc
    end = to_date or datetime.now(zone).date()
    start = from_date or end - timedelta(days=29)
    if start > end or (end - start).days > 366:
        raise HTTPException(422, "Invalid date range")
    return start, end, zone


def _filtered_cases(claims, from_date, to_date, timezone_name):
    start, end, zone = _period(from_date, to_date, timezone_name)
    lower = datetime.combine(start, time.min, zone).astimezone(timezone.utc)
    upper = datetime.combine(end + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    cases = [item for item in store.list_cases(claims.organization_id) if lower <= (item.submitted_at or item.created_at) < upper]
    return cases, start, end, zone


def _metric_params(from_date, to_date, timezone_name, granularity):
    if granularity not in {"day", "week", "month"}:
        raise HTTPException(422, "Invalid granularity")
    return _period(from_date, to_date, timezone_name)


@router.get("/officer-dashboard/summary")
async def management_summary(from_date: date | None = Query(None, alias="from"), to_date: date | None = Query(None, alias="to"), timezone_name: str = Query("Asia/Bangkok", alias="timezone"), granularity: str = "day", claims: TokenClaims = OfficerClaims):
    _metric_params(from_date, to_date, timezone_name, granularity)
    cases, _, _, _ = _filtered_cases(claims, from_date, to_date, timezone_name)
    ids = {item.id for item in cases}
    findings = [item for item in store.findings.values() if item.case_id in ids and item.status == "open"]
    statuses = [project_application_status(item.status, has_caution=any(f.case_id == item.id for f in findings)) for item in cases]
    return {"success": True, "data": {"total": len(cases), "ready": sum(s == "READY_FOR_PROCESSING" for s in statuses), "caution": sum(s == "CAUTION_REVIEW_REQUIRED" for s in statuses), "in_process": sum(s == "IN_PROCESS" for s in statuses), "returned": sum(s == "RETURNED_TO_CITIZEN" for s in statuses), "open_anomalies": len(findings)}}


@router.get("/officer-dashboard/timeseries")
async def management_timeseries(from_date: date | None = Query(None, alias="from"), to_date: date | None = Query(None, alias="to"), timezone_name: str = Query("Asia/Bangkok", alias="timezone"), granularity: Literal["day", "week", "month"] = "day", claims: TokenClaims = OfficerClaims):
    cases, start, end, zone = _filtered_cases(claims, from_date, to_date, timezone_name)
    def label(value: date) -> str:
        if granularity == "week":
            return (value - timedelta(days=value.weekday())).isoformat()
        if granularity == "month":
            return value.replace(day=1).isoformat()
        return value.isoformat()
    buckets = Counter(label((item.submitted_at or item.created_at).astimezone(zone).date()) for item in cases)
    cursor, labels = start, []
    while cursor <= end:
        bucket = label(cursor)
        if not labels or labels[-1] != bucket:
            labels.append(bucket)
        cursor += timedelta(days=1)
    return {"success": True, "data": [{"period": key, "count": buckets[key]} for key in labels]}


def _distribution(cases, key):
    counts = Counter(key(item) or "UNKNOWN" for item in cases)
    return [{"key": name, "count": count} for name, count in sorted(counts.items())]


@router.get("/officer-dashboard/status-distribution")
async def status_distribution(from_date: date | None = Query(None, alias="from"), to_date: date | None = Query(None, alias="to"), timezone_name: str = Query("Asia/Bangkok", alias="timezone"), granularity: str = "day", claims: TokenClaims = OfficerClaims):
    _metric_params(from_date, to_date, timezone_name, granularity)
    cases, *_ = _filtered_cases(claims, from_date, to_date, timezone_name)
    return {"success": True, "data": _distribution(cases, lambda item: project_application_status(item.status, has_caution=bool(store.findings_for(item.id, claims.organization_id))))}


@router.get("/officer-dashboard/application-types")
async def application_types(from_date: date | None = Query(None, alias="from"), to_date: date | None = Query(None, alias="to"), timezone_name: str = Query("Asia/Bangkok", alias="timezone"), granularity: str = "day", claims: TokenClaims = OfficerClaims):
    _metric_params(from_date, to_date, timezone_name, granularity)
    cases, *_ = _filtered_cases(claims, from_date, to_date, timezone_name)
    return {"success": True, "data": _distribution(cases, lambda item: item.procedure_id)}


@router.get("/officer-dashboard/anomalies")
async def anomaly_distribution(from_date: date | None = Query(None, alias="from"), to_date: date | None = Query(None, alias="to"), timezone_name: str = Query("Asia/Bangkok", alias="timezone"), granularity: str = "day", claims: TokenClaims = OfficerClaims):
    _metric_params(from_date, to_date, timezone_name, granularity)
    cases, *_ = _filtered_cases(claims, from_date, to_date, timezone_name)
    ids = {item.id for item in cases}
    counts = Counter(item.type for item in store.findings.values() if item.case_id in ids and item.status == "open")
    return {"success": True, "data": [{"key": key, "count": value} for key, value in sorted(counts.items())]}
