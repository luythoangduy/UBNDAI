import pytest
from sqlalchemy import select

from src.services.application_repository import ApplicationRepository, RepositoryConflict
from src.services.persistence import (
    ApplicationCaseDecisionORM,
    ApplicationCaseORM,
    AuditEventORM,
    NotificationEventORM,
    SubmissionVersionORM,
    ValidationFindingORM,
    create_sqlite_database,
)


def test_repository_updates_case_with_optimistic_version():
    db = create_sqlite_database()
    with db.session() as session:
        session.add(ApplicationCaseORM(id="case", case_code="CASE", organization_id="org", citizen_id="citizen", procedure_id="khai_sinh", procedure_version_id="v1"))
        session.commit()
        repository = ApplicationRepository(session)
        updated = repository.update_status("case", "org", "in_officer_review", expected_version=1)
        session.commit()
        assert updated.version == 2
        assert updated.status == "in_officer_review"
        with pytest.raises(RepositoryConflict):
            repository.update_status("case", "org", "done", expected_version=1)


def test_repository_never_returns_cross_organization_case():
    db = create_sqlite_database()
    with db.session() as session:
        session.add(ApplicationCaseORM(id="case", case_code="CASE", organization_id="org-a", citizen_id="citizen", procedure_id="p", procedure_version_id="v1"))
        session.commit()
        assert ApplicationRepository(session).get("case", "org-b") is None


def test_complete_decision_is_atomic_and_idempotent():
    db = create_sqlite_database()
    with db.session() as session:
        session.add_all([
            ApplicationCaseORM(id="case", case_code="CASE", organization_id="org", citizen_id="citizen", procedure_id="p", procedure_version_id="v1", status="in_officer_review"),
            SubmissionVersionORM(id="sv", case_id="case", version=1, procedure_version_id="v1", procedure_rule_version="r1"),
            ValidationFindingORM(id="finding", case_id="case", submission_version_id="sv", type="missing", severity="warning", source="rule", message="Missing"),
        ])
        session.commit()
        repository = ApplicationRepository(session)
        decision = ApplicationCaseDecisionORM(id="decision", case_id="case", submission_version_id="sv", officer_id="officer", decision="RETURN_TO_CITIZEN", note="Return with explanation", selected_finding_ids=["finding"], citizen_message="Please update", previous_status="in_officer_review", new_status="needs_citizen_update", expected_version=1, idempotency_key="idem-key")
        result = repository.record_decision(
            case_id="case", organization_id="org", decision=decision,
            target_status="needs_citizen_update", finding_status="accepted",
            audit=AuditEventORM(id="audit", case_id="case", actor_id="officer", organization_id="org", event_type="supplement_requested", object_type="case", object_id="case"),
            notification=NotificationEventORM(id="notification", case_id="case", recipient_id="citizen", event_type="supplement_requested", payload={"case_id": "case"}),
        )
        session.commit()
        assert result.id == "decision"
        assert session.get(ApplicationCaseORM, "case").version == 2
        assert session.get(ValidationFindingORM, "finding").status == "accepted"
        assert session.scalar(select(NotificationEventORM).where(NotificationEventORM.id == "notification")) is not None

        replay = repository.record_decision(
            case_id="case", organization_id="org", decision=decision,
            target_status="needs_citizen_update", finding_status="accepted",
            audit=AuditEventORM(id="unused-audit", case_id="case", actor_id="officer", organization_id="org", event_type="unused", object_type="case", object_id="case"),
            notification=NotificationEventORM(id="unused-notification", case_id="case", recipient_id="citizen", event_type="unused", payload={}),
        )
        assert replay.id == "decision"
        assert session.get(ApplicationCaseORM, "case").version == 2


def test_complete_decision_rolls_back_all_records_on_stale_version():
    db = create_sqlite_database()
    with db.session() as session:
        session.add_all([
            ApplicationCaseORM(id="case", case_code="CASE", organization_id="org", citizen_id="citizen", procedure_id="p", procedure_version_id="v1", version=2),
            SubmissionVersionORM(id="sv", case_id="case", version=1, procedure_version_id="v1", procedure_rule_version="r1"),
        ])
        session.commit()
        decision = ApplicationCaseDecisionORM(id="decision", case_id="case", submission_version_id="sv", officer_id="officer", decision="CONTINUE_PROCESSING", note="Continue after review", selected_finding_ids=[], previous_status="awaiting_officer_review", new_status="in_officer_review", expected_version=1, idempotency_key="stale-key")
        with pytest.raises(RepositoryConflict):
            ApplicationRepository(session).record_decision(
                case_id="case", organization_id="org", decision=decision,
                target_status="in_officer_review", finding_status="accepted",
                audit=AuditEventORM(id="audit", case_id="case", actor_id="officer", organization_id="org", event_type="continued", object_type="case", object_id="case"),
                notification=NotificationEventORM(id="notification", case_id="case", recipient_id="citizen", event_type="continued", payload={}),
            )
        session.rollback()
        assert session.get(ApplicationCaseDecisionORM, "decision") is None
        assert session.get(AuditEventORM, "audit") is None
        assert session.get(NotificationEventORM, "notification") is None
