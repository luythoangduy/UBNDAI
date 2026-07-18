"""SQLAlchemy 2 persistence foundation for the citizen/officer workflow.

The mappings deliberately use portable SQL types (JSON and text enums), so the
same schema can be exercised with SQLite in tests and deployed on PostgreSQL.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, UTC
from typing import Any
from collections.abc import Iterator

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, event, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(UTC)


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ApplicationCaseORM(TimestampMixin, Base):
    __tablename__ = "application_cases"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    citizen_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    procedure_id: Mapped[str] = mapped_column(String(128), nullable=False)
    procedure_version_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="draft", index=True, nullable=False)
    source_channel: Mapped[str] = mapped_column(String(64), default="citizen_portal", nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(128))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_submission_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    form_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    checklist: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    classification_method: Mapped[str | None] = mapped_column(String(64))
    classification_evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analysis_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analysis_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SubmissionVersionORM(Base):
    __tablename__ = "case_submission_versions"
    __table_args__ = (UniqueConstraint("case_id", "version", name="uq_submission_case_version"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("application_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    form_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    checklist_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    procedure_version_id: Mapped[str] = mapped_column(String(128), nullable=False)
    procedure_rule_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(64), default="citizen_portal", nullable=False)


class CaseDocumentORM(Base):
    __tablename__ = "case_documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("application_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    submission_version_id: Mapped[str | None] = mapped_column(ForeignKey("case_submission_versions.id", ondelete="SET NULL"), index=True)
    document_type: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="upload_pending", index=True, nullable=False)
    ocr_status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    ocr_engine: Mapped[str | None] = mapped_column(String(128))
    ocr_version: Mapped[str | None] = mapped_column(String(128))
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    template_code: Mapped[str | None] = mapped_column(String(128))
    template_version: Mapped[str | None] = mapped_column(String(128))
    extracted_text: Mapped[str | None] = mapped_column(Text)


class ExtractedFieldRecordORM(TimestampMixin, Base):
    __tablename__ = "extracted_field_records"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("case_documents.id", ondelete="CASCADE"), index=True, nullable=False)
    field_key: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    bounding_box: Mapped[list[float] | None] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(64), default="unreviewed", nullable=False)
    previous_value: Mapped[str | None] = mapped_column(Text)


class ValidationFindingORM(TimestampMixin, Base):
    __tablename__ = "validation_findings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("application_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    submission_version_id: Mapped[str] = mapped_column(ForeignKey("case_submission_versions.id", ondelete="CASCADE"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str | None] = mapped_column(Text)
    rule_id: Mapped[str | None] = mapped_column(String(128))
    rule_version: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True, nullable=False)
    field_keys: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)


class FindingDecisionORM(Base):
    __tablename__ = "finding_decisions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("validation_findings.id", ondelete="CASCADE"), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(ForeignKey("application_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    officer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SupplementRequestORM(Base):
    __tablename__ = "supplement_requests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("application_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    submission_version_id: Mapped[str] = mapped_column(ForeignKey("case_submission_versions.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    public_message: Mapped[str] = mapped_column(Text, nullable=False)
    finding_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="sent", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ApplicationCaseDecisionORM(Base):
    __tablename__ = "application_case_decisions"
    __table_args__ = (UniqueConstraint("case_id", "idempotency_key", name="uq_case_decision_idempotency"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("application_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    submission_version_id: Mapped[str] = mapped_column(ForeignKey("case_submission_versions.id", ondelete="CASCADE"), nullable=False)
    officer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    selected_finding_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    citizen_message: Mapped[str | None] = mapped_column(Text)
    previous_status: Mapped[str] = mapped_column(String(64), nullable=False)
    new_status: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditEventORM(Base):
    __tablename__ = "case_audit_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("application_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    object_type: Mapped[str] = mapped_column(String(128), nullable=False)
    object_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RoutingDecisionORM(Base):
    __tablename__ = "routing_decisions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("application_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    submission_version_id: Mapped[str] = mapped_column(ForeignKey("case_submission_versions.id", ondelete="CASCADE"), nullable=False)
    procedure_id: Mapped[str] = mapped_column(String(128), nullable=False)
    procedure_version_id: Mapped[str] = mapped_column(String(128), nullable=False)
    locality_code: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    matched_rule: Mapped[str] = mapped_column(String(256), nullable=False)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ConsentRecordORM(Base):
    __tablename__ = "consent_records"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("application_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    submission_version_id: Mapped[str] = mapped_column(ForeignKey("case_submission_versions.id", ondelete="CASCADE"), nullable=False)
    citizen_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted: Mapped[bool] = mapped_column(nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String(128))


class BackgroundJobORM(Base):
    __tablename__ = "background_jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class NotificationEventORM(Base):
    __tablename__ = "notification_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("application_cases.id", ondelete="SET NULL"), index=True)
    recipient_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Database:
    def __init__(self, url: str):
        self.engine = create_engine(url, future=True)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
        self._session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class AsyncDatabase:
    """Async SQLAlchemy 2 database used by API/worker processes in production."""

    def __init__(self, url: str):
        normalized = url
        if normalized.startswith("sqlite://") and "+aiosqlite" not in normalized:
            normalized = normalized.replace("sqlite://", "sqlite+aiosqlite://", 1)
        if normalized.startswith("postgresql://"):
            normalized = normalized.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.engine: AsyncEngine = create_async_engine(normalized, future=True)
        self._session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> AsyncSession:
        return self._session_factory()

    async def create_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)


def create_async_database(url: str) -> AsyncDatabase:
    return AsyncDatabase(url)


def create_sqlite_database(url: str = "sqlite+pysqlite:///:memory:") -> Database:
    db = Database(url)
    db.create_schema()
    return db


class CaseRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, case: ApplicationCaseORM) -> ApplicationCaseORM:
        self.session.add(case)
        return case

    def get(self, case_id: str) -> ApplicationCaseORM | None:
        return self.session.get(ApplicationCaseORM, case_id)

    def list_for_organization(self, organization_id: str) -> list[ApplicationCaseORM]:
        return list(self.session.scalars(select(ApplicationCaseORM).where(ApplicationCaseORM.organization_id == organization_id).order_by(ApplicationCaseORM.created_at)))
