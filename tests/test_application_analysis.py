from datetime import date

from src.services.application_analysis import (
    classify_application,
    detect_duplicates,
    normalize_ai_anomalies,
    validate_citizen_id,
    validate_cross_document,
    validate_date,
    validate_required_documents,
    validate_required_fields,
    validate_template,
)


CATALOG = [
    {"code": "BIRTH_REGISTRATION", "name": "Đăng ký khai sinh", "keywords": ["khai sinh", "giấy chứng sinh"]},
    {"code": "MARRIAGE_REGISTRATION", "name": "Đăng ký kết hôn", "keywords": ["kết hôn"]},
]


def test_application_classifier_returns_grounded_type_and_evidence():
    result = classify_application("Tôi cần làm giấy khai sinh cho con", CATALOG)
    assert result.code == "BIRTH_REGISTRATION"
    assert result.confidence > 0.5
    assert result.evidence
    assert result.method == "keyword_catalog"


def test_application_classifier_returns_unknown_when_no_catalog_match():
    result = classify_application("Tôi cần hỏi một việc không có trong catalog", CATALOG)
    assert result.code == "UNKNOWN"
    assert result.needs_manual_review is True


def test_citizen_id_requires_exactly_twelve_digits():
    assert validate_citizen_id("001234567890")
    assert not validate_citizen_id("00123456789")
    assert not validate_citizen_id("00123456789A")


def test_required_fields_return_stable_anomaly_codes():
    issues = validate_required_fields({"citizen_id": "  "}, ["citizen_id", "child_name"])
    assert [issue.code for issue in issues] == ["MISSING_REQUIRED_FIELD", "MISSING_REQUIRED_FIELD"]


def test_document_date_and_template_validators_are_deterministic():
    assert validate_required_documents(["cccd"], ["cccd", "to_khai"])[0].code == "MISSING_REQUIRED_DOCUMENT"
    assert validate_date("31/02/2026", "ngay_sinh")[0].code == "INVALID_DATE"
    assert validate_date("2099-01-01", "ngay_sinh", today=date(2026, 1, 1))[0].code == "FUTURE_DATE"
    assert validate_template("KS-01", "1", "KS-01", "2")[0].code == "WRONG_TEMPLATE_VERSION"


def test_duplicate_cross_document_and_ai_safety():
    assert detect_duplicates(["a", "a"])[0].code == "DUPLICATE_DOCUMENT"
    assert validate_cross_document([{"cccd": "123"}, {"cccd": "456"}])[0].field_name == "cccd"
    ai_issue = normalize_ai_anomalies([{"code": "X", "message": "x", "severity": "error"}])[0]
    assert ai_issue.severity == "warning"
