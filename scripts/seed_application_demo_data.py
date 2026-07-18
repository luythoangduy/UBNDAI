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
from src.services.storage import storage  # noqa: E402


def seed_application_demo_data() -> int:
    """Create a small status/anomaly matrix without duplicating existing rows."""
    source = store.cases.get("case-demo-001")
    submission = next((item for item in store.submissions.values() if item.case_id == "case-demo-001"), None)
    source_document = next((item for item in store.documents.values() if item.case_id == "case-demo-001"), None)
    if source is None or submission is None or source_document is None:
        raise RuntimeError("The base officer demo case is unavailable")
    source_fields = [item for item in store.extracted_fields.values() if item.document_id == source_document.id]
    if not source_fields:
        raise RuntimeError("The base officer demo OCR fields are unavailable")
    demo_asset = Path(__file__).resolve().parents[1] / "data" / "demo" / "giay_chung_sinh_demo.svg"
    demo_content = demo_asset.read_bytes()
    timestamp = now()
    records = (
        ("case-demo-ready", "UBNDAI-2026-000101", "precheck_ready", 60, False),
        ("case-demo-processing", "UBNDAI-2026-000102", "in_officer_review", 70, False),
        ("case-demo-returned", "UBNDAI-2026-000103", "needs_citizen_update", 50, True),
    )
    created = 0
    for case_id, case_code, status, priority, has_finding in records:
        case = store.cases.get(case_id)
        if case is None:
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
            store.cases[case_id] = case
            store._save_case(case)
            created += 1

        case_submission = next((item for item in store.submissions.values() if item.case_id == case_id), None)
        if case_submission is None:
            case_submission = submission.model_copy(update={
                "id": f"submission-{case_id}",
                "case_id": case_id,
                "created_by": case.citizen_id,
            })
            store.submissions[case_submission.id] = case_submission
            store._save_submission(case_submission)

        document = next((item for item in store.documents.values() if item.case_id == case_id), None)
        if document is None:
            object_key = f"demo/{case_id}/giay-chung-sinh.svg"
            storage.put(object_key, demo_content)
            document = source_document.model_copy(update={
                "id": f"document-{case_id}",
                "case_id": case_id,
                "submission_version_id": case_submission.id,
                "file_uri": f"private://{object_key}",
                "object_key": object_key,
                "uploaded_at": case.submitted_at or case.created_at,
            })
            store.documents[document.id] = document
            store._save_document(document)

        for source_field in source_fields:
            field_id = f"field-{case_id}-{source_field.field_key}"
            if field_id in store.extracted_fields:
                continue
            field = source_field.model_copy(update={"id": field_id, "document_id": document.id})
            store.extracted_fields[field.id] = field
            store._save_field(field)

        finding_id = f"finding-{case_id}"
        if has_finding and finding_id not in store.findings:
            finding = ValidationFinding(
                id=finding_id, case_id=case_id,
                submission_version_id=case_submission.id, type="missing_required_document",
                severity="warning", source="rule", message="Thiếu giấy tờ bắt buộc để tiếp tục xử lý.",
                suggestion="Bổ sung tài liệu còn thiếu.", rule_id="DEMO-R1", rule_version=1,
                confidence=1.0, field_keys=["giay_to_bo_sung"], created_at=timestamp,
            )
            store.findings[finding.id] = finding
            store._save_finding(finding)
    return created


if __name__ == "__main__":
    print(f"Created {seed_application_demo_data()} application demo records")
