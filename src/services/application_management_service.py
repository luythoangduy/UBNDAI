"""Application use-cases isolated from HTTP and storage details."""

from __future__ import annotations

from uuid import uuid4

from src.models import CaseAuditEvent, CaseSubmissionVersion
from src.services.application_repository import ApplicationRepository, RepositoryConflict, RepositoryNotFound
from src.services.application_state_machine import InvalidApplicationTransition, require_transition
from src.services.officer_store import OfficerStore, now, store
from src.services.persistence import (
    ApplicationCaseDecisionORM,
    AuditEventORM,
    FindingDecisionORM,
    NotificationEventORM,
    SubmissionVersionORM,
    SupplementRequestORM,
)


class ApplicationNotFound(LookupError):
    pass


class ApplicationConflict(RuntimeError):
    pass


class ApplicationManagementService:
    """Application use cases with a durable repository and memory fallback."""

    def __init__(self, backing_store: OfficerStore = store):
        self.store = backing_store

    def get(self, application_id: str, organization_id: str):
        case = self.store.get_case(application_id, organization_id)
        if case is None:
            raise ApplicationNotFound(application_id)
        return case

    def _event(self, case, actor_id: str, event_type: str, metadata: dict | None = None):
        event = CaseAuditEvent(id=f"event-{uuid4().hex}", case_id=case.id, actor_id=actor_id,
            organization_id=case.organization_id, event_type=event_type, object_type="application",
            object_id=case.id, metadata=metadata or {}, created_at=now())
        self.store.audit.append(event)
        self.store._save_audit(event)
        return event

    def create(self, organization_id: str, actor_id: str, citizen_id: str, procedure_id: str, locality_code: str):
        case = self.store.create_citizen_case(citizen_id, procedure_id, locality_code)
        updated = case.model_copy(update={"organization_id": organization_id, "updated_at": now()})
        self.store.cases[updated.id] = updated
        self.store._save_case(updated)
        self._event(updated, actor_id, "application.created")
        return updated

    def assign(self, application_id: str, organization_id: str, actor_id: str, assigned_to: str | None, expected_version: int):
        if self.store._db:
            with self.store._db.session() as session:
                repository = ApplicationRepository(session)
                row = repository.get(application_id, organization_id, for_update=True)
                if row is None:
                    raise ApplicationNotFound(application_id)
                if row.version != expected_version:
                    raise ApplicationConflict("Application version has changed")
                row.assigned_to = assigned_to
                row.assigned_at = now() if assigned_to else None
                row.version += 1
                row.updated_at = now()
                session.add(AuditEventORM(
                    id=f"event-{uuid4().hex}", case_id=row.id, actor_id=actor_id,
                    organization_id=organization_id, event_type="application.assigned",
                    object_type="application", object_id=row.id,
                    metadata_={"assigned_to": assigned_to}, created_at=now(),
                ))
                session.commit()
                case = self.store._case_model(row)
                self.store.cases[case.id] = case
                return case
        case = self.get(application_id, organization_id)
        if case.version != expected_version:
            raise ApplicationConflict("Application version has changed")
        updated = case.model_copy(update={
            "assigned_to": assigned_to,
            "assigned_at": now() if assigned_to else None,
            "version": case.version + 1,
            "updated_at": now(),
        })
        self.store.cases[updated.id] = updated
        self.store._save_case(updated)
        self._event(updated, actor_id, "application.assigned", {"assigned_to": assigned_to})
        return updated

    def register_document(self, application_id: str, organization_id: str, actor_id: str, filename: str, content_type: str, size_bytes: int):
        case = self.get(application_id, organization_id)
        document = self.store.create_document(case.id, case.citizen_id, filename, content_type, size_bytes)
        self._event(case, actor_id, "document.registered", {"document_id": document.id})
        return document

    def analyze(self, application_id: str, organization_id: str, actor_id: str):
        case = self.get(application_id, organization_id)
        if case.status not in {"submitted_for_precheck", "resubmitted", "awaiting_officer_review"}:
            raise ApplicationConflict("Application cannot be analyzed in its current state")
        findings = self.store.rerun_validation(case.id, organization_id, actor_id)
        self._event(case, actor_id, "application.analysis_requested", {"submission_version": case.current_submission_version})
        return findings

    def resubmit(self, application_id: str, organization_id: str, actor_id: str, expected_version: int, form_data: dict):
        if self.store._db:
            with self.store._db.session() as session:
                repository = ApplicationRepository(session)
                row = repository.get(application_id, organization_id, for_update=True)
                if row is None:
                    raise ApplicationNotFound(application_id)
                if row.version != expected_version:
                    raise ApplicationConflict("Application version has changed")
                if row.status != "needs_citizen_update":
                    raise ApplicationConflict("Only returned applications can be resubmitted")
                submission_number = row.current_submission_version + 1
                submission = SubmissionVersionORM(
                    id=f"submission-{uuid4().hex}", case_id=row.id, version=submission_number,
                    form_data={**(row.form_data or {}), **form_data}, checklist_snapshot=row.checklist or {},
                    procedure_version_id=row.procedure_version_id, procedure_rule_version="rules-v1",
                    created_at=now(), created_by=actor_id, source="citizen_portal",
                )
                row.form_data = submission.form_data
                row.current_submission_version = submission_number
                row.status = "resubmitted"
                row.version += 1
                row.updated_at = now()
                session.add_all([submission, AuditEventORM(
                    id=f"event-{uuid4().hex}", case_id=row.id, actor_id=actor_id,
                    organization_id=organization_id, event_type="application.resubmitted",
                    object_type="application", object_id=row.id,
                    metadata_={"submission_version": submission_number}, created_at=now(),
                )])
                session.commit()
                case = self.store._case_model(row)
                self.store.cases[case.id] = case
                self.store.submissions[submission.id] = CaseSubmissionVersion(
                    id=submission.id, case_id=submission.case_id, version=submission.version,
                    form_data=submission.form_data, checklist_snapshot=submission.checklist_snapshot,
                    procedure_version_id=submission.procedure_version_id,
                    procedure_rule_version=submission.procedure_rule_version,
                    created_at=submission.created_at, created_by=submission.created_by, source=submission.source,
                )
                return case
        case = self.get(application_id, organization_id)
        if case.version != expected_version:
            raise ApplicationConflict("Application version has changed")
        if case.status != "needs_citizen_update":
            raise ApplicationConflict("Only returned applications can be resubmitted")
        timestamp = now()
        updated = case.model_copy(update={
            "form_data": {**case.form_data, **form_data},
            "current_submission_version": case.current_submission_version + 1,
            "status": "resubmitted",
            "version": case.version + 1,
            "updated_at": timestamp,
        })
        submission = CaseSubmissionVersion(
            id=f"submission-{uuid4().hex}", case_id=case.id,
            version=updated.current_submission_version, form_data=updated.form_data,
            checklist_snapshot=updated.checklist, procedure_version_id=updated.procedure_version_id,
            procedure_rule_version="rules-v1", created_at=timestamp, created_by=actor_id,
        )
        self.store.cases[updated.id] = updated
        self.store.submissions[submission.id] = submission
        self.store._save_submission(submission)
        self.store._save_case(updated)
        self._event(updated, actor_id, "application.resubmitted", {"submission_version": updated.current_submission_version})
        return updated

    def decide(
        self,
        application_id: str,
        organization_id: str,
        actor_id: str,
        *,
        decision: str,
        note: str,
        anomaly_ids: list[str],
        citizen_message: str | None,
        expected_version: int,
        idempotency_key: str,
    ):
        """Apply a decision atomically when SQL persistence is enabled."""
        target = "in_officer_review" if decision == "CONTINUE_PROCESSING" else "needs_citizen_update"
        if self.store._db:
            with self.store._db.session() as session:
                repository = ApplicationRepository(session)
                existing = repository.decision_by_idempotency(application_id, idempotency_key)
                if existing is not None:
                    if existing.decision != decision or existing.note != note:
                        raise ApplicationConflict("Idempotency key was already used with another decision")
                    row = repository.get(application_id, organization_id)
                    if row is None:
                        raise ApplicationNotFound(application_id)
                    return self.store._case_model(row), True
                row = repository.get(application_id, organization_id, for_update=True)
                if row is None:
                    raise ApplicationNotFound(application_id)
                try:
                    require_transition(row.status, target)
                except InvalidApplicationTransition as exc:
                    raise ApplicationConflict(str(exc)) from exc
                submission = session.query(SubmissionVersionORM).filter(
                    SubmissionVersionORM.case_id == application_id,
                    SubmissionVersionORM.version == row.current_submission_version,
                ).one_or_none()
                if submission is None:
                    raise ApplicationConflict("Current submission version is missing")
                timestamp = now()
                decision_id = f"decision-{uuid4().hex}"
                decision_row = ApplicationCaseDecisionORM(
                    id=decision_id, case_id=application_id, submission_version_id=submission.id,
                    officer_id=actor_id, decision=decision, note=note,
                    selected_finding_ids=anomaly_ids, citizen_message=citizen_message,
                    previous_status=row.status, new_status=target, expected_version=expected_version,
                    idempotency_key=idempotency_key, created_at=timestamp,
                )
                finding_decisions = [FindingDecisionORM(
                    id=f"finding-decision-{uuid4().hex}", finding_id=finding_id,
                    case_id=application_id, officer_id=actor_id, decision="accepted",
                    reason=note or citizen_message, created_at=timestamp,
                ) for finding_id in anomaly_ids]
                supplement = None
                if decision == "RETURN_TO_CITIZEN":
                    supplement = SupplementRequestORM(
                        id=f"supplement-{uuid4().hex}", case_id=application_id,
                        submission_version_id=submission.id, created_by=actor_id,
                        public_message=citizen_message or "", finding_ids=anomaly_ids,
                        status="sent", created_at=timestamp,
                    )
                try:
                    repository.record_decision(
                        case_id=application_id,
                        organization_id=organization_id,
                        decision=decision_row,
                        target_status=target,
                        finding_status="accepted",
                        audit=AuditEventORM(
                            id=f"event-{uuid4().hex}", case_id=application_id, actor_id=actor_id,
                            organization_id=organization_id, event_type="application.decision_recorded",
                            object_type="application", object_id=application_id,
                            metadata_={"decision": decision, "submission_version": submission.version},
                            created_at=timestamp,
                        ),
                        notification=NotificationEventORM(
                            id=f"notification-{uuid4().hex}", case_id=application_id,
                            recipient_id=row.citizen_id, event_type="application.decision_recorded",
                            payload={"application_id": application_id, "decision": decision},
                            created_at=timestamp,
                        ),
                        finding_decisions=finding_decisions,
                        supplement=supplement,
                    )
                    session.commit()
                    session.refresh(row)
                except (RepositoryConflict, RepositoryNotFound) as exc:
                    session.rollback()
                    raise ApplicationConflict(str(exc)) from exc
                case = self.store._case_model(row)
                self.store.cases[case.id] = case
                return case, False

        key = (application_id, idempotency_key)
        existing = self.store.idempotency_results.get(key)
        if existing is not None:
            if existing["decision"] != decision or existing["note"] != note:
                raise ApplicationConflict("Idempotency key was already used with another decision")
            return self.get(application_id, organization_id), True
        case = self.get(application_id, organization_id)
        if case.version != expected_version:
            raise ApplicationConflict("Application version has changed")
        try:
            require_transition(case.status, target)
            updated = self.store.transition(application_id, organization_id, actor_id, target, note or citizen_message)
        except (InvalidApplicationTransition, ValueError) as exc:
            raise ApplicationConflict(str(exc)) from exc
        if updated is None:
            raise ApplicationNotFound(application_id)
        self.store.idempotency_results[key] = {"decision": decision, "note": note}
        return updated, False


application_management_service = ApplicationManagementService()
