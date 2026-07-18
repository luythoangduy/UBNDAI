"""Application use-cases isolated from HTTP and storage details."""

from __future__ import annotations

from uuid import uuid4

from src.models import CaseAuditEvent
from src.services.officer_store import OfficerStore, now, store


class ApplicationNotFound(LookupError):
    pass


class ApplicationConflict(RuntimeError):
    pass


class ApplicationManagementService:
    """Compatibility facade; OfficerStore may later delegate to SQL repositories."""

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
        case.organization_id = organization_id
        case.updated_at = now()
        self.store._save_case(case)
        self._event(case, actor_id, "application.created")
        return case

    def assign(self, application_id: str, organization_id: str, actor_id: str, assigned_to: str | None, expected_version: int):
        case = self.get(application_id, organization_id)
        if case.version != expected_version:
            raise ApplicationConflict("Application version has changed")
        case.assigned_to = assigned_to
        case.assigned_at = now() if assigned_to else None
        case.version += 1
        case.updated_at = now()
        self.store._save_case(case)
        self._event(case, actor_id, "application.assigned", {"assigned_to": assigned_to})
        return case

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
        case = self.get(application_id, organization_id)
        if case.version != expected_version:
            raise ApplicationConflict("Application version has changed")
        if case.status != "needs_citizen_update":
            raise ApplicationConflict("Only returned applications can be resubmitted")
        case.form_data = {**case.form_data, **form_data}
        case.current_submission_version += 1
        case.status = "resubmitted"
        case.version += 1
        case.updated_at = now()
        self.store._save_case(case)
        self._event(case, actor_id, "application.resubmitted", {"submission_version": case.current_submission_version})
        return case


application_management_service = ApplicationManagementService()
