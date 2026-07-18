"""Catalog thủ tục hành chính — nguồn sự thật cho checklist và autofill.

Dữ liệu thật nằm ở ``data/procedures/*.json``, validate bằng các model này.
Owner: Dev A (schema), cả team review khi thay đổi (contract).
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

FieldType = Literal["text", "date", "number", "select", "checkbox"]
AnswerType = Literal["boolean", "integer", "text", "choice"]
ProcedureStatus = Literal["discovered", "extracted", "needs_review", "approved", "published"]


class ClarifyingQuestion(BaseModel):
    """Câu hỏi làm rõ gắn trực tiếp với key được lưu trong ``Case.answers``."""

    key: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    text: str = Field(min_length=1)
    answer_type: AnswerType
    options: list[str] = Field(default_factory=list)
    minimum: int | None = None
    maximum: int | None = None

    @model_validator(mode="after")
    def validate_answer_constraints(self) -> "ClarifyingQuestion":
        if self.answer_type == "choice" and not self.options:
            raise ValueError("Câu hỏi choice bắt buộc phải có options")
        if self.answer_type != "choice" and self.options:
            raise ValueError("options chỉ áp dụng cho câu hỏi choice")
        if self.answer_type != "integer" and (
            self.minimum is not None or self.maximum is not None
        ):
            raise ValueError("minimum/maximum chỉ áp dụng cho câu hỏi integer")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("minimum không được lớn hơn maximum")
        return self


class DocumentRequirement(BaseModel):
    """Một giấy tờ yêu cầu trong thành phần hồ sơ."""

    code: str = Field(description="Mã duy nhất trong thủ tục, vd 'giay_chung_sinh'")
    name: str
    condition: str | None = Field(
        default=None,
        description=(
            "Điều kiện áp dụng (biểu thức trên answers của người dân), "
            "vd \"answers.ket_hon == false\". None = luôn bắt buộc."
        ),
    )
    condition_label: str | None = Field(
        default=None,
        description="Mô tả điều kiện thân thiện với người dân; không lộ expression nội bộ",
    )
    original_required: bool = True
    copies: int = 0
    accepted_doc_types: list[str] = Field(
        default_factory=list,
        description="Các doc_type OCR thoả mãn yêu cầu này, vd ['giay_chung_sinh']",
    )
    notes: str | None = None


class FormField(BaseModel):
    """Một trường trên biểu mẫu, kèm khai báo nguồn OCR để autofill."""

    key: str
    label: str
    type: FieldType = "text"
    required: bool = True
    options: list[str] = Field(
        default_factory=list,
        description="Các giá trị hợp lệ khi type='select'",
    )
    ocr_sources: list[str] = Field(
        default_factory=list,
        description="Đường dẫn trường OCR điền được trường này, vd ['cccd_me.ho_ten']",
    )

    @model_validator(mode="after")
    def validate_options(self) -> "FormField":
        if self.type == "select" and not self.options:
            raise ValueError("Trường select bắt buộc phải có options")
        if self.type != "select" and self.options:
            raise ValueError("options chỉ áp dụng cho trường select")
        if len(self.options) != len(set(self.options)):
            raise ValueError("FormField.options không được trùng lặp")
        return self


class FormTemplate(BaseModel):
    id: str
    name: str
    fields: list[FormField]


class Procedure(BaseModel):
    """Một thủ tục hành chính trong catalog."""

    id: str = Field(description="Mã nội bộ, vd 'khai_sinh'")
    status: ProcedureStatus = Field(
        default="published",
        description="Chỉ approved/published mới được dùng cho workflow có tác động pháp lý",
    )
    locality_code: str = "national"
    national_code: str | None = Field(
        default=None, description="Mã trên Cổng DVC quốc gia, vd '1.001193'"
    )
    name: str
    aliases: list[str] = Field(default_factory=list)
    example_queries: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    required_token_groups: list[list[str]] = Field(default_factory=list)
    agency: str = Field(description="Cơ quan thực hiện, vd 'UBND cấp xã'")
    legal_basis: list[str] = Field(
        default_factory=list, description="Căn cứ pháp lý (tên văn bản) — dùng cho citation"
    )
    processing_days: int | None = None
    fee_vnd: int | None = None
    clarifying_questions: list[ClarifyingQuestion] = Field(
        default_factory=list,
        description="Câu hỏi làm rõ có key/type để parse và chỉ hỏi phần còn thiếu",
    )
    requirements: list[DocumentRequirement]
    form_templates: list[FormTemplate] = Field(default_factory=list)
    source_url: str | None = None
    source_hash: str | None = None
    retrieved_at: datetime | None = None

    @model_validator(mode="after")
    def condition_keys_have_questions(self) -> "Procedure":
        question_key_list = [question.key for question in self.clarifying_questions]
        question_keys = set(question_key_list)
        condition_keys = {
            match.group(1)
            for requirement in self.requirements
            if requirement.condition
            for match in [
                re.match(
                    r"^\s*answers\.([A-Za-z_][A-Za-z0-9_]*)\s*(?:==|!=)",
                    requirement.condition,
                )
            ]
            if match
        }
        missing = condition_keys - question_keys
        if missing:
            raise ValueError(
                "Các condition key chưa có clarifying question: "
                + ", ".join(sorted(missing))
            )
        if len(question_key_list) != len(question_keys):
            raise ValueError("Clarifying question key phải unique trong một thủ tục")
        requirement_codes = [requirement.code for requirement in self.requirements]
        if len(requirement_codes) != len(set(requirement_codes)):
            raise ValueError("DocumentRequirement.code phải unique trong một thủ tục")
        template_ids = [template.id for template in self.form_templates]
        if len(template_ids) != len(set(template_ids)):
            raise ValueError("FormTemplate.id phải unique trong một thủ tục")
        if any(len(set(group)) < 2 for group in self.required_token_groups):
            raise ValueError("Mỗi required_token_group phải có ít nhất hai token")
        return self


class ProcedureSummary(BaseModel):
    id: str
    national_code: str | None = None
    name: str
    agency: str
    locality_code: str = "national"
    status: ProcedureStatus
    source_url: str | None = None


class ProcedureCapabilities(BaseModel):
    chat: bool = True
    checklist: bool = False
    dynamic_form: bool = False
    ocr_autofill: bool = False
    legal_validation: bool = False
    official_draft: bool = False
    requires_human_review: bool = True


class ProcedureFormSchema(BaseModel):
    procedure_id: str
    template_id: str
    title: str
    fields: list[FormField]
    clarifying_questions: list[ClarifyingQuestion] = Field(default_factory=list)
