"""Kết quả kiểm tra hồ sơ trước khi nộp. Owner: Dev B.

Bất biến quan trọng:
- ``severity="error"`` chỉ được sinh từ rule engine (source="rule").
- AI checker chỉ sinh warning/info.
- readiness_score là hàm deterministic trên issues + checklist, không phải LLM chấm.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Severity = Literal["error", "warning", "info"]
IssueSource = Literal["rule", "ai"]


class ValidationIssue(BaseModel):
    rule_id: str = Field(description="ID rule trong rules/*.yaml, hoặc 'ai.<loại>' với AI checker")
    severity: Severity
    message: str = Field(description="Thông điệp tiếng Việt hiển thị cho người dân")
    field_keys: list[str] = Field(
        default_factory=list, description="Các trường liên quan, vd ['giay_chung_sinh.ho_ten_me']"
    )
    suggestion: str | None = Field(default=None, description="Hướng dẫn cách sửa")
    source: IssueSource

    @model_validator(mode="after")
    def _ai_cannot_error(self) -> "ValidationIssue":
        if self.source == "ai" and self.severity == "error":
            raise ValueError("AI checker không được sinh severity=error (AGENTS.md §5)")
        return self


class ValidationReport(BaseModel):
    case_id: str
    issues: list[ValidationIssue] = Field(default_factory=list)
    readiness_score: float = Field(ge=0.0, le=1.0)
    checked_at: datetime

    @property
    def has_blocking_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)
