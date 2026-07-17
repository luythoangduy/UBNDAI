"""Tests rule engine trên bộ rule khai_sinh.yaml thật."""

from datetime import UTC, datetime, timedelta

import pytest

from src.models import Case, ChecklistItem, ExtractedDocument, ExtractedField
from src.services.validation.rule_engine import (
    RuleFileError,
    compute_readiness_score,
    load_rules,
    run,
)


def _case(answers=None, form_data=None, checklist=None) -> Case:
    now = datetime.now(UTC)
    return Case(
        id="case_1",
        citizen_id="citizen_1",
        procedure_id="khai_sinh",
        answers=answers or {},
        form_data=form_data or {},
        checklist=checklist or [],
        created_at=now,
        updated_at=now,
    )


def _doc(doc_type: str, fields: dict[str, str]) -> ExtractedDocument:
    return ExtractedDocument(
        id=f"doc_{doc_type}",
        case_id="case_1",
        file_id="file_1",
        doc_type=doc_type,
        doc_type_confidence=0.95,
        fields=[ExtractedField(key=k, value=v, confidence=0.95) for k, v in fields.items()],
        ocr_engine="vision_llm",
        created_at=datetime.now(UTC),
    )


def _recent_date() -> str:
    return (datetime.now(UTC) - timedelta(days=10)).strftime("%d/%m/%Y")


def _issue_ids(report) -> set[str]:
    return {i.rule_id for i in report.issues}


def test_missing_giay_chung_sinh_is_blocking_error():
    case = _case(answers={"sinh_tai_co_so_y_te": True})

    report = run(case, documents=[])

    assert "KS-R1" in _issue_ids(report)
    issue = next(i for i in report.issues if i.rule_id == "KS-R1")
    assert issue.severity == "error" and issue.source == "rule"
    assert report.has_blocking_errors


def test_rule_not_applicable_when_condition_false():
    case = _case(answers={"sinh_tai_co_so_y_te": False})

    report = run(case, documents=[])

    assert "KS-R1" not in _issue_ids(report)


def test_mother_name_match_tolerates_diacritics_and_case():
    docs = [
        _doc("giay_chung_sinh", {"ho_ten_me": "Trần Thị Hoa", "ngay_sinh": _recent_date()}),
        _doc("cccd", {"ho_ten": "TRAN THI HOA"}),
    ]

    report = run(_case(), docs)

    assert "KS-R2" not in _issue_ids(report)


def test_mother_name_mismatch_is_error():
    docs = [
        _doc("giay_chung_sinh", {"ho_ten_me": "Trần Thị Hoa", "ngay_sinh": _recent_date()}),
        _doc("cccd", {"ho_ten": "Nguyễn Thị Lan"}),
    ]

    report = run(_case(), docs)

    issue = next(i for i in report.issues if i.rule_id == "KS-R2")
    assert issue.severity == "error"
    assert "giay_chung_sinh.ho_ten_me" in issue.field_keys


def test_overdue_birth_registration_is_warning():
    old = (datetime.now(UTC) - timedelta(days=90)).strftime("%d/%m/%Y")
    docs = [_doc("giay_chung_sinh", {"ngay_sinh": old})]

    report = run(_case(), docs)

    issue = next(i for i in report.issues if i.rule_id == "KS-R3")
    assert issue.severity == "warning"


def test_unparseable_date_fails_check_conservatively():
    docs = [_doc("giay_chung_sinh", {"ngay_sinh": "ngày mười hai tháng ba"})]

    report = run(_case(), docs)

    assert "KS-R3" in _issue_ids(report)


def test_unmarried_parents_with_father_name_warns():
    case = _case(answers={"ket_hon": False}, form_data={"ho_ten_cha": "Nguyễn Văn Cha"})

    report = run(case, documents=[])

    assert "KS-R4" in _issue_ids(report)


def test_readiness_score_penalizes_errors_warnings_and_missing_items():
    assert compute_readiness_score(0, 0, 0) == 1.0
    assert compute_readiness_score(1, 0, 0) == 0.7
    assert compute_readiness_score(1, 2, 1) == pytest.approx(0.35)
    assert compute_readiness_score(4, 0, 0) == 0.0  # clamp


def test_readiness_score_counts_missing_checklist_items():
    checklist = [
        ChecklistItem(requirement_code="giay_chung_sinh", status="missing"),
        ChecklistItem(requirement_code="cccd_cha_me", status="uploaded"),
    ]
    case = _case(checklist=checklist)

    report = run(case, documents=[])

    # không rule nào fail (không answers, không docs) → chỉ trừ 1 missing
    assert report.readiness_score == pytest.approx(1.0 - 0.15)


def test_load_rules_rejects_unknown_procedure():
    with pytest.raises(RuleFileError):
        load_rules("khong_ton_tai")


def test_run_requires_procedure_id():
    case = _case()
    case = case.model_copy(update={"procedure_id": None})
    with pytest.raises(RuleFileError):
        run(case, [])
