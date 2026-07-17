"""Conservative quality gate for normalized procedure candidates."""

from src.models import NormalizedProcedureMetadata, ProcedureDocument, QualityReport


def evaluate(
    document: ProcedureDocument,
    normalized: NormalizedProcedureMetadata | None,
    *,
    confidence_threshold: float = 0.9,
) -> QualityReport:
    issues: list[str] = []
    chat_ready = bool(document.sections) and all(
        section.source_url and section.source_hash for section in document.sections
    )
    if not chat_ready:
        issues.append("Raw sections thiếu nội dung hoặc provenance")
    if normalized is None:
        issues.append("Chưa chạy được LLM structured extraction")
        return QualityReport(
            chat_ready=chat_ready,
            score=1.0 if chat_ready else 0.0,
            issues=issues,
        )
    if normalized.confidence < confidence_threshold:
        issues.append(f"Confidence {normalized.confidence:.2f} dưới ngưỡng {confidence_threshold:.2f}")
    if normalized.agency is None:
        issues.append("Thiếu cơ quan thực hiện")
    if not normalized.requirements:
        issues.append("Thiếu thành phần hồ sơ chuẩn hoá")
    if any(item.confidence < confidence_threshold for item in normalized.fees):
        issues.append("Có mức phí confidence thấp")
    fee_values = {item.value.strip().casefold() for item in normalized.fees}
    if len(fee_values) > 1:
        issues.append("Có nhiều mức phí; cần cán bộ xác định phạm vi/địa phương áp dụng")
    time_values = {item.value.strip().casefold() for item in normalized.processing_times}
    if len(time_values) > 1:
        issues.append("Có nhiều thời hạn xử lý; cần cán bộ xác định điều kiện áp dụng")
    # Dù đạt chất lượng, bước duyệt của cán bộ vẫn bắt buộc trước workflow publish.
    issues.append("Bắt buộc cán bộ duyệt trước khi bật checklist/form/validation")
    return QualityReport(
        status="needs_review",
        chat_ready=chat_ready,
        workflow_ready=False,
        score=normalized.confidence,
        issues=issues,
    )
