"""Idempotently add officer application-management demo records.

Run after the database schema/migrations are applied:
    python scripts/seed_application_demo_data.py
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models import ValidationFinding  # noqa: E402
from src.services.officer_store import now, store


def seed_application_demo_data() -> int:
    """Create a small status/anomaly matrix without duplicating existing rows."""
    source = store.cases.get("case-demo-001")
    submission = next((item for item in store.submissions.values() if item.case_id == "case-demo-001"), None)
    if source is None or submission is None:
        raise RuntimeError("The base officer demo case is unavailable")
    timestamp = now()
    records = (
        ("case-demo-ready", "UBNDAI-2026-000101", "precheck_ready", 60, False),
        ("case-demo-processing", "UBNDAI-2026-000102", "in_officer_review", 70, False),
        ("case-demo-returned", "UBNDAI-2026-000103", "needs_citizen_update", 50, True),
    )
    created = 0
    for case_id, case_code, status, priority, has_finding in records:
        if case_id in store.cases:
            continue
        case = source.model_copy(update={
            "id": case_id,
            "case_code": case_code,
            "citizen_id": f"citizen-{case_id}",
            "status": status,
            "priority": priority,
            "created_at": timestamp - timedelta(days=priority // 10),
            "updated_at": timestamp,
            "submitted_at": timestamp - timedelta(days=priority // 10),
            "version": 1,
        })
        case_submission = submission.model_copy(update={
            "id": f"submission-{case_id}",
            "case_id": case_id,
            "created_by": case.citizen_id,
        })
        store.cases[case_id] = case
        store.submissions[case_submission.id] = case_submission
        store._save_case(case)
        store._save_submission(case_submission)
        if has_finding:
            finding = ValidationFinding(
                id=f"finding-{case_id}", case_id=case_id,
                submission_version_id=case_submission.id, type="missing_required_document",
                severity="warning", source="rule", message="Thiếu giấy tờ bắt buộc để tiếp tục xử lý.",
                suggestion="Bổ sung tài liệu còn thiếu.", rule_id="DEMO-R1", rule_version=1,
                confidence=1.0, field_keys=["giay_to_bo_sung"], created_at=timestamp,
            )
            store.findings[finding.id] = finding
            store._save_finding(finding)
        created += 1
    return created


if __name__ == "__main__":
    print(f"Created {seed_application_demo_data()} application demo records")
