"""Pydantic contracts — single source of truth giữa 3 workstream.

Đổi bất kỳ model nào ở đây = đổi contract → PR phải tag cả team (TEAM_PLAN §4).
"""

from src.models.cases import Case, CaseCreate, CaseStatus, CaseUpdate, ChecklistItem
from src.models.chat import ChatRequest, ChatResponse, Citation, IntentName
from src.models.documents import ExtractedDocument, ExtractedField
from src.models.ops import (
    AnomalyAlert,
    Assignment,
    CaseSummary,
    DailyDigest,
    MetricPoint,
)
from src.models.procedures import (
    ClarifyingQuestion,
    DocumentRequirement,
    FormField,
    FormTemplate,
    Procedure,
)
from src.models.validation import ValidationIssue, ValidationReport
from src.models.citizen import (
    CitizenCaseCreate,
    CitizenCaseUpdate,
    CitizenSubmitRequest,
    ConsentRecord,
    RoutingDecision,
    UploadCompleteRequest,
    UploadIntentRequest,
    UploadIntentResponse,
)
from src.models.officer import (
    ApplicationCase,
    CaseAuditEvent,
    CaseDocument,
    CaseSubmissionVersion,
    ExtractedFieldRecord,
    OfficerDecision,
    OfficerIdentity,
    SupplementRequest,
    TokenClaims,
    ValidationFinding,
)

__all__ = [
    "AnomalyAlert",
    "Assignment",
    "Case",
    "CaseCreate",
    "CaseStatus",
    "CaseSummary",
    "CaseUpdate",
    "ChatRequest",
    "ChatResponse",
    "ChecklistItem",
    "ClarifyingQuestion",
    "Citation",
    "DailyDigest",
    "DocumentRequirement",
    "ExtractedDocument",
    "ExtractedField",
    "FormField",
    "FormTemplate",
    "IntentName",
    "MetricPoint",
    "Procedure",
    "ValidationIssue",
    "ValidationReport",
    "ApplicationCase",
    "CaseAuditEvent",
    "CaseDocument",
    "CaseSubmissionVersion",
    "ExtractedFieldRecord",
    "OfficerDecision",
    "OfficerIdentity",
    "SupplementRequest",
    "TokenClaims",
    "ValidationFinding",
    "CitizenCaseCreate",
    "CitizenCaseUpdate",
    "CitizenSubmitRequest",
    "ConsentRecord",
    "RoutingDecision",
    "UploadCompleteRequest",
    "UploadIntentRequest",
    "UploadIntentResponse",
]
