"""Phát hiện bất thường chuỗi thời gian trên metrics vận hành. Owner: Dev C.

MVP: baseline = rolling mean/std của cùng-khung-giờ-trong-tuần (14–28 ngày gần nhất);
cảnh báo khi |z| > 2 (warning) hoặc > 3 (critical). Cần >= 7 điểm baseline mới xét.
Metrics ghi bởi job định kỳ (metrics.py): error_rate, late_rate, volume, avg_readiness.
Nâng cấp STL/Prophet sau MVP nếu số liệu có seasonality phức tạp.
"""

from src.models import AnomalyAlert, MetricPoint


def detect(history: list[MetricPoint], current: MetricPoint) -> AnomalyAlert | None:
    raise NotImplementedError  # TODO(C) Sprint 3
