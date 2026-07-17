"""Legacy operations endpoints backed by deterministic local-P0 services."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from src.models import AnomalyAlert, Assignment, Case, CaseSummary, DailyDigest, MetricPoint
from src.services import cases
from src.services.cases import CaseNotFoundError, ConcurrentCaseUpdateError
from src.services.ops.assignment import auto_assign as assign_case
from src.services.ops.summarizer import daily_digest as build_digest
from src.services.ops.summarizer import summarize_case

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/queue", response_model=list[Case])
async def my_queue(officer_id: str) -> list[Case]:
    assigned = [case for case in await cases.list_all() if case.assigned_officer_id == officer_id]
    return sorted(assigned, key=lambda case: (sum(item.status == "uncertain" for item in case.checklist), case.updated_at), reverse=True)


@router.post("/assign", response_model=Assignment)
async def auto_assign(case_id: str) -> Assignment:
    try:
        return await assign_case(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except ConcurrentCaseUpdateError as exc:
        raise HTTPException(status_code=409, detail="Case was updated by another request") from exc


@router.get("/cases/{case_id}/summary", response_model=CaseSummary)
async def case_summary(case_id: str) -> CaseSummary:
    try:
        return await summarize_case(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@router.get("/digest", response_model=DailyDigest)
async def daily_digest(officer_id: str, date: str) -> DailyDigest:
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must use YYYY-MM-DD") from exc
    return await build_digest(officer_id, date)


@router.get("/metrics", response_model=list[MetricPoint])
async def metrics(metric: str, days: int = Query(default=14, ge=1, le=90)) -> list[MetricPoint]:
    if metric not in {"error_rate", "late_rate", "volume", "avg_readiness"}:
        raise HTTPException(status_code=422, detail="Unsupported metric")
    all_cases = await cases.list_all()
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    points: list[MetricPoint] = []
    for offset in range(days - 1, -1, -1):
        bucket = today - timedelta(days=offset)
        bucket_cases = [case for case in all_cases if case.created_at.date() == bucket.date()]
        if metric == "volume":
            value = float(len(bucket_cases))
        elif metric == "avg_readiness":
            value = sum(case.readiness_score for case in bucket_cases) / len(bucket_cases) if bucket_cases else 0.0
        elif metric == "late_rate":
            value = sum(bool(case.due_at and case.due_at < datetime.now(timezone.utc) and case.status not in {"done", "rejected"}) for case in bucket_cases) / len(bucket_cases) if bucket_cases else 0.0
        else:
            value = sum(any(item.status in {"missing", "uncertain"} for item in case.checklist) for case in bucket_cases) / len(bucket_cases) if bucket_cases else 0.0
        points.append(MetricPoint(metric=metric, value=value, bucket_start=bucket))
    return points


@router.get("/anomalies", response_model=list[AnomalyAlert])
async def anomalies(days: int = Query(default=7, ge=1, le=90)) -> list[AnomalyAlert]:
    # No scheduled historical metric store exists in local P0. Returning an
    # explicit empty list is truthful and keeps clients stable.
    return []
