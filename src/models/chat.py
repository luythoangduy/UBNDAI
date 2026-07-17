"""Contract API chat guidance. Owner: Dev A (nội dung), Dev C (frontend tiêu thụ)."""

from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    procedure_id: str
    label: str = Field(description="Vd 'Thủ tục Đăng ký khai sinh — Luật Hộ tịch 2014'")
    source_url: str | None = None


class ChatRequest(BaseModel):
    case_id: str | None = Field(default=None, description="None = mở hội thoại/case mới")
    message: str


class ChatResponse(BaseModel):
    case_id: str
    reply: str
    kind: Literal["clarify", "checklist", "answer", "fallback"] = Field(
        description="Node cuối cùng của graph sinh ra reply — frontend render khác nhau"
    )
    clarifying_questions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
