"""Public contracts for citizen intake and submission."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class CitizenCaseCreate(BaseModel):
    procedure_id: str = Field(min_length=1, max_length=100)
    locality_code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")


class CitizenCaseUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    answers: dict[str, Any] | None = None
    form_data: dict[str, Any] | None = None


class UploadIntentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    size_bytes: int = Field(gt=0, le=10 * 1024 * 1024)

    @field_validator("content_type")
    @classmethod
    def supported_content_type(cls, value: str) -> str:
        if value not in {"image/jpeg", "image/png"}:
            raise ValueError("Only JPEG and PNG images are supported for OCR")
        return value

    @field_validator("filename")
    @classmethod
    def supported_extension(cls, value: str) -> str:
        if not value.casefold().endswith((".jpg", ".jpeg", ".png")):
            raise ValueError("Unsupported file extension")
        return value


class UploadCompleteRequest(BaseModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CitizenSubmitRequest(BaseModel):
    expected_version: int = Field(ge=1)
    consent_version: str = Field(min_length=1, max_length=100)
    consent_accepted: bool


class RoutingDecision(BaseModel):
    procedure_id: str
    locality_code: str
    organization_id: str
    matched_rule: str


class ConsentRecord(BaseModel):
    case_id: str
    citizen_id: str
    consent_version: str
    accepted: bool


class UploadIntentResponse(BaseModel):
    document_id: str
    upload_url: str
    expires_in: int = 900
