"""Model vận hành nội bộ: phân công, tóm tắt, metrics, anomaly. Owner: Dev C."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MetricName = Literal["error_rate", "late_rate", "volume", "avg_readiness"]


class Assignment(BaseModel):
    case_id: str
    officer_id: str
    assigned_at: datetime
    reason: str = Field(description="Vd 'round_robin:linh_vuc_ho_tich' — để giải thích được")
    priority: int = Field(default=0, description="Cao hơn = xử lý trước; hồ sơ uncertain được cộng điểm")


class CaseSummary(BaseModel):
    """Tóm tắt hồ sơ do LLM sinh cho cán bộ — chỉ mô tả, không quyết định."""

    case_id: str
    summary: str
    open_issues: list[str] = Field(default_factory=list)
    generated_at: datetime


class DailyDigest(BaseModel):
    officer_id: str
    date: str = Field(description="YYYY-MM-DD")
    summary: str
    handled_count: int
    pending_count: int
    flagged_case_ids: list[str] = Field(default_factory=list)


class MetricPoint(BaseModel):
    metric: MetricName
    value: float
    bucket_start: datetime = Field(description="Đầu khung giờ/ngày của điểm dữ liệu")
    procedure_id: str | None = Field(default=None, description="None = toàn hệ thống")


class AnomalyAlert(BaseModel):
    metric: MetricName
    value: float
    expected_low: float
    expected_high: float
    zscore: float
    severity: Literal["warning", "critical"]
    procedure_id: str | None = None
    detected_at: datetime
    message: str = Field(description="Vd 'Tỷ lệ hồ sơ lỗi 18% — gấp 3 lần trung bình cùng khung giờ'")
