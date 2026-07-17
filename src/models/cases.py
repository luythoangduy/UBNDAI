"""Hồ sơ (Case) — trạng thái trung tâm mà cả 3 workstream đọc/ghi.

Owner: Dev C (persistence), contract chung — đổi phải tag cả team.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CaseStatus = Literal[
    "draft",  # đang chat/làm rõ, chưa có checklist
    "collecting",  # có checklist, đang upload giấy tờ
    "ready",  # readiness_score đạt ngưỡng, sẵn sàng nộp
    "submitted",  # đã handoff sang cổng DVC
    "processing",  # cán bộ đang xử lý
    "need_more_info",  # cán bộ yêu cầu bổ sung
    "done",
    "rejected",
]
PendingAction = Literal[
    "select_procedure", "answer_clarification", "confirm_switch_procedure"
]

ChecklistItemStatus = Literal[
    "missing",  # chưa có giấy tờ
    "uploaded",  # đã upload, chờ OCR/kiểm tra
    "verified",  # rule engine xác nhận đạt
    "uncertain",  # AI không chắc — cần cán bộ xác nhận
    "not_applicable",  # điều kiện áp dụng không khớp trường hợp này
]


class ChecklistItem(BaseModel):
    requirement_code: str = Field(description="Trỏ về DocumentRequirement.code")
    status: ChecklistItemStatus = "missing"
    document_id: str | None = Field(
        default=None, description="ExtractedDocument.id thoả mãn item này"
    )
    note: str | None = None


class Case(BaseModel):
    id: str
    citizen_id: str
    procedure_id: str | None = Field(
        default=None, description="None khi còn ở giai đoạn clarify/identify"
    )
    answers: dict[str, Any] = Field(
        default_factory=dict, description="Câu trả lời làm rõ, key khớp điều kiện trong catalog"
    )
    pending_action: PendingAction | None = None
    pending_procedure_ids: list[str] = Field(default_factory=list)
    pending_question_keys: list[str] = Field(default_factory=list)
    pending_switch_query: str | None = None
    checklist: list[ChecklistItem] = Field(default_factory=list)
    form_data: dict[str, Any] = Field(
        default_factory=dict, description="Dữ liệu biểu mẫu đã autofill/người dân sửa"
    )
    readiness_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Do ValidationReport tính — nơi khác chỉ đọc"
    )
    status: CaseStatus = "draft"
    assigned_officer_id: str | None = None
    version: int = Field(default=0, ge=0, description="Optimistic locking cho cập nhật case")
    created_at: datetime
    updated_at: datetime
    due_at: datetime | None = Field(default=None, description="Hạn xử lý — đầu vào cho late_rate")


class CaseCreate(BaseModel):
    citizen_id: str
    procedure_id: str | None = None


class CaseUpdate(BaseModel):
    answers: dict[str, Any] | None = None
    form_data: dict[str, Any] | None = None
    status: CaseStatus | None = None
    assigned_officer_id: str | None = None
    pending_action: PendingAction | None = None
    pending_procedure_ids: list[str] | None = None
    pending_question_keys: list[str] | None = None
    pending_switch_query: str | None = None
