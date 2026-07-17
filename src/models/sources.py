"""Contracts for discovered official sources and review-gated normalization."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProcedureSection(BaseModel):
    procedure_id: str
    procedure_name: str
    section: Literal[
        "tong_quan",
        "thanh_phan_ho_so",
        "cach_thuc_thuc_hien",
        "thoi_han",
        "phi_le_phi",
        "dieu_kien",
        "can_cu_phap_ly",
        "bieu_mau",
    ]
    content: str = Field(min_length=1)
    locality_code: str = "national"
    source_url: str
    retrieved_at: datetime
    source_hash: str


class ProcedureDocument(BaseModel):
    procedure_id: str
    procedure_name: str
    locality_code: str = "national"
    source_url: str
    retrieved_at: datetime
    source_hash: str
    sections: list[ProcedureSection]


class ProvenancedValue(BaseModel):
    value: str
    source_url: str
    source_quote: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)


class NormalizedProcedureMetadata(BaseModel):
    procedure_id: str
    name: ProvenancedValue
    national_code: ProvenancedValue | None = None
    agency: ProvenancedValue | None = None
    requirements: list[ProvenancedValue] = Field(default_factory=list)
    fees: list[ProvenancedValue] = Field(default_factory=list)
    processing_times: list[ProvenancedValue] = Field(default_factory=list)
    forms: list[ProvenancedValue] = Field(default_factory=list)
    legal_basis: list[ProvenancedValue] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class QualityReport(BaseModel):
    status: Literal["needs_review", "approved"] = "needs_review"
    chat_ready: bool
    workflow_ready: bool = False
    score: float = Field(ge=0, le=1)
    issues: list[str] = Field(default_factory=list)


class SyncResult(BaseModel):
    discovered: int = 0
    changed: int = 0
    unchanged: int = 0
    failed: int = 0
    review_items: list[str] = Field(default_factory=list)
