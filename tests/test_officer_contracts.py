"""Contract guards for the versioned officer-review workflow."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models import (
    ApplicationCase,
    CaseAuditEvent,
    CaseSubmissionVersion,
    OfficerDecision,
    OfficerIdentity,
    SupplementRequest,
    TokenClaims,
    ValidationFinding,
)

NOW = datetime.now(timezone.utc)


def test_application_case_accepts_canonical_officer_status_and_lock_version():
    case = ApplicationCase(
        id="case-1",
        case_code="UBNDAI-2026-000001",
        organization_id="org-1",
        citizen_id="citizen-1",
        procedure_id="khai_sinh",
        procedure_version_id="procedure-v1",
        status="awaiting_officer_review",
        current_submission_version=2,
        version=4,
        created_at=NOW,
        updated_at=NOW,
    )

    assert case.status == "awaiting_officer_review"
    assert case.current_submission_version == 2
    assert case.version == 4


def test_submission_version_is_frozen_and_requires_positive_version():
    submission = CaseSubmissionVersion(
        id="submission-1",
        case_id="case-1",
        version=1,
        form_data={"full_name": "Nguyen Van A"},
        checklist_snapshot={"birth_certificate": "uploaded"},
        procedure_version_id="procedure-v1",
        procedure_rule_version="ruleset-v3",
        created_at=NOW,
        created_by="citizen-1",
        source="citizen_portal",
    )

    with pytest.raises(ValidationError):
        submission.version = 2

    with pytest.raises(ValidationError):
        CaseSubmissionVersion(
            id="submission-0",
            case_id="case-1",
            version=0,
            procedure_version_id="procedure-v1",
            procedure_rule_version="ruleset-v3",
            created_at=NOW,
            source="citizen_portal",
        )


def test_ai_finding_cannot_have_error_severity():
    with pytest.raises(ValidationError):
        ValidationFinding(
            id="finding-1",
            case_id="case-1",
            submission_version_id="submission-1",
            type="cross_document_conflict",
            severity="error",
            source="ai",
            message="Conflict",
            created_at=NOW,
        )


def test_dismissing_error_finding_requires_non_blank_reason():
    with pytest.raises(ValidationError):
        OfficerDecision(
            id="decision-1",
            finding_id="finding-1",
            officer_id="officer-1",
            decision="dismissed",
            finding_severity="error",
            reason="  ",
            created_at=NOW,
        )

    decision = OfficerDecision(
        id="decision-2",
        finding_id="finding-1",
        officer_id="officer-1",
        decision="dismissed",
        finding_severity="error",
        reason="OCR misread the source document",
        created_at=NOW,
    )
    assert decision.reason == "OCR misread the source document"


def test_officer_decision_and_audit_event_are_append_only_contracts():
    decision = OfficerDecision(
        id="decision-1",
        finding_id="finding-1",
        officer_id="officer-1",
        decision="accepted",
        created_at=NOW,
    )
    event = CaseAuditEvent(
        id="event-1",
        case_id="case-1",
        actor_id="officer-1",
        organization_id="org-1",
        event_type="finding_accepted",
        object_type="validation_finding",
        object_id="finding-1",
        metadata={"reason_code": "SOURCE_CONFIRMED"},
        created_at=NOW,
    )

    with pytest.raises(ValidationError):
        decision.decision = "dismissed"
    with pytest.raises(ValidationError):
        event.event_type = "finding_dismissed"


def test_supplement_request_requires_message_and_finding_link():
    request = SupplementRequest(
        id="supplement-1",
        case_id="case-1",
        submission_version_id="submission-1",
        created_by="officer-1",
        public_message="Please provide the missing document.",
        finding_ids=["finding-1"],
        status="draft",
        created_at=NOW,
    )
    assert request.finding_ids == ["finding-1"]

    with pytest.raises(ValidationError):
        SupplementRequest(
            id="supplement-2",
            case_id="case-1",
            submission_version_id="submission-1",
            created_by="officer-1",
            public_message=" ",
            finding_ids=[],
            status="draft",
            created_at=NOW,
        )


def test_officer_identity_and_token_claims_require_organization_scope():
    identity = OfficerIdentity(
        user_id="officer-1",
        organization_id="org-1",
        roles={"officer_reviewer", "specialist"},
        active=True,
    )
    claims = TokenClaims(
        user_id=identity.user_id,
        organization_id=identity.organization_id,
        roles=identity.roles,
        exp=int(NOW.timestamp()) + 1800,
    )

    assert "officer_reviewer" in claims.roles

    with pytest.raises(ValidationError):
        TokenClaims(
            user_id="officer-1",
            organization_id="",
            roles={"officer_reviewer"},
            exp=int(NOW.timestamp()) + 1800,
        )
