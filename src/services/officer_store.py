"""Repository-like in-memory officer workflow store for local P0/demo."""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import RLock
from uuid import uuid4

from src.models import (
    ApplicationCase,
    CaseAuditEvent,
    CaseDocument,
    CaseSubmissionVersion,
    ConsentRecord,
    ExtractedFieldRecord,
    OfficerDecision,
    RoutingDecision,
    SupplementRequest,
    ValidationFinding,
)
from src.config import settings
from src.services.application_repository import ApplicationRepository, RepositoryNotFound
from src.services.persistence import (
    ApplicationCaseORM,
    AuditEventORM,
    CaseDocumentORM,
    Database,
    ExtractedFieldRecordORM,
    FindingDecisionORM,
    SubmissionVersionORM,
    SupplementRequestORM,
    ValidationFindingORM,
)
from src.services.storage import storage


def now() -> datetime:
    return datetime.now(timezone.utc)


class OfficerStore:
    def __init__(self, *, database: Database | None = None, seed: bool = True) -> None:
        self._lock = RLock()
        self.cases: dict[str, ApplicationCase] = {}
        self.findings: dict[str, ValidationFinding] = {}
        self.submissions: dict[str, CaseSubmissionVersion] = {}
        self.decisions: list[OfficerDecision] = []
        self.audit: list[CaseAuditEvent] = []
        self.supplements: list[SupplementRequest] = []
        self.documents: dict[str, CaseDocument] = {}
        self.extracted_fields: dict[str, ExtractedFieldRecord] = {}
        self.routing_decisions: dict[str, RoutingDecision] = {}
        self.consents: list[ConsentRecord] = []
        self.idempotency_results: dict[tuple[str, str], dict] = {}
        self._db = database or (Database(settings.database_url) if settings.persistence_enabled else None)
        if self._db:
            if settings.app_env != "production":
                self._db.create_schema()
            self._load_persisted_cases()
        if seed:
            self._seed()

    @staticmethod
    def _case_model(row: ApplicationCaseORM) -> ApplicationCase:
        return ApplicationCase(
            id=row.id,
            case_code=row.case_code,
            organization_id=row.organization_id,
            citizen_id=row.citizen_id,
            procedure_id=row.procedure_id,
            procedure_version_id=row.procedure_version_id,
            status=row.status,
            source_channel=row.source_channel,
            assigned_to=row.assigned_to,
            assigned_at=row.assigned_at,
            priority=row.priority,
            submitted_at=row.submitted_at,
            sla_due_at=row.sla_due_at,
            current_submission_version=row.current_submission_version,
            version=row.version,
            form_data=row.form_data or {},
            checklist=row.checklist or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _finding_model(row: ValidationFindingORM) -> ValidationFinding:
        return ValidationFinding(
            id=row.id,
            case_id=row.case_id,
            submission_version_id=row.submission_version_id,
            type=row.type,
            severity=row.severity,
            source=row.source,
            message=row.message,
            suggestion=row.suggestion,
            rule_id=row.rule_id,
            rule_version=row.rule_version,
            confidence=row.confidence,
            status=row.status,
            field_keys=row.field_keys or [],
            evidence=row.evidence or [],
            created_at=row.created_at,
        )

    def _load_persisted_cases(self) -> None:
        if not self._db:
            return
        with self._db.session() as session:
            for row in session.query(ApplicationCaseORM).all():
                self.cases[row.id] = self._case_model(row)
            for row in session.query(SubmissionVersionORM).all():
                self.submissions[row.id] = CaseSubmissionVersion(id=row.id, case_id=row.case_id, version=row.version, form_data=row.form_data or {}, checklist_snapshot=row.checklist_snapshot or {}, procedure_version_id=row.procedure_version_id, procedure_rule_version=row.procedure_rule_version, created_at=row.created_at, created_by=row.created_by, source=row.source)
            for row in session.query(CaseDocumentORM).all():
                self.documents[row.id] = CaseDocument(id=row.id, case_id=row.case_id, submission_version_id=row.submission_version_id or "", document_type=row.document_type, file_uri=f"private://{row.object_key}", object_key=row.object_key, original_filename=row.original_filename, content_type=row.content_type, size_bytes=row.size_bytes, sha256=row.sha256, ocr_status=row.ocr_status, ocr_engine=row.ocr_engine, ocr_version=row.ocr_version, uploaded_at=row.uploaded_at or row.created_at)
            for row in session.query(ExtractedFieldRecordORM).all():
                self.extracted_fields[row.id] = ExtractedFieldRecord(id=row.id, document_id=row.document_id, field_key=row.field_key, raw_value=row.raw_value, normalized_value=row.normalized_value, confidence=row.confidence, page=row.page, bounding_box=row.bounding_box, review_status=row.review_status, previous_value=row.previous_value)
            for row in session.query(ValidationFindingORM).all():
                self.findings[row.id] = self._finding_model(row)
            for row in session.query(SupplementRequestORM).all():
                self.supplements.append(SupplementRequest(id=row.id, case_id=row.case_id, submission_version_id=row.submission_version_id, created_by=row.created_by, public_message=row.public_message, finding_ids=row.finding_ids or [], due_at=row.due_at, status=row.status, created_at=row.created_at))
            for row in session.query(AuditEventORM).all():
                self.audit.append(CaseAuditEvent(id=row.id, case_id=row.case_id, actor_id=row.actor_id, organization_id=row.organization_id, event_type=row.event_type, object_type=row.object_type, object_id=row.object_id, metadata=row.metadata_ or {}, created_at=row.created_at))

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

    def _save_field(self, field: ExtractedFieldRecord) -> None:
        if not self._db:
            return
        with self._db.session() as session:
            session.merge(ExtractedFieldRecordORM(id=field.id, document_id=field.document_id, field_key=field.field_key, raw_value=field.raw_value, normalized_value=field.normalized_value, confidence=field.confidence, page=field.page, bounding_box=field.bounding_box, review_status=field.review_status, previous_value=field.previous_value))
            session.commit()

    def _save_finding(self, finding: ValidationFinding) -> None:
        if not self._db:
            return
        with self._db.session() as session:
            session.merge(ValidationFindingORM(id=finding.id, case_id=finding.case_id, submission_version_id=finding.submission_version_id, type=finding.type, severity=finding.severity, source=finding.source, message=finding.message, suggestion=finding.suggestion, rule_id=finding.rule_id, rule_version=str(finding.rule_version) if finding.rule_version is not None else None, confidence=finding.confidence, status=finding.status, field_keys=finding.field_keys, evidence=finding.evidence, created_at=finding.created_at, updated_at=now()))
            session.commit()

    def _save_supplement(self, request: SupplementRequest) -> None:
        if not self._db:
            return
        with self._db.session() as session:
            session.merge(SupplementRequestORM(id=request.id, case_id=request.case_id, submission_version_id=request.submission_version_id, created_by=request.created_by, public_message=request.public_message, finding_ids=request.finding_ids, due_at=request.due_at, status=request.status, created_at=request.created_at))
            session.commit()

    def _save_finding_decision(self, case_id: str, decision: OfficerDecision) -> None:
        if not self._db:
            return
        with self._db.session() as session:
            session.merge(FindingDecisionORM(id=decision.id, finding_id=decision.finding_id, case_id=case_id, officer_id=decision.officer_id, decision=decision.decision, reason=decision.reason, created_at=decision.created_at))
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
        demo_form = {
            "ho_ten_con": "Nguyễn Minh An",
            "ngay_sinh": "12/07/2026",
            "gioi_tinh": "Nam",
            "noi_sinh": "Bệnh viện Đa khoa Thành phố",
            "ho_ten_me": "Nguyễn Thị Lan",
            "ho_ten_cha": "Trần Văn Nam",
            "locality_code": "00001",
            "_readiness_score": 86,
        }
        demo_checklist = {
            "to_khai_khai_sinh": "verified",
            "giay_chung_sinh": "uploaded",
            "cccd_cha_me": "uploaded",
            "giay_dang_ky_ket_hon": "missing",
        }
        case = ApplicationCase(id="case-demo-001", case_code="UBNDAI-2026-000001", organization_id="org-demo", citizen_id="citizen-demo", procedure_id="khai_sinh", procedure_version_id="khai-sinh-v1", status="awaiting_officer_review", source_channel="citizen_portal", priority=80, form_data=demo_form, checklist=demo_checklist, created_at=timestamp, updated_at=timestamp)
        other = case.model_copy(update={"id": "case-other-001", "case_code": "UBNDAI-2026-000002", "organization_id": "org-other"})
        self.cases[case.id] = case
        self.cases[other.id] = other
        submission = CaseSubmissionVersion(id="submission-demo-001", case_id=case.id, version=1, form_data=demo_form, checklist_snapshot=demo_checklist, procedure_version_id=case.procedure_version_id, procedure_rule_version="ruleset-v1", created_at=timestamp, created_by=case.citizen_id)
        other_submission = submission.model_copy(
            update={
                "id": "submission-other-001",
                "case_id": other.id,
                "created_by": other.citizen_id,
            }
        )
        self.submissions[submission.id] = submission
        self.submissions[other_submission.id] = other_submission
        self._save_case(case)
        self._save_case(other)
        self._save_submission(submission)
        self._save_submission(other_submission)
        demo_asset = Path(__file__).resolve().parents[2] / "data" / "demo" / "giay_chung_sinh_demo.svg"
        demo_content = demo_asset.read_bytes()
        object_key = "demo/case-demo-001/giay-chung-sinh.svg"
        storage.put(object_key, demo_content)
        document = CaseDocument(
            id="document-demo-001",
            case_id=case.id,
            submission_version_id=submission.id,
            document_type="giay_chung_sinh",
            file_uri=f"private://{object_key}",
            object_key=object_key,
            original_filename="giay-chung-sinh-demo.svg",
            content_type="image/svg+xml",
            size_bytes=len(demo_content),
            sha256=sha256(demo_content).hexdigest(),
            ocr_status="manual_review_required",
            ocr_engine="vision_llm",
            ocr_version="demo-v1",
            uploaded_at=timestamp,
        )
        self.documents[document.id] = document
        self._save_document(document)
        for field_id, key, value, confidence, bbox in [
            ("field-demo-child", "ho_ten_con", "Nguyễn Minh An", 0.98, [0.24, 0.28, 0.38, 0.045]),
            ("field-demo-birth-date", "ngay_sinh", "12/07/2026", 0.96, [0.23, 0.35, 0.22, 0.04]),
            ("field-demo-birth-place", "noi_sinh", "Bệnh viện Đa khoa Thành phố", 0.91, [0.20, 0.43, 0.55, 0.04]),
            ("field-demo-mother", "ho_ten_me", "Nguyễn Thị Lân", 0.72, [0.22, 0.52, 0.34, 0.045]),
            ("field-demo-gender", "gioi_tinh", "Nam", 0.95, [0.66, 0.35, 0.10, 0.04]),
        ]:
            self.extracted_fields[field_id] = ExtractedFieldRecord(
                id=field_id,
                document_id=document.id,
                field_key=key,
                raw_value=value,
                normalized_value=value,
                confidence=confidence,
                page=1,
                bounding_box=bbox,
                review_status="needs_human_review" if confidence < settings.ocr_confidence_threshold else "unreviewed",
            )
            self._save_field(self.extracted_fields[field_id])
        finding = ValidationFinding(id="finding-demo-001", case_id=case.id, submission_version_id=submission.id, type="cross_document_mismatch", severity="error", source="rule", message="Họ tên mẹ trên Giấy chứng sinh chưa khớp dữ liệu tờ khai.", suggestion="Đối chiếu ảnh gốc và sửa trường OCR nếu hệ thống đọc sai dấu.", rule_id="KS-R2", rule_version=1, confidence=1.0, field_keys=["ho_ten_me"], created_at=timestamp)
        self.findings[finding.id] = finding
        self.findings["finding-demo-002"] = ValidationFinding(
            id="finding-demo-002",
            case_id=case.id,
            submission_version_id=submission.id,
            type="low_ocr_confidence",
            severity="warning",
            source="ai",
            message="Trường họ tên mẹ có độ tin cậy OCR 72% và cần cán bộ xác minh.",
            suggestion="Phóng to vùng được khoanh trên tài liệu gốc trước khi xác nhận.",
            confidence=0.72,
            field_keys=["ho_ten_me"],
            created_at=timestamp,
        )
        self._save_finding(finding)
        self._save_finding(self.findings["finding-demo-002"])
        self._audit(case, case.citizen_id, "case_created", "application_case", case.id)
        self._audit(case, case.citizen_id, "document_uploaded", "case_document", document.id)
        self._audit(case, "system-ai", "precheck_completed", "case_submission_version", submission.id)

    def reset_demo_data(self) -> None:
        """Reset the local demo projection to its deterministic showcase state."""
        with self._lock:
            self.cases.clear()
            self.findings.clear()
            self.submissions.clear()
            self.decisions.clear()
            self.audit.clear()
            self.supplements.clear()
            self.documents.clear()
            self.extracted_fields.clear()
            self.routing_decisions.clear()
            self.consents.clear()
            self.idempotency_results.clear()
            if self._db:
                with self._db.session() as session:
                    for model in (FindingDecisionORM, SupplementRequestORM, ValidationFindingORM, ExtractedFieldRecordORM, AuditEventORM, CaseDocumentORM, SubmissionVersionORM, ApplicationCaseORM):
                        session.query(model).delete()
                    session.commit()
            self._seed()

    def list_cases(self, organization_id: str) -> list[ApplicationCase]:
        if self._db:
            with self._db.session() as session:
                rows, _ = ApplicationRepository(session).list(organization_id)
                cases = [self._case_model(row) for row in rows]
                with self._lock:
                    self.cases.update({case.id: case for case in cases})
                return [deepcopy(case) for case in cases]
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

    def ensure_guidance_case(
        self,
        case_id: str,
        citizen_id: str,
        procedure_id: str | None = None,
    ) -> ApplicationCase:
        """Create the portal projection for an authenticated guidance case."""
        with self._lock:
            existing = self.cases.get(case_id)
            if existing is not None:
                if existing.citizen_id != citizen_id:
                    raise KeyError("case_not_found")
                return deepcopy(existing)

            timestamp = now()
            resolved_procedure = procedure_id or "pending_guidance"
            case = ApplicationCase(
                id=case_id,
                case_code=f"UBNDAI-{timestamp.year}-{case_id[:8].upper()}",
                organization_id="pending-routing",
                citizen_id=citizen_id,
                procedure_id=resolved_procedure,
                procedure_version_id=f"{resolved_procedure}-v1",
                status="draft",
                source_channel="ai_guidance",
                form_data={"locality_code": "00001"},
                created_at=timestamp,
                updated_at=timestamp,
            )
            self.cases[case.id] = case
            self._audit(case, citizen_id, "case_created_from_guidance", "application_case", case.id)
            self._save_case(case)
            return deepcopy(case)

    def sync_guidance_case(
        self,
        case_id: str,
        citizen_id: str,
        procedure_id: str | None,
        answers: dict,
        checklist: dict[str, str],
        status: str,
    ) -> ApplicationCase:
        """Synchronize LangGraph guidance state into the public portal case."""
        with self._lock:
            case = self.cases.get(case_id)
            if case is None or case.citizen_id != citizen_id:
                raise KeyError("case_not_found")
            resolved_procedure = procedure_id or "pending_guidance"
            form_data = {
                **case.form_data,
                "_answers": deepcopy(answers),
            }
            mapped_status = "collecting" if status == "collecting" else "draft"
            updated = case.model_copy(
                update={
                    "procedure_id": resolved_procedure,
                    "procedure_version_id": f"{resolved_procedure}-v1",
                    "form_data": form_data,
                    "checklist": deepcopy(checklist),
                    "status": mapped_status,
                    "version": case.version + 1,
                    "updated_at": now(),
                }
            )
            self.cases[case_id] = updated
            self._save_case(updated)
            return deepcopy(updated)

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
            merged_form_data = {**case.form_data, **(form_data or {})}
            if answers is not None:
                existing_answers = case.form_data.get("_answers", {})
                merged_form_data["_answers"] = {
                    **(existing_answers if isinstance(existing_answers, dict) else {}),
                    **answers,
                }
            updated = case.model_copy(update={"form_data": merged_form_data, "version": case.version + 1, "updated_at": now()})
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

    def complete_document(
        self,
        document_id: str,
        citizen_id: str,
        sha256: str,
        document_type: str,
        manual_review: bool,
        fields: list[dict] | None = None,
        ocr_engine: str | None = None,
    ) -> CaseDocument:
        with self._lock:
            document = self.documents.get(document_id)
            case = self.cases.get(document.case_id) if document else None
            if document is None or case is None or case.citizen_id != citizen_id:
                raise KeyError("document_not_found")
            engine_name = ocr_engine or settings.ocr_engine
            updated = document.model_copy(update={"sha256": sha256, "document_type": document_type, "ocr_status": "manual_review_required" if manual_review else "ready", "file_uri": f"private://{document.object_key}", "ocr_engine": engine_name, "ocr_version": "demo-v1"})
            self.documents[document_id] = updated
            for item in fields or []:
                confidence = float(item.get("confidence", 0.0))
                record = ExtractedFieldRecord(
                    id=str(uuid4()),
                    document_id=document_id,
                    field_key=str(item.get("key", "unknown")),
                    raw_value=str(item.get("value", "")),
                    normalized_value=str(item.get("value", "")),
                    confidence=confidence,
                    review_status="needs_human_review" if confidence < settings.ocr_confidence_threshold else "unreviewed",
                    bounding_box=item.get("bbox") or item.get("bounding_box"),
                )
                self.extracted_fields[record.id] = record
                self._save_field(record)
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
            submitted_values = {
                key: value
                for key, value in case.form_data.items()
                if not key.startswith("_") and key != "locality_code" and value not in (None, "")
            }
            if not submitted_values:
                raise ValueError("form_data_not_ready")
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
        if self._db:
            with self._db.session() as session:
                row = ApplicationRepository(session).get(case_id, organization_id)
                if row is None:
                    return None
                case = self._case_model(row)
                with self._lock:
                    self.cases[case.id] = case
                return deepcopy(case)
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
                active_statuses = {"open", "accepted", "escalated"}
                active = [f for f in self.findings.values() if f.case_id == case_id and f.submission_version_id == self.submission_for(case_id).id and f.severity == "error" and f.status in active_statuses]
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
            self._save_supplement(request)
            updated = case.model_copy(update={"status": "needs_citizen_update", "version": case.version + 1, "updated_at": now()})
            self.cases[case_id] = updated
            self._audit(updated, officer_id, "supplement_requested", "supplement_request", request.id)
            self._save_case(updated)
            return deepcopy(request)

    def submission_for(self, case_id: str) -> CaseSubmissionVersion:
        return max((s for s in self.submissions.values() if s.case_id == case_id), key=lambda item: item.version)

    def findings_for(self, case_id: str, organization_id: str) -> list[ValidationFinding]:
        if self._db:
            with self._db.session() as session:
                repository = ApplicationRepository(session)
                try:
                    rows = repository.findings(case_id, organization_id)
                except RepositoryNotFound:
                    return []
                if not rows:
                    return []
                latest_submission = max(
                    (item for item in self.submissions.values() if item.case_id == case_id),
                    key=lambda item: item.version,
                    default=None,
                )
                if latest_submission is None:
                    latest_id = rows[-1].submission_version_id
                else:
                    latest_id = latest_submission.id
                findings = [self._finding_model(row) for row in rows if row.submission_version_id == latest_id]
                with self._lock:
                    self.findings.update({finding.id: finding for finding in findings})
                return [deepcopy(finding) for finding in findings]
        if not self.get_case(case_id, organization_id):
            return []
        current = self.submission_for(case_id).id
        with self._lock:
            return [deepcopy(f) for f in self.findings.values() if f.case_id == case_id and f.submission_version_id == current]

    def documents_for_case(self, case_id: str, organization_id: str) -> list[CaseDocument]:
        if self.get_case(case_id, organization_id) is None:
            return []
        if self._db:
            with self._db.session() as session:
                rows = session.query(CaseDocumentORM).filter(CaseDocumentORM.case_id == case_id).order_by(CaseDocumentORM.created_at, CaseDocumentORM.id).all()
                documents = [CaseDocument(
                    id=row.id, case_id=row.case_id, submission_version_id=row.submission_version_id or "",
                    document_type=row.document_type, file_uri=f"private://{row.object_key}",
                    object_key=row.object_key, original_filename=row.original_filename,
                    content_type=row.content_type, size_bytes=row.size_bytes, sha256=row.sha256,
                    ocr_status=row.ocr_status, ocr_engine=row.ocr_engine, ocr_version=row.ocr_version,
                    uploaded_at=row.uploaded_at or row.created_at,
                ) for row in rows]
                with self._lock:
                    self.documents.update({document.id: document for document in documents})
                return documents
        with self._lock:
            return [deepcopy(document) for document in self.documents.values() if document.case_id == case_id]

    def fields_for_document(self, document_id: str, organization_id: str) -> list[ExtractedFieldRecord]:
        if self._db:
            with self._db.session() as session:
                document = session.get(CaseDocumentORM, document_id)
                if document is None or ApplicationRepository(session).get(document.case_id, organization_id) is None:
                    raise KeyError("document_not_found")
                rows = ApplicationRepository(session).fields_for_document(document_id)
                return [ExtractedFieldRecord(
                    id=row.id, document_id=row.document_id, field_key=row.field_key,
                    raw_value=row.raw_value, normalized_value=row.normalized_value,
                    confidence=row.confidence, page=row.page, bounding_box=row.bounding_box,
                    review_status=row.review_status, previous_value=row.previous_value,
                ) for row in rows]
        with self._lock:
            document = self.documents.get(document_id)
            case = self.cases.get(document.case_id) if document else None
            if document is None or case is None or case.organization_id != organization_id:
                raise KeyError("document_not_found")
            return [deepcopy(field) for field in self.extracted_fields.values() if field.document_id == document_id]

    def update_field(
        self,
        field_id: str,
        organization_id: str,
        officer_id: str,
        normalized_value: str,
        reason: str,
    ) -> ExtractedFieldRecord:
        with self._lock:
            field = self.extracted_fields.get(field_id)
            document = self.documents.get(field.document_id) if field else None
            case = self.cases.get(document.case_id) if document else None
            if field is None or document is None or case is None or case.organization_id != organization_id:
                raise KeyError("field_not_found")
            previous = field.normalized_value or field.raw_value
            updated = field.model_copy(
                update={
                    "normalized_value": normalized_value.strip(),
                    "previous_value": previous,
                    "review_status": "edited",
                }
            )
            self.extracted_fields[field_id] = updated
            self._save_field(updated)
            self._audit(
                case,
                officer_id,
                "ocr_field_edited",
                "extracted_field",
                field_id,
                {"field_key": field.field_key, "reason": reason},
            )
            return deepcopy(updated)

    def rerun_validation(self, case_id: str, organization_id: str, officer_id: str) -> list[ValidationFinding]:
        """Refresh deterministic field-review findings for the local P0 store.

        Full rule execution remains in ``services.validation``. This method only
        maintains the version-scoped OCR review finding required by the officer
        workspace and never manufactures a rule-engine error.
        """
        with self._lock:
            case = self.cases.get(case_id)
            if case is None or case.organization_id != organization_id:
                raise KeyError("case_not_found")
            submission = self.submission_for(case_id)
            document_ids = {item.id for item in self.documents.values() if item.case_id == case_id}
            needs_review = [
                field
                for field in self.extracted_fields.values()
                if field.document_id in document_ids and field.review_status == "needs_human_review"
            ]
            for finding_id, finding in list(self.findings.items()):
                if finding.case_id == case_id and finding.type == "ocr_human_review" and finding.status == "open":
                    self.findings[finding_id] = finding.model_copy(update={"status": "superseded"})
                    self._save_finding(self.findings[finding_id])
            if needs_review:
                finding = ValidationFinding(
                    id=str(uuid4()),
                    case_id=case_id,
                    submission_version_id=submission.id,
                    type="ocr_human_review",
                    severity="warning",
                    source="rule",
                    message=f"Có {len(needs_review)} trường OCR cần cán bộ xác minh.",
                    suggestion="Đối chiếu tài liệu gốc và xác nhận hoặc chỉnh sửa các trường có độ tin cậy thấp.",
                    rule_id="ocr.confidence_threshold",
                    rule_version="local-v1",
                    field_keys=[field.field_key for field in needs_review],
                    created_at=now(),
                )
                self.findings[finding.id] = finding
                self._save_finding(finding)
            self._audit(case, officer_id, "validation_rerun", "case_submission_version", submission.id)
            return self.findings_for(case_id, organization_id)

    def supplements_for(self, case_id: str, organization_id: str) -> list[SupplementRequest]:
        if self.get_case(case_id, organization_id) is None:
            raise KeyError("case_not_found")
        with self._lock:
            return [deepcopy(item) for item in self.supplements if item.case_id == case_id]

    def decide(self, finding_id: str, organization_id: str, officer_id: str, decision: str, reason: str | None = None) -> ValidationFinding:
        with self._lock:
            finding = self.findings.get(finding_id)
            case = self.cases.get(finding.case_id) if finding else None
            if finding is None or case is None or case.organization_id != organization_id:
                raise KeyError("finding_not_found")
            updated = finding.model_copy(update={"status": decision})
            self.findings[finding_id] = updated
            officer_decision = OfficerDecision(id=str(uuid4()), finding_id=finding_id, officer_id=officer_id, decision=decision, finding_severity=finding.severity, reason=reason, created_at=now())
            self.decisions.append(officer_decision)
            self._save_finding(updated)
            self._save_finding_decision(case.id, officer_decision)
            self._audit(case, officer_id, f"finding_{decision}", "validation_finding", finding_id, {"reason": reason} if reason else {})
            return deepcopy(updated)

    def timeline(self, case_id: str, organization_id: str) -> list[CaseAuditEvent]:
        if self._db:
            if self.get_case(case_id, organization_id) is None:
                return []
            with self._db.session() as session:
                rows = session.query(AuditEventORM).filter(AuditEventORM.case_id == case_id).order_by(AuditEventORM.created_at, AuditEventORM.id).all()
                return [CaseAuditEvent(id=row.id, case_id=row.case_id, actor_id=row.actor_id, organization_id=row.organization_id, event_type=row.event_type, object_type=row.object_type, object_id=row.object_id, metadata=row.metadata_ or {}, created_at=row.created_at) for row in rows]
        if not self.get_case(case_id, organization_id):
            return []
        with self._lock:
            return [deepcopy(e) for e in self.audit if e.case_id == case_id]

    def _audit(self, case: ApplicationCase, actor_id: str, event_type: str, object_type: str, object_id: str, metadata: dict | None = None) -> None:
        event = CaseAuditEvent(id=str(uuid4()), case_id=case.id, actor_id=actor_id, organization_id=case.organization_id, event_type=event_type, object_type=object_type, object_id=object_id, metadata=metadata or {}, created_at=now())
        self.audit.append(event)
        self._save_audit(event)


store = OfficerStore()
