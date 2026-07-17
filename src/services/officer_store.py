"""Repository-like in-memory officer workflow store for local P0/demo."""

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from src.models import (
    ApplicationCase,
    CaseAuditEvent,
    CaseDocument,
    CaseSubmissionVersion,
    ConsentRecord,
    OfficerDecision,
    RoutingDecision,
    SupplementRequest,
    ValidationFinding,
)
from src.config import settings
from src.services.persistence import ApplicationCaseORM, AuditEventORM, CaseDocumentORM, Database, SubmissionVersionORM


def now() -> datetime:
    return datetime.now(timezone.utc)


class OfficerStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self.cases: dict[str, ApplicationCase] = {}
        self.findings: dict[str, ValidationFinding] = {}
        self.submissions: dict[str, CaseSubmissionVersion] = {}
        self.decisions: list[OfficerDecision] = []
        self.audit: list[CaseAuditEvent] = []
        self.supplements: list[SupplementRequest] = []
        self.documents: dict[str, CaseDocument] = {}
        self.routing_decisions: dict[str, RoutingDecision] = {}
        self.consents: list[ConsentRecord] = []
        self.idempotency_results: dict[tuple[str, str], dict] = {}
        self._db = Database(settings.database_url) if settings.persistence_enabled else None
        if self._db:
            self._db.create_schema()
            self._load_persisted_cases()
        self._seed()

    def _load_persisted_cases(self) -> None:
        if not self._db:
            return
        with self._db.session() as session:
            for row in session.query(ApplicationCaseORM).all():
                self.cases[row.id] = ApplicationCase(id=row.id, case_code=row.case_code, organization_id=row.organization_id, citizen_id=row.citizen_id, procedure_id=row.procedure_id, procedure_version_id=row.procedure_version_id, status=row.status, source_channel=row.source_channel, assigned_to=row.assigned_to, assigned_at=row.assigned_at, priority=row.priority, submitted_at=row.submitted_at, sla_due_at=row.sla_due_at, current_submission_version=row.current_submission_version, version=row.version, form_data=row.form_data or {}, checklist=row.checklist or {}, created_at=row.created_at, updated_at=row.updated_at)

    def _save_case(self, case: ApplicationCase) -> None:
        if not self._db:
            return
        with self._db.session() as session:
            row = session.get(ApplicationCaseORM, case.id)
            if row is None:
                row = ApplicationCaseORM(id=case.id, case_code=case.case_code, organization_id=case.organization_id, citizen_id=case.citizen_id, procedure_id=case.procedure_id or "", procedure_version_id=case.procedure_version_id)
            for key, value in {"case_code": case.case_code, "organization_id": case.organization_id, "citizen_id": case.citizen_id, "procedure_id": case.procedure_id or "", "procedure_version_id": case.procedure_version_id, "status": case.status, "source_channel": case.source_channel, "assigned_to": case.assigned_to, "assigned_at": case.assigned_at, "priority": case.priority, "submitted_at": case.submitted_at, "sla_due_at": case.sla_due_at, "current_submission_version": case.current_submission_version, "version": case.version, "form_data": case.form_data, "checklist": case.checklist, "created_at": case.created_at, "updated_at": case.updated_at}.items():
                setattr(row, key, value)
            session.add(row)
            session.commit()

    def _save_submission(self, submission: CaseSubmissionVersion) -> None:
        if not self._db:
            return
        with self._db.session() as session:
            session.merge(SubmissionVersionORM(id=submission.id, case_id=submission.case_id, version=submission.version, form_data=submission.form_data, checklist_snapshot=submission.checklist_snapshot, procedure_version_id=submission.procedure_version_id, procedure_rule_version=submission.procedure_rule_version, created_at=submission.created_at, created_by=submission.created_by, source=submission.source))
            session.commit()

    def _save_document(self, document: CaseDocument) -> None:
        if not self._db:
            return
        with self._db.session() as session:
            session.merge(CaseDocumentORM(id=document.id, case_id=document.case_id, submission_version_id=document.submission_version_id, document_type=document.document_type, object_key=document.object_key or "", original_filename=document.original_filename or "document", content_type=document.content_type or "application/octet-stream", size_bytes=document.size_bytes or 0, sha256=document.sha256 or ("0" * 64), status=document.ocr_status, ocr_status=document.ocr_status, ocr_engine=document.ocr_engine, ocr_version=document.ocr_version, uploaded_at=document.uploaded_at, extracted_fields={}))
            session.commit()

    def _save_audit(self, event: CaseAuditEvent) -> None:
        if not self._db:
            return
        with self._db.session() as session:
            session.merge(AuditEventORM(id=event.id, case_id=event.case_id, actor_id=event.actor_id, organization_id=event.organization_id, event_type=event.event_type, object_type=event.object_type, object_id=event.object_id, metadata_=event.metadata, created_at=event.created_at))
            session.commit()

    def _seed(self) -> None:
        if self._db and self.cases:
            return
        timestamp = now()
        case = ApplicationCase(id="case-demo-001", case_code="UBNDAI-2026-000001", organization_id="org-demo", citizen_id="citizen-demo", procedure_id="khai_sinh", procedure_version_id="khai-sinh-v1", status="awaiting_officer_review", source_channel="citizen_portal", priority=80, created_at=timestamp, updated_at=timestamp)
        other = case.model_copy(update={"id": "case-other-001", "case_code": "UBNDAI-2026-000002", "organization_id": "org-other"})
        self.cases[case.id] = case
        self.cases[other.id] = other
        submission = CaseSubmissionVersion(id="submission-demo-001", case_id=case.id, version=1, form_data={"applicant_full_name": "Nguyen Van A"}, checklist_snapshot={"birth_certificate": "uploaded"}, procedure_version_id=case.procedure_version_id, procedure_rule_version="ruleset-v1", created_at=timestamp, created_by=case.citizen_id)
        self.submissions[submission.id] = submission
        self._save_case(case)
        self._save_case(other)
        self._save_submission(submission)
        finding = ValidationFinding(id="finding-demo-001", case_id=case.id, submission_version_id=submission.id, type="missing_required_document", severity="error", source="rule", message="Thiếu giấy tờ bắt buộc trong checklist.", suggestion="Bổ sung giấy tờ còn thiếu.", rule_id="khai_sinh.required_document", rule_version=1, confidence=1.0, field_keys=["birth_certificate"], created_at=timestamp)
        self.findings[finding.id] = finding

    def list_cases(self, organization_id: str) -> list[ApplicationCase]:
        with self._lock:
            return [deepcopy(c) for c in self.cases.values() if c.organization_id == organization_id]

    def create_citizen_case(self, citizen_id: str, procedure_id: str, locality_code: str) -> ApplicationCase:
        timestamp = now()
        case_id = str(uuid4())
        case = ApplicationCase(
            id=case_id,
            case_code=f"UBNDAI-{timestamp.year}-{case_id[:8].upper()}",
            organization_id="pending-routing",
            citizen_id=citizen_id,
            procedure_id=procedure_id,
            procedure_version_id=f"{procedure_id}-v1",
            status="collecting",
            source_channel="citizen_portal",
            form_data={"locality_code": locality_code},
            created_at=timestamp,
            updated_at=timestamp,
        )
        with self._lock:
            self.cases[case.id] = case
            self._audit(case, citizen_id, "case_created", "application_case", case.id)
            self._save_case(case)
        return deepcopy(case)

    def list_citizen_cases(self, citizen_id: str) -> list[ApplicationCase]:
        with self._lock:
            return [deepcopy(case) for case in self.cases.values() if case.citizen_id == citizen_id]

    def get_citizen_case(self, case_id: str, citizen_id: str) -> ApplicationCase | None:
        with self._lock:
            case = self.cases.get(case_id)
            return deepcopy(case) if case and case.citizen_id == citizen_id else None

    def update_citizen_case(self, case_id: str, citizen_id: str, expected_version: int, answers: dict | None, form_data: dict | None) -> ApplicationCase:
        with self._lock:
            case = self.cases.get(case_id)
            if case is None or case.citizen_id != citizen_id:
                raise KeyError("case_not_found")
            if case.status not in {"draft", "collecting", "needs_citizen_update"}:
                raise ValueError("case_not_editable")
            if case.version != expected_version:
                raise ValueError("version_conflict")
            merged_answers = {**case.answers, **(answers or {})}
            merged_form_data = {**case.form_data, **(form_data or {})}
            updated = case.model_copy(update={"answers": merged_answers, "form_data": merged_form_data, "version": case.version + 1, "updated_at": now()})
            self.cases[case_id] = updated
            self._audit(updated, citizen_id, "case_updated", "application_case", case_id)
            self._save_case(updated)
            return deepcopy(updated)

    def create_document(self, case_id: str, citizen_id: str, filename: str, content_type: str, size_bytes: int) -> CaseDocument:
        case = self.get_citizen_case(case_id, citizen_id)
        if case is None:
            raise KeyError("case_not_found")
        with self._lock:
            if sum(document.case_id == case_id for document in self.documents.values()) >= 10:
                raise ValueError("document_limit_reached")
            document_id = str(uuid4())
            document = CaseDocument(
                id=document_id,
                case_id=case_id,
                submission_version_id=f"draft:{case_id}",
                document_type="unknown",
                file_uri="private://pending",
                object_key=f"{case_id}/{document_id}",
                original_filename=filename,
                content_type=content_type,
                size_bytes=size_bytes,
                ocr_status="upload_pending",
                uploaded_at=now(),
            )
            self.documents[document.id] = document
            self._save_document(document)
            return deepcopy(document)

    def get_citizen_document(self, document_id: str, citizen_id: str) -> CaseDocument | None:
        with self._lock:
            document = self.documents.get(document_id)
            case = self.cases.get(document.case_id) if document else None
            return deepcopy(document) if document and case and case.citizen_id == citizen_id else None

    def complete_document(self, document_id: str, citizen_id: str, sha256: str, document_type: str, manual_review: bool) -> CaseDocument:
        with self._lock:
            document = self.documents.get(document_id)
            case = self.cases.get(document.case_id) if document else None
            if document is None or case is None or case.citizen_id != citizen_id:
                raise KeyError("document_not_found")
            updated = document.model_copy(update={"sha256": sha256, "document_type": document_type, "ocr_status": "manual_review_required" if manual_review else "ready", "file_uri": f"private://{document.object_key}", "ocr_engine": "paddleocr", "ocr_version": "local-v1"})
            self.documents[document_id] = updated
            self._audit(case, citizen_id, "document_completed", "case_document", document_id)
            self._save_document(updated)
            return deepcopy(updated)

    def submit_citizen_case(self, case_id: str, citizen_id: str, expected_version: int, consent_version: str, idempotency_key: str) -> dict:
        cache_key = (citizen_id, idempotency_key)
        with self._lock:
            if cache_key in self.idempotency_results:
                return deepcopy(self.idempotency_results[cache_key])
            case = self.cases.get(case_id)
            if case is None or case.citizen_id != citizen_id:
                raise KeyError("case_not_found")
            if case.version != expected_version:
                raise ValueError("version_conflict")
            documents = [document for document in self.documents.values() if document.case_id == case_id]
            if not documents or any(document.ocr_status not in {"ready", "manual_review_required"} for document in documents):
                raise ValueError("documents_not_ready")
            locality_code = str(case.form_data.get("locality_code", ""))
            if not locality_code:
                raise ValueError("routing_not_found")
            organization_id = "org-demo"
            submission_version = case.current_submission_version
            submission_id = str(uuid4())
            submission = CaseSubmissionVersion(id=submission_id, case_id=case_id, version=submission_version, form_data=deepcopy(case.form_data), checklist_snapshot={document.document_type: "uploaded" for document in documents}, procedure_version_id=case.procedure_version_id, procedure_rule_version="ruleset-v1", created_at=now(), created_by=citizen_id)
            self.submissions[submission.id] = submission
            for document in documents:
                self.documents[document.id] = document.model_copy(update={"submission_version_id": submission_id})
            updated = case.model_copy(update={"organization_id": organization_id, "status": "awaiting_officer_review", "submitted_at": now(), "version": case.version + 1, "updated_at": now()})
            self.cases[case_id] = updated
            self._save_submission(submission)
            self._save_case(updated)
            for document in documents:
                self._save_document(self.documents[document.id])
            self.consents.append(ConsentRecord(case_id=case_id, citizen_id=citizen_id, consent_version=consent_version, accepted=True))
            self.routing_decisions[case_id] = RoutingDecision(procedure_id=case.procedure_id, locality_code=locality_code, organization_id=organization_id, matched_rule="procedure+locality:default")
            self._audit(updated, citizen_id, "case_submitted", "case_submission_version", submission_id)
            result = {"id": case_id, "case_code": updated.case_code, "status": updated.status, "submission_version": submission_version, "organization_id": organization_id, "version": updated.version}
            self.idempotency_results[cache_key] = result
            return deepcopy(result)

    def get_case(self, case_id: str, organization_id: str) -> ApplicationCase | None:
        with self._lock:
            case = self.cases.get(case_id)
            return deepcopy(case) if case and case.organization_id == organization_id else None

    def case_for_finding(self, finding_id: str, organization_id: str) -> ApplicationCase | None:
        with self._lock:
            finding = self.findings.get(finding_id)
            if finding is None:
                return None
            case = self.cases.get(finding.case_id)
            return deepcopy(case) if case and case.organization_id == organization_id else None

    def claim(self, case_id: str, organization_id: str, officer_id: str) -> ApplicationCase | None:
        with self._lock:
            case = self.cases.get(case_id)
            if case is None or case.organization_id != organization_id:
                return None
            if case.assigned_to and case.assigned_to != officer_id:
                raise ValueError("case_locked")
            updated = case.model_copy(update={"assigned_to": officer_id, "assigned_at": now(), "status": "in_officer_review", "version": case.version + 1, "updated_at": now()})
            self.cases[case_id] = updated
            self._audit(updated, officer_id, "case_claimed", "application_case", case_id)
            self._save_case(updated)
            return deepcopy(updated)

    def transition(self, case_id: str, organization_id: str, officer_id: str, target: str, reason: str | None = None) -> ApplicationCase | None:
        allowed = {"in_officer_review": {"needs_citizen_update", "escalated", "precheck_ready", "closed"}, "awaiting_officer_review": {"in_officer_review"}, "needs_citizen_update": {"resubmitted", "closed"}, "resubmitted": {"ocr_processing"}}
        with self._lock:
            case = self.cases.get(case_id)
            if case is None or case.organization_id != organization_id:
                return None
            if target not in allowed.get(case.status, set()):
                raise ValueError("invalid_transition")
            if target == "precheck_ready":
                active = [f for f in self.findings.values() if f.case_id == case_id and f.submission_version_id == self.submission_for(case_id).id and f.severity == "error" and f.status == "open"]
                if active:
                    raise ValueError("blocking_findings")
            updated = case.model_copy(update={"status": target, "version": case.version + 1, "updated_at": now()})
            self.cases[case_id] = updated
            self._audit(updated, officer_id, "case_transitioned", "application_case", case_id, {"target": target, "reason": reason} if reason else {"target": target})
            self._save_case(updated)
            return deepcopy(updated)

    def create_supplement(self, case_id: str, organization_id: str, officer_id: str, message: str, finding_ids: list[str]) -> SupplementRequest:
        with self._lock:
            case = self.cases.get(case_id)
            if case is None or case.organization_id != organization_id:
                raise KeyError("case_not_found")
            available = {f.id for f in self.findings_for(case_id, organization_id)}
            if not finding_ids or not set(finding_ids).issubset(available):
                raise ValueError("invalid_finding_ids")
            request = SupplementRequest(id=str(uuid4()), case_id=case_id, submission_version_id=self.submission_for(case_id).id, created_by=officer_id, public_message=message, finding_ids=finding_ids, status="sent", created_at=now())
            self.supplements.append(request)
            updated = case.model_copy(update={"status": "needs_citizen_update", "version": case.version + 1, "updated_at": now()})
            self.cases[case_id] = updated
            self._audit(updated, officer_id, "supplement_requested", "supplement_request", request.id)
            self._save_case(updated)
            return deepcopy(request)

    def submission_for(self, case_id: str) -> CaseSubmissionVersion:
        return max((s for s in self.submissions.values() if s.case_id == case_id), key=lambda item: item.version)

    def findings_for(self, case_id: str, organization_id: str) -> list[ValidationFinding]:
        if not self.get_case(case_id, organization_id):
            return []
        current = self.submission_for(case_id).id
        with self._lock:
            return [deepcopy(f) for f in self.findings.values() if f.case_id == case_id and f.submission_version_id == current]

    def decide(self, finding_id: str, organization_id: str, officer_id: str, decision: str, reason: str | None = None) -> ValidationFinding:
        with self._lock:
            finding = self.findings.get(finding_id)
            case = self.cases.get(finding.case_id) if finding else None
            if finding is None or case is None or case.organization_id != organization_id:
                raise KeyError("finding_not_found")
            updated = finding.model_copy(update={"status": decision})
            self.findings[finding_id] = updated
            self.decisions.append(OfficerDecision(id=str(uuid4()), finding_id=finding_id, officer_id=officer_id, decision=decision, finding_severity=finding.severity, reason=reason, created_at=now()))
            self._audit(case, officer_id, f"finding_{decision}", "validation_finding", finding_id, {"reason": reason} if reason else {})
            return deepcopy(updated)

    def timeline(self, case_id: str, organization_id: str) -> list[CaseAuditEvent]:
        if not self.get_case(case_id, organization_id):
            return []
        with self._lock:
            return [deepcopy(e) for e in self.audit if e.case_id == case_id]

    def _audit(self, case: ApplicationCase, actor_id: str, event_type: str, object_type: str, object_id: str, metadata: dict | None = None) -> None:
        event = CaseAuditEvent(id=str(uuid4()), case_id=case.id, actor_id=actor_id, organization_id=case.organization_id, event_type=event_type, object_type=object_type, object_id=object_id, metadata=metadata or {}, created_at=now())
        self.audit.append(event)
        self._save_audit(event)


store = OfficerStore()
