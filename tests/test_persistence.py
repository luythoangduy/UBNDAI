from sqlalchemy import select

from src.services.persistence import (
    ApplicationCaseORM,
    AuditEventORM,
    BackgroundJobORM,
    CaseDocumentORM,
    CaseRepository,
    ConsentRecordORM,
    NotificationEventORM,
    RoutingDecisionORM,
    SubmissionVersionORM,
    create_sqlite_database,
)


def test_sqlite_schema_and_case_repository():
    db = create_sqlite_database()
    with db.session() as session:
        case = ApplicationCaseORM(
            id="case-1",
            case_code="UBNDAI-0001",
            organization_id="org-1",
            citizen_id="citizen-1",
            procedure_id="khai_sinh",
            procedure_version_id="v1",
        )
        CaseRepository(session).add(case)
        session.commit()
        loaded = CaseRepository(session).get("case-1")
        assert loaded is not None
        assert loaded.status == "draft"


def test_versioned_related_records_and_json_columns():
    db = create_sqlite_database()
    with db.session() as session:
        session.add_all(
            [
                ApplicationCaseORM(id="c", case_code="C", organization_id="o", citizen_id="u", procedure_id="p", procedure_version_id="pv"),
                SubmissionVersionORM(id="sv", case_id="c", version=1, form_data={"name": "A"}, checklist_snapshot={"x": "ok"}, procedure_version_id="pv", procedure_rule_version="r1", created_by="u"),
                CaseDocumentORM(id="d", case_id="c", submission_version_id="sv", document_type="cccd", object_key="private/c/d", original_filename="id.pdf", content_type="application/pdf", size_bytes=10, sha256="a" * 64),
                AuditEventORM(id="a", case_id="c", actor_id="u", organization_id="o", event_type="created", object_type="case", object_id="c", metadata_={"source": "test"}),
                RoutingDecisionORM(id="rd", case_id="c", submission_version_id="sv", procedure_id="p", procedure_version_id="pv", locality_code="01", organization_id="o", matched_rule="r"),
                ConsentRecordORM(id="co", case_id="c", submission_version_id="sv", citizen_id="u", consent_version="2026-01", accepted=True),
                BackgroundJobORM(id="j", job_type="ocr", payload={"document_id": "d"}),
                NotificationEventORM(id="n", case_id="c", recipient_id="u", event_type="status_changed", payload={"status": "submitted"}),
            ]
        )
        session.commit()
        assert session.scalar(select(SubmissionVersionORM).where(SubmissionVersionORM.id == "sv")).form_data["name"] == "A"


def test_case_repository_organization_scope():
    db = create_sqlite_database()
    with db.session() as session:
        session.add_all([
            ApplicationCaseORM(id="a", case_code="A", organization_id="org-a", citizen_id="u", procedure_id="p", procedure_version_id="v"),
            ApplicationCaseORM(id="b", case_code="B", organization_id="org-b", citizen_id="u", procedure_id="p", procedure_version_id="v"),
        ])
        session.commit()
        assert [c.id for c in CaseRepository(session).list_for_organization("org-a")] == ["a"]
