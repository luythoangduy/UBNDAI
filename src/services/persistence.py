"""SQLAlchemy 2 persistence foundation for the citizen/officer workflow.

The mappings deliberately use portable SQL types (JSON and text enums), so the
same schema can be exercised with SQLite in tests and deployed on PostgreSQL.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


class SubmissionVersionORM(Base):
    __tablename__ = "case_submission_versions"
    __table_args__ = (UniqueConstraint("case_id", "version", name="uq_submission_case_version"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
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
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    submission_version_id: Mapped[str | None] = mapped_column(String(64), index=True)
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


class AuditEventORM(Base):
    __tablename__ = "case_audit_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
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
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    submission_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
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
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    submission_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
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
    case_id: Mapped[str | None] = mapped_column(String(64), index=True)
    recipient_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Database:
    def __init__(self, url: str):
        self.engine = create_engine(url, future=True)
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
