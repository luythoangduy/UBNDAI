"""Database-only repository for the officer application aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.services.persistence import (
    ApplicationCaseDecisionORM,
    ApplicationCaseORM,
    AuditEventORM,
    ExtractedFieldRecordORM,
    FindingDecisionORM,
    NotificationEventORM,
    SupplementRequestORM,
    ValidationFindingORM,
    utcnow,
)


class RepositoryNotFound(LookupError):
    pass


class RepositoryConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class ApplicationFilters:
    search: str | None = None
    status: str | None = None
    procedure_id: str | None = None
    assigned_to: str | None = None
    submitted_from: datetime | None = None
    submitted_to: datetime | None = None
    page: int = 1
    page_size: int = 20


class ApplicationRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, case_id: str, organization_id: str, *, for_update: bool = False) -> ApplicationCaseORM | None:
        statement = select(ApplicationCaseORM).where(
            ApplicationCaseORM.id == case_id,
            ApplicationCaseORM.organization_id == organization_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def list(self, organization_id: str, filters: ApplicationFilters | None = None) -> tuple[list[ApplicationCaseORM], int]:
        filters = filters or ApplicationFilters()
        conditions = [ApplicationCaseORM.organization_id == organization_id]
        if filters.search:
            term = f"%{filters.search.strip()}%"
            conditions.append(or_(ApplicationCaseORM.case_code.ilike(term), ApplicationCaseORM.procedure_id.ilike(term)))
        if filters.status:
            conditions.append(ApplicationCaseORM.status == filters.status)
        if filters.procedure_id:
            conditions.append(ApplicationCaseORM.procedure_id == filters.procedure_id)
        if filters.assigned_to:
            conditions.append(ApplicationCaseORM.assigned_to == filters.assigned_to)
        if filters.submitted_from:
            conditions.append(ApplicationCaseORM.submitted_at >= filters.submitted_from)
        if filters.submitted_to:
            conditions.append(ApplicationCaseORM.submitted_at <= filters.submitted_to)
        base = select(ApplicationCaseORM).where(*conditions).order_by(ApplicationCaseORM.created_at.desc())
        total = self.session.scalar(select(func.count()).select_from(base.subquery())) or 0
        offset = max(filters.page - 1, 0) * filters.page_size
        rows = list(self.session.scalars(base.offset(offset).limit(filters.page_size)))
        return rows, int(total)

    def update_status(self, case_id: str, organization_id: str, target_status: str, *, expected_version: int) -> ApplicationCaseORM:
        case = self.get(case_id, organization_id, for_update=True)
        if case is None:
            raise RepositoryNotFound(case_id)
        if case.version != expected_version:
            raise RepositoryConflict("application version is stale")
        case.status = target_status
        case.version += 1
        case.updated_at = utcnow()
        return case

    def decision_by_idempotency(self, case_id: str, idempotency_key: str) -> ApplicationCaseDecisionORM | None:
        return self.session.scalar(select(ApplicationCaseDecisionORM).where(
            ApplicationCaseDecisionORM.case_id == case_id,
            ApplicationCaseDecisionORM.idempotency_key == idempotency_key,
        ))

    def add_decision(self, decision: ApplicationCaseDecisionORM) -> ApplicationCaseDecisionORM:
        existing = self.decision_by_idempotency(decision.case_id, decision.idempotency_key)
        if existing is not None:
            if existing.decision != decision.decision or existing.note != decision.note:
                raise RepositoryConflict("idempotency key was already used with another decision")
            return existing
        self.session.add(decision)
        return decision

    def findings(self, case_id: str, organization_id: str, *, submission_version_id: str | None = None) -> list[ValidationFindingORM]:
        if self.get(case_id, organization_id) is None:
            raise RepositoryNotFound(case_id)
        statement = select(ValidationFindingORM).where(ValidationFindingORM.case_id == case_id)
        if submission_version_id:
            statement = statement.where(ValidationFindingORM.submission_version_id == submission_version_id)
        return list(self.session.scalars(statement.order_by(ValidationFindingORM.created_at, ValidationFindingORM.id)))

    def fields_for_document(self, document_id: str) -> list[ExtractedFieldRecordORM]:
        return list(self.session.scalars(select(ExtractedFieldRecordORM).where(
            ExtractedFieldRecordORM.document_id == document_id,
        ).order_by(ExtractedFieldRecordORM.created_at, ExtractedFieldRecordORM.id)))

    def record_decision(
        self,
        *,
        case_id: str,
        organization_id: str,
        decision: ApplicationCaseDecisionORM,
        target_status: str,
        finding_status: str,
        audit: AuditEventORM,
        notification: NotificationEventORM,
        finding_decisions: list[FindingDecisionORM] | None = None,
        supplement: SupplementRequestORM | None = None,
    ) -> ApplicationCaseDecisionORM:
        """Stage the complete officer decision as one database transaction.

        The caller owns commit/rollback. Returning a previous idempotent result
        does not apply any state change a second time.
        """
        existing = self.decision_by_idempotency(case_id, decision.idempotency_key)
        if existing is not None:
            if existing.decision != decision.decision or existing.note != decision.note:
                raise RepositoryConflict("idempotency key was already used with another decision")
            return existing

        case = self.update_status(case_id, organization_id, target_status, expected_version=decision.expected_version)
        selected = set(decision.selected_finding_ids)
        if selected:
            rows = list(self.session.scalars(select(ValidationFindingORM).where(
                ValidationFindingORM.case_id == case_id,
                ValidationFindingORM.submission_version_id == decision.submission_version_id,
                ValidationFindingORM.id.in_(selected),
            )))
            if {row.id for row in rows} != selected:
                raise RepositoryConflict("selected finding is stale or belongs to another submission")
            for row in rows:
                row.status = finding_status
                row.updated_at = utcnow()

        decision.previous_status = decision.previous_status or case.status
        self.session.add_all([decision, audit, notification, *(finding_decisions or [])])
        if supplement is not None:
            self.session.add(supplement)
        self.session.flush()
        return decision


__all__ = ["ApplicationFilters", "ApplicationRepository", "RepositoryConflict", "RepositoryNotFound"]
