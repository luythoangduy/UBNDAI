"""Dashboard & vận hành cho cán bộ. Owner: Dev C. Yêu cầu role officer/manager."""

from fastapi import APIRouter

from src.models import AnomalyAlert, Assignment, Case, CaseSummary, DailyDigest, MetricPoint

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/queue", response_model=list[Case])
async def my_queue(officer_id: str) -> list[Case]:
    """Hồ sơ được phân công, sắp theo priority (uncertain lên đầu)."""
    raise NotImplementedError  # TODO(C)


@router.post("/assign", response_model=Assignment)
async def auto_assign(case_id: str) -> Assignment:
    raise NotImplementedError  # TODO(C): services.ops.assignment


@router.get("/cases/{case_id}/summary", response_model=CaseSummary)
async def case_summary(case_id: str) -> CaseSummary:
    raise NotImplementedError  # TODO(C): services.ops.summarizer


@router.get("/digest", response_model=DailyDigest)
async def daily_digest(officer_id: str, date: str) -> DailyDigest:
    raise NotImplementedError  # TODO(C)


@router.get("/metrics", response_model=list[MetricPoint])
async def metrics(metric: str, days: int = 14) -> list[MetricPoint]:
    raise NotImplementedError  # TODO(C)


@router.get("/anomalies", response_model=list[AnomalyAlert])
async def anomalies(days: int = 7) -> list[AnomalyAlert]:
    raise NotImplementedError  # TODO(C): services.ops.anomaly
