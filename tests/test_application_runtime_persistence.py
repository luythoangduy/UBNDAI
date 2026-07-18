from sqlalchemy import func, select

from src.services.application_management_service import ApplicationManagementService
from src.services.officer_store import OfficerStore
from src.services.persistence import (
    ApplicationCaseDecisionORM,
    ApplicationCaseORM,
    AuditEventORM,
    NotificationEventORM,
    SubmissionVersionORM,
    SupplementRequestORM,
    ValidationFindingORM,
    create_sqlite_database,
)


def _persistent_store(*, status: str = "awaiting_officer_review"):
    database = create_sqlite_database()
    with database.session() as session:
        session.add_all(
            [
                ApplicationCaseORM(
                    id="case",
                    case_code="CASE-001",
                    organization_id="org",
                    citizen_id="citizen",
                    procedure_id="khai_sinh",
                    procedure_version_id="v1",
                    status=status,
                ),
                SubmissionVersionORM(
                    id="submission-1",
                    case_id="case",
                    version=1,
                    procedure_version_id="v1",
                    procedure_rule_version="rules-v1",
                ),
                ValidationFindingORM(
                    id="finding",
                    case_id="case",
                    submission_version_id="submission-1",
                    type="missing_document",
                    severity="warning",
                    source="rule",
                    message="Missing document",
                ),
            ]
        )
        session.commit()
    return database, OfficerStore(database=database, seed=False)


def test_persistent_store_reads_database_as_source_of_truth():
    database, runtime_store = _persistent_store()

    with database.session() as session:
        row = session.get(ApplicationCaseORM, "case")
        row.priority = 91
        session.commit()

    assert runtime_store.get_case("case", "org").priority == 91
    assert runtime_store.list_cases("org")[0].priority == 91
    assert runtime_store.findings_for("case", "org")[0].id == "finding"


def test_list_cases_returns_every_case_not_just_first_page():
    # Regression: list_cases() used to call ApplicationRepository.list() with its
    # default page_size=20, so any org above that size silently lost cases 21+
    # from the officer queue and undercounted the dashboard summary.
    database = create_sqlite_database()
    with database.session() as session:
        session.add_all(
            [
                ApplicationCaseORM(
                    id=f"case-{i}",
                    case_code=f"CASE-{i:03d}",
                    organization_id="org",
                    citizen_id="citizen",
                    procedure_id="khai_sinh",
                    procedure_version_id="v1",
                    status="awaiting_officer_review",
                )
                for i in range(25)
            ]
        )
        session.commit()
    runtime_store = OfficerStore(database=database, seed=False)

    cases = runtime_store.list_cases("org")

    assert len(cases) == 25


def test_guidance_case_is_persisted_before_its_audit_event():
    database = create_sqlite_database()
    runtime_store = OfficerStore(database=database, seed=False)

    case = runtime_store.ensure_guidance_case("guidance-case", "citizen")

    with database.session() as session:
        assert session.get(ApplicationCaseORM, case.id) is not None
        audit = session.scalar(
            select(AuditEventORM).where(AuditEventORM.case_id == case.id)
        )
        assert audit is not None
        assert audit.event_type == "case_created_from_guidance"


def test_assignment_and_resubmit_are_durable_transactions():
    database, runtime_store = _persistent_store(status="needs_citizen_update")
    service = ApplicationManagementService(runtime_store)

    assigned = service.assign("case", "org", "supervisor", "officer", expected_version=1)
    resubmitted = service.resubmit(
        "case",
        "org",
        "citizen",
        expected_version=2,
        form_data={"full_name": "Nguyen Van A"},
    )

    with database.session() as session:
        persisted = session.get(ApplicationCaseORM, "case")
        assert assigned.assigned_to == "officer"
        assert persisted.assigned_to == "officer"
        assert resubmitted.version == 3
        assert persisted.status == "resubmitted"
        assert persisted.form_data["full_name"] == "Nguyen Van A"
        assert session.scalar(
            select(func.count()).select_from(SubmissionVersionORM).where(SubmissionVersionORM.case_id == "case")
        ) == 2


def test_runtime_decision_is_atomic_durable_and_idempotent():
    database, runtime_store = _persistent_store()
    service = ApplicationManagementService(runtime_store)

    first, replayed = service.decide(
        "case",
        "org",
        "officer",
        decision="RETURN_TO_CITIZEN",
        note="Return after reviewing the evidence",
        anomaly_ids=["finding"],
        citizen_message="Please provide the missing document.",
        expected_version=1,
        idempotency_key="decision-key-001",
    )
    second, second_replayed = service.decide(
        "case",
        "org",
        "officer",
        decision="RETURN_TO_CITIZEN",
        note="Return after reviewing the evidence",
        anomaly_ids=["finding"],
        citizen_message="Please provide the missing document.",
        expected_version=1,
        idempotency_key="decision-key-001",
    )

    assert replayed is False
    assert second_replayed is True
    assert (first.id, first.status, first.version) == (second.id, second.status, second.version)
    with database.session() as session:
        assert session.get(ApplicationCaseORM, "case").status == "needs_citizen_update"
        assert session.get(ValidationFindingORM, "finding").status == "accepted"
        assert session.scalar(select(func.count()).select_from(ApplicationCaseDecisionORM)) == 1
        assert session.scalar(select(func.count()).select_from(SupplementRequestORM)) == 1
        assert session.scalar(select(func.count()).select_from(AuditEventORM)) == 1
        assert session.scalar(select(func.count()).select_from(NotificationEventORM)) == 1
