"""Catalog thủ tục hành chính — nguồn sự thật cho checklist và autofill.

Dữ liệu thật nằm ở ``data/procedures/*.json``, validate bằng các model này.
Owner: Dev A (schema), cả team review khi thay đổi (contract).
"""

from typing import Literal

from pydantic import BaseModel, Field

FieldType = Literal["text", "date", "number", "select", "checkbox"]


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
    ocr_sources: list[str] = Field(
        default_factory=list,
        description="Đường dẫn trường OCR điền được trường này, vd ['cccd_me.ho_ten']",
    )


class FormTemplate(BaseModel):
    id: str
    name: str
    fields: list[FormField]


class Procedure(BaseModel):
    """Một thủ tục hành chính trong catalog."""

    id: str = Field(description="Mã nội bộ, vd 'khai_sinh'")
    national_code: str | None = Field(
        default=None, description="Mã trên Cổng DVC quốc gia, vd '1.001193'"
    )
    name: str
    agency: str = Field(description="Cơ quan thực hiện, vd 'UBND cấp xã'")
    legal_basis: list[str] = Field(
        default_factory=list, description="Căn cứ pháp lý (tên văn bản) — dùng cho citation"
    )
    processing_days: int | None = None
    fee_vnd: int | None = None
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Câu hỏi làm rõ để xác định điều kiện áp dụng requirement",
    )
    requirements: list[DocumentRequirement]
    form_templates: list[FormTemplate] = Field(default_factory=list)
    source_url: str | None = None
