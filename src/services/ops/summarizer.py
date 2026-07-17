"""Grounded deterministic summaries for the local P0 operations view."""

from datetime import datetime, timezone

from src.models import CaseSummary, DailyDigest
from src.services import cases


async def summarize_case(case_id: str) -> CaseSummary:
    case = await cases.get(case_id)
    open_issues = [item.note or item.requirement_code for item in case.checklist if item.status in {"missing", "uncertain"}]
    procedure = case.procedure_id or "chưa xác định thủ tục"
    summary = f"Hồ sơ {procedure}, trạng thái {case.status}, mức sẵn sàng {case.readiness_score:.0%}."
    return CaseSummary(case_id=case.id, summary=summary, open_issues=open_issues, generated_at=datetime.now(timezone.utc))


async def daily_digest(officer_id: str, date: str) -> DailyDigest:
    all_cases = await cases.list_all()
    assigned = [case for case in all_cases if case.assigned_officer_id == officer_id]
    handled = [case for case in assigned if case.status in {"done", "submitted"} and case.updated_at.date().isoformat() == date]
    pending = [case for case in assigned if case.status not in {"done", "rejected"}]
    flagged = [case.id for case in pending if any(item.status == "uncertain" for item in case.checklist)]
    return DailyDigest(
        officer_id=officer_id,
        date=date,
        summary=f"Đã xử lý {len(handled)} hồ sơ; còn {len(pending)} hồ sơ cần theo dõi.",
        handled_count=len(handled),
        pending_count=len(pending),
        flagged_case_ids=flagged,
    )
