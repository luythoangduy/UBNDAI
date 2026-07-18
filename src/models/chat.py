"""Contract API chat guidance. Owner: Dev A (nội dung), Dev C (frontend tiêu thụ)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

IntentName = Literal[
    "procedure_discovery",
    "switch_procedure",
    "switch_confirmation",
    "clarification_answer",
    "checklist",
    "fee",
    "processing_time",
    "agency",
    "legal_basis",
    "forms",
    "status_tracking",
    "submission",
    "document_upload",
    "capabilities",
    "greeting",
    "thanks",
    "out_of_scope",
    "general_question",
    "unknown",
]


class Citation(BaseModel):
    index: int = Field(ge=1)
    procedure_id: str
    chunk_id: str
    section: str
    label: str = Field(description="Vd 'Thủ tục Đăng ký khai sinh — Luật Hộ tịch 2014'")
    excerpt: str
    source_url: str | None = None


ChatActionKind = Literal["send_message", "start_form", "open_url"]
EvidenceStatus = Literal["ready", "cache_hit", "fallback", "unavailable"]


class ChatAction(BaseModel):
    id: str
    label: str
    description: str
    kind: ChatActionKind
    value: str
    icon: Literal["search", "checklist", "clock", "template", "form", "source"]
    primary: bool = False


class TemplateCitation(BaseModel):
    document_number: str
    title: str
    issuing_authority: str
    role: str
    source_url: str
    official: bool
    priority: int = Field(ge=0)


class ChatTemplateResource(BaseModel):
    template_id: str
    title: str
    version: str
    source_checked_on: str
    field_count: int = Field(ge=0)
    source_url: str
    source_label: str
    official_source: bool
    citations: list[TemplateCitation] = Field(default_factory=list)


class EvidenceStep(BaseModel):
    id: str
    label: str
    detail: str
    status: EvidenceStatus
    source_url: str | None = None


class ChatCacheInfo(BaseModel):
    backend: Literal["redis", "memory", "none"] = "none"
    status: Literal["hit", "miss", "unavailable"] = "unavailable"
    ttl_seconds: int = Field(default=0, ge=0)


class ChatStarterResponse(BaseModel):
    reply: str
    actions: list[ChatAction] = Field(default_factory=list)
    evidence: list[EvidenceStep] = Field(default_factory=list)
    cache: ChatCacheInfo = Field(default_factory=ChatCacheInfo)


class ChatRequest(BaseModel):
    case_id: str | None = Field(default=None, description="None = mở hội thoại/case mới")
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tin nhắn không được để trống")
        return value


class ChatResponse(BaseModel):
    case_id: str
    reply: str
    kind: Literal["clarify", "checklist", "answer", "fallback"] = Field(
        description="Node cuối cùng của graph sinh ra reply — frontend render khác nhau"
    )
    primary_intent: IntentName = "unknown"
    detected_intents: list[IntentName] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    procedure_id: str | None = None
    actions: list[ChatAction] = Field(default_factory=list)
    templates: list[ChatTemplateResource] = Field(default_factory=list)
    evidence: list[EvidenceStep] = Field(default_factory=list)
    cache: ChatCacheInfo = Field(default_factory=ChatCacheInfo)


class ChatHistoryMessage(BaseModel):
    id: int = Field(ge=1)
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    response: ChatResponse | None = Field(
        default=None,
        description="Structured assistant response when recorded; absent for legacy messages.",
    )


class ChatHistoryResponse(BaseModel):
    case_id: str
    procedure_id: str | None = None
    status: str
    messages: list[ChatHistoryMessage] = Field(default_factory=list)
