"""Contract API chat guidance. Owner: Dev A (nội dung), Dev C (frontend tiêu thụ)."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Citation(BaseModel):
    index: int = Field(ge=1)
    procedure_id: str
    chunk_id: str
    section: str
    label: str = Field(description="Vd 'Thủ tục Đăng ký khai sinh — Luật Hộ tịch 2014'")
    excerpt: str
    source_url: str | None = None


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
    clarifying_questions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
