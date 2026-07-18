import pytest
from pydantic import ValidationError

from src.models.application_management import (
    ApplicationDecisionRequest,
    ApplicationStatus,
    project_application_status,
)


def test_legacy_status_projects_to_canonical_officer_status():
    assert project_application_status("awaiting_officer_review", has_caution=True) == ApplicationStatus.CAUTION_REVIEW_REQUIRED
    assert project_application_status("awaiting_officer_review", has_caution=False) == ApplicationStatus.READY_FOR_PROCESSING
    assert project_application_status("precheck_ready", has_caution=False) == ApplicationStatus.READY_FOR_PROCESSING
    assert project_application_status("needs_citizen_update", has_caution=True) == ApplicationStatus.RETURNED_TO_CITIZEN
    assert project_application_status("unknown-value", has_caution=False) == ApplicationStatus.UNKNOWN


def test_continue_decision_requires_ten_non_whitespace_characters():
    with pytest.raises(ValidationError):
        ApplicationDecisionRequest(
            decision="CONTINUE_PROCESSING",
            note=" too short ",
            anomaly_ids=[],
            expected_version=1,
            idempotency_key="decision-1",
        )

    request = ApplicationDecisionRequest(
        decision="CONTINUE_PROCESSING",
        note="Đã đối chiếu hồ sơ gốc.",
        anomaly_ids=[],
        expected_version=1,
        idempotency_key="decision-1",
    )
    assert request.note == "Đã đối chiếu hồ sơ gốc."


def test_return_decision_requires_findings_and_message():
    with pytest.raises(ValidationError):
        ApplicationDecisionRequest(
            decision="RETURN_TO_CITIZEN",
            note="",
            anomaly_ids=[],
            citizen_message="",
            expected_version=1,
            idempotency_key="decision-2",
        )

    request = ApplicationDecisionRequest(
        decision="RETURN_TO_CITIZEN",
        note="",
        anomaly_ids=["finding-1"],
        citizen_message=" Vui lòng bổ sung giấy tờ còn thiếu. ",
        expected_version=1,
        idempotency_key="decision-2",
    )
    assert request.citizen_message == "Vui lòng bổ sung giấy tờ còn thiếu."
