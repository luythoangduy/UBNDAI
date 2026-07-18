"""Contracts shared by the officer application-management API and UI.

The database continues to store the existing lower-case officer statuses.  This
module exposes a stable, presentation-facing vocabulary without changing the
legacy ``ApplicationCase`` contract.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ApplicationStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AI_ANALYZING = "AI_ANALYZING"
    READY_FOR_PROCESSING = "READY_FOR_PROCESSING"
    CAUTION_REVIEW_REQUIRED = "CAUTION_REVIEW_REQUIRED"
    IN_PROCESS = "IN_PROCESS"
    RETURNED_TO_CITIZEN = "RETURNED_TO_CITIZEN"
    RESUBMITTED = "RESUBMITTED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


DecisionType = Literal["CONTINUE_PROCESSING", "RETURN_TO_CITIZEN"]


def project_application_status(internal_status: str, *, has_caution: bool) -> ApplicationStatus:
    """Project an existing officer status without rewriting persisted data."""

    if internal_status in {"draft", "collecting"}:
        return ApplicationStatus.DRAFT
    if internal_status in {"submitted", "submitted_for_precheck"}:
        return ApplicationStatus.SUBMITTED
    if internal_status in {"ocr_processing", "precheck_processing"}:
        return ApplicationStatus.AI_ANALYZING
    if internal_status == "awaiting_officer_review":
        return (
            ApplicationStatus.CAUTION_REVIEW_REQUIRED
            if has_caution
            else ApplicationStatus.READY_FOR_PROCESSING
        )
    if internal_status in {"in_officer_review", "processing"}:
        return ApplicationStatus.IN_PROCESS
    if internal_status in {"needs_citizen_update", "need_more_info"}:
        return ApplicationStatus.RETURNED_TO_CITIZEN
    if internal_status == "resubmitted":
        return ApplicationStatus.RESUBMITTED
    if internal_status in {"precheck_ready", "ready"}:
        return ApplicationStatus.READY_FOR_PROCESSING
    if internal_status in {"done", "completed"}:
        return ApplicationStatus.COMPLETED
    if internal_status == "rejected":
        return ApplicationStatus.REJECTED
    if internal_status == "escalated":
        return ApplicationStatus.ESCALATED
    if internal_status == "cancelled":
        return ApplicationStatus.CANCELLED
    if internal_status == "closed":
        return ApplicationStatus.CLOSED
    return ApplicationStatus.UNKNOWN


class ApplicationDecisionRequest(BaseModel):
    decision: DecisionType
    note: str = Field(default="", max_length=1000)
    anomaly_ids: list[str] = Field(default_factory=list, max_length=50)
    citizen_message: str | None = Field(default=None, max_length=5000)
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=200)

    @field_validator("note", "citizen_message", mode="before")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("anomaly_ids")
    @classmethod
    def unique_anomaly_ids(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("anomaly_ids must be unique")
        return cleaned

    @model_validator(mode="after")
    def validate_decision(self) -> "ApplicationDecisionRequest":
        if self.decision == "CONTINUE_PROCESSING":
            if len(self.note) < 10:
                raise ValueError("note must contain at least 10 characters")
        elif not self.anomaly_ids:
            raise ValueError("return decision requires at least one anomaly")
        elif not (self.citizen_message or "").strip():
            raise ValueError("return decision requires a citizen message")
        return self


__all__ = [
    "ApplicationDecisionRequest",
    "ApplicationStatus",
    "DecisionType",
    "project_application_status",
]
