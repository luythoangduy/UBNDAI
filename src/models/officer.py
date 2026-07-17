"""Contracts for the versioned officer-review workflow."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OfficerCaseStatus = Literal[
    "draft",
    "collecting",
    "submitted_for_precheck",
    "ocr_processing",
    "precheck_processing",
    "awaiting_officer_review",
    "in_officer_review",
    "needs_citizen_update",
    "resubmitted",
    "escalated",
    "precheck_ready",
    "submitted",
    "processing",
    "ready",
    "need_more_info",
    "done",
    "rejected",
    "cancelled",
    "closed",
]


class ApplicationCase(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str
    case_code: str
    organization_id: str
    citizen_id: str
    procedure_id: str
    procedure_version_id: str
    status: OfficerCaseStatus = "draft"
    source_channel: str = "citizen_portal"
    assigned_to: str | None = None
    assigned_at: datetime | None = None
    priority: int = Field(default=0, ge=0, le=100)
    submitted_at: datetime | None = None
    sla_due_at: datetime | None = None
    current_submission_version: int = Field(default=1, ge=1)
    version: int = Field(default=1, ge=1)
    form_data: dict[str, Any] = Field(default_factory=dict)
    checklist: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CaseSubmissionVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    case_id: str
    version: int = Field(ge=1)
    form_data: dict[str, Any] = Field(default_factory=dict)
    checklist_snapshot: dict[str, Any] = Field(default_factory=dict)
    procedure_version_id: str
    procedure_rule_version: str
    created_at: datetime
    created_by: str | None = None
    source: str = "citizen_portal"


class CaseDocument(BaseModel):
    id: str
    case_id: str
    submission_version_id: str
    document_type: str
    file_uri: str
    object_key: str | None = None
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0, le=20 * 1024 * 1024)
    sha256: str | None = None
    ocr_status: Literal["upload_pending", "uploaded", "scanning", "ocr_processing", "ready", "rejected", "pending", "processing", "completed", "failed", "manual_review_required"] = "upload_pending"
    ocr_engine: str | None = None
    ocr_version: str | None = None
    uploaded_at: datetime


class ExtractedFieldRecord(BaseModel):
    id: str
    document_id: str
    field_key: str
    raw_value: str
    normalized_value: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    page: int | None = Field(default=None, ge=1)
    bounding_box: list[float] | None = None
    review_status: Literal["unreviewed", "confirmed", "edited", "needs_human_review"] = "unreviewed"
    previous_value: str | None = None


class ValidationFinding(BaseModel):
    id: str
    case_id: str
    submission_version_id: str
    type: str
    severity: Literal["error", "warning", "info"]
    source: Literal["rule", "ai"]
    message: str
    suggestion: str | None = None
    rule_id: str | None = None
    rule_version: int | str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: Literal["open", "accepted", "dismissed", "escalated", "superseded"] = "open"
    field_keys: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime

    @model_validator(mode="after")
    def ai_cannot_error(self) -> "ValidationFinding":
        if self.source == "ai" and self.severity == "error":
            raise ValueError("AI findings cannot have error severity")
        return self


class OfficerDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    finding_id: str
    officer_id: str
    decision: Literal["accepted", "dismissed", "escalated", "request_update"]
    finding_severity: Literal["error", "warning", "info"] | None = None
    reason: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def error_dismiss_requires_reason(self) -> "OfficerDecision":
        if self.decision == "dismissed" and self.finding_severity == "error" and not (self.reason or "").strip():
            raise ValueError("Dismissing an error finding requires a reason")
        return self


class SupplementRequest(BaseModel):
    id: str
    case_id: str
    submission_version_id: str
    created_by: str
    public_message: str = Field(min_length=1)
    finding_ids: list[str] = Field(min_length=1)
    due_at: datetime | None = None
    status: Literal["draft", "sent", "fulfilled", "cancelled"] = "draft"
    created_at: datetime

    @field_validator("public_message")
    @classmethod
    def non_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("public_message must not be blank")
        return value.strip()


class CaseAuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    case_id: str
    actor_id: str
    organization_id: str
    event_type: str
    object_type: str
    object_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class OfficerIdentity(BaseModel):
    user_id: str
    organization_id: str = Field(min_length=1)
    roles: set[str] = Field(min_length=1)
    active: bool = True


class TokenClaims(BaseModel):
    user_id: str
    organization_id: str = Field(min_length=1)
    roles: set[str] = Field(min_length=1)
    exp: int
