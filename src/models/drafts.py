"""Contract cho API sinh bản nháp kết quả thủ tục hành chính.

Mỗi mẫu kết quả gắn với đúng ``procedure_id`` và tự khai báo nguồn pháp lý.
Renderer chỉ dựng bản nháp để cán bộ rà soát, không tạo văn bản đã ký/đóng dấu.
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

DraftFieldType = Literal["text", "date", "year"]
DraftValueFormat = Literal["text", "uppercase", "date_numeric", "date_words"]
DraftBlockKind = Literal["title", "text", "field", "row", "spacer"]
LegalSourceRole = Literal[
    "output_template", "content_rule", "amendment", "consolidated_reference"
]


class DraftDocxStyle(BaseModel):
    """Thông số vật lý của file DOCX, khai báo riêng cho từng biểu mẫu."""

    filename: str = Field(pattern=r"^[A-Za-z0-9_.-]+\.docx$")
    page_width_mm: float = Field(gt=0)
    page_height_mm: float = Field(gt=0)
    margin_top_mm: float = Field(ge=0)
    margin_right_mm: float = Field(ge=0)
    margin_bottom_mm: float = Field(ge=0)
    margin_left_mm: float = Field(ge=0)
    body_font: str = Field(min_length=1)
    body_size_pt: float = Field(gt=0)
    line_spacing_pt: float = Field(gt=0)
    title_size_pt: float = Field(gt=0)
    title_color_hex: str = Field(pattern=r"^[0-9A-Fa-f]{6}$")
    notes_font_size_pt: float = Field(gt=0)
    notes_table_width_mm: float = Field(gt=0)
    notes_table_height_mm: float = Field(gt=0)


class DraftLegalSource(BaseModel):
    document_number: str
    title: str
    issuing_authority: str
    role: LegalSourceRole
    provisions: list[str] = Field(default_factory=list)
    source_url: HttpUrl
    effective_from: date | None = None
    applicability_note: str | None = None


class DraftFieldSpec(BaseModel):
    key: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    label: str = Field(min_length=1)
    input_type: DraftFieldType = "text"
    required: bool = True
    normalize: Literal["trim", "uppercase"] = "trim"
    allowed_values: list[str] = Field(default_factory=list)
    pattern: str | None = None
    validation_message: str | None = None
    description: str | None = None


class DraftConditionalGroup(BaseModel):
    name: str
    trigger_fields: list[str] = Field(min_length=1)
    required_fields: list[str] = Field(min_length=1)


class DraftBlockItem(BaseModel):
    field: str
    label: str | None = None
    value_format: DraftValueFormat = "text"


class DraftLayoutBlock(BaseModel):
    kind: DraftBlockKind
    text: str | None = None
    field: str | None = None
    label: str | None = None
    value_format: DraftValueFormat = "text"
    items: list[DraftBlockItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shape(self) -> "DraftLayoutBlock":
        if self.kind in {"title", "text"} and not self.text:
            raise ValueError(f"Block {self.kind} bắt buộc có text")
        if self.kind == "field" and not self.field:
            raise ValueError("Block field bắt buộc có field")
        if self.kind == "row" and not self.items:
            raise ValueError("Block row bắt buộc có items")
        return self


class DraftTemplate(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    procedure_id: str
    output_name: str
    version: str
    is_default: bool = True
    source_checked_on: date
    legal_sources: list[DraftLegalSource] = Field(min_length=1)
    fields: list[DraftFieldSpec] = Field(min_length=1)
    conditional_groups: list[DraftConditionalGroup] = Field(default_factory=list)
    layout: list[DraftLayoutBlock] = Field(min_length=1)
    docx_style: DraftDocxStyle
    disclaimer: str

    @model_validator(mode="after")
    def validate_references(self) -> "DraftTemplate":
        field_keys = [field.key for field in self.fields]
        if len(field_keys) != len(set(field_keys)):
            raise ValueError("DraftFieldSpec.key phải unique trong một template")
        known = set(field_keys)
        referenced = {
            ref
            for block in self.layout
            for ref in ([block.field] if block.field else [])
        }
        referenced.update(
            item.field for block in self.layout for item in block.items
        )
        for group in self.conditional_groups:
            referenced.update(group.trigger_fields)
            referenced.update(group.required_fields)
        unknown = referenced - known
        if unknown:
            raise ValueError(
                "Template tham chiếu field chưa khai báo: "
                + ", ".join(sorted(unknown))
            )
        if not any(source.role == "output_template" for source in self.legal_sources):
            raise ValueError("Template phải có legal source role='output_template'")
        return self


class DraftTemplateInfo(BaseModel):
    id: str
    procedure_id: str
    output_name: str
    version: str
    source_checked_on: date
    legal_sources: list[DraftLegalSource]
    fields: list[DraftFieldSpec]
    docx_style: DraftDocxStyle
    disclaimer: str


class DraftGenerateRequest(BaseModel):
    procedure_id: str
    template_id: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    allow_incomplete: bool = Field(
        default=False,
        description="Cho phép sinh preview có placeholder khi thiếu trường bắt buộc",
    )


class GeneratedDraft(BaseModel):
    id: str
    procedure_id: str
    template_id: str
    output_name: str
    template_version: str
    status: Literal["draft"] = "draft"
    watermark: str
    normalized_values: dict[str, str]
    rendered_text: str
    missing_required_fields: list[str] = Field(default_factory=list)
    ready_for_review: bool
    warnings: list[str] = Field(default_factory=list)
    legal_sources: list[DraftLegalSource]
    disclaimer: str
    generated_at: datetime
