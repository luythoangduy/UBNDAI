"""Kết quả OCR một giấy tờ. Owner: Dev B."""

from datetime import datetime

from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    key: str = Field(description="Tên trường chuẩn hoá, vd 'ho_ten', 'ngay_sinh'")
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    edited_by_user: bool = Field(
        default=False, description="True nếu người dân đã sửa tay giá trị OCR"
    )


class ExtractedDocument(BaseModel):
    id: str
    case_id: str
    file_id: str = Field(description="Trỏ về file upload gốc trong storage")
    doc_type: str = Field(description="Loại giấy tờ, vd 'cccd', 'giay_chung_sinh'")
    doc_type_confidence: float = Field(ge=0.0, le=1.0)
    fields: list[ExtractedField] = Field(default_factory=list)
    raw_text: str | None = None
    needs_human_review: bool = Field(
        default=False,
        description="True khi doc_type hoặc trường bất kỳ dưới ngưỡng confidence",
    )
    ocr_engine: str = Field(description="'paddleocr' | 'google_vision'")
    created_at: datetime

    def field_map(self) -> dict[str, str]:
        """Map ``'<doc_type>.<key>' -> value`` dùng cho autofill và rule engine."""
        return {f"{self.doc_type}.{f.key}": f.value for f in self.fields}
