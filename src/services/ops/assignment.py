"""Deterministic local-P0 assignment for legacy cases."""

from datetime import datetime, timezone

from src.models import Assignment, CaseUpdate
from src.services import cases


async def auto_assign(case_id: str) -> Assignment:
    case = await cases.get(case_id)
    # The production identity directory/workload allocator is deferred. Keeping
    # this explicit makes the local demo deterministic and explainable.
    officer_id = case.assigned_officer_id or "officer.demo"
    priority = 50 + min(50, sum(item.status == "uncertain" for item in case.checklist) * 10)
    if case.assigned_officer_id != officer_id:
        await cases.update(case_id, CaseUpdate(assigned_officer_id=officer_id))
    return Assignment(
        case_id=case_id,
        officer_id=officer_id,
        assigned_at=datetime.now(timezone.utc),
        reason="local_p0:default_officer;uncertain_items_first",
        priority=priority,
    )
