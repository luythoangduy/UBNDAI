"""Small, explainable z-score detector for operational metrics."""

from math import sqrt

from src.models import AnomalyAlert, MetricPoint


def detect(history: list[MetricPoint], current: MetricPoint) -> AnomalyAlert | None:
    comparable = [point.value for point in history if point.metric == current.metric and point.procedure_id == current.procedure_id]
    if len(comparable) < 7:
        return None
    mean = sum(comparable) / len(comparable)
    variance = sum((value - mean) ** 2 for value in comparable) / len(comparable)
    deviation = sqrt(variance)
    if deviation == 0:
        return None
    zscore = (current.value - mean) / deviation
    if abs(zscore) <= 2:
        return None
    return AnomalyAlert(
        metric=current.metric,
        value=current.value,
        expected_low=mean - 2 * deviation,
        expected_high=mean + 2 * deviation,
        zscore=zscore,
        severity="critical" if abs(zscore) > 3 else "warning",
        procedure_id=current.procedure_id,
        detected_at=current.bucket_start,
        message=f"{current.metric} lệch {abs(zscore):.1f} độ lệch chuẩn so với baseline.",
    )
