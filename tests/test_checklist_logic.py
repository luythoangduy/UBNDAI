"""Checklist deterministic: eval_condition + build_checklist (AGENTS.md §5, §6)."""

import pytest

from src.models import ClarifyingQuestion
from src.services import catalog
from src.services.checklist import (
    build_checklist,
    eval_condition,
    unresolved_condition_keys,
)
from src.services.clarification import extract_answers


def _khai_sinh():
    procedure = catalog.get_procedure("khai_sinh")
    assert procedure is not None
    return procedure


def test_eval_condition_without_condition_is_always_true():
    assert eval_condition(None, {}) is True


def test_eval_condition_true_false_and_missing():
    condition = "answers.ket_hon == true"
    assert eval_condition(condition, {"ket_hon": True}) is True
    assert eval_condition(condition, {"ket_hon": False}) is False
    assert eval_condition(condition, {}) is None  # chưa đủ dữ liệu


def test_eval_condition_accepts_vietnamese_yes_no_strings():
    assert eval_condition("answers.ket_hon == true", {"ket_hon": "có"}) is True
    assert eval_condition("answers.ket_hon == true", {"ket_hon": "chưa"}) is False
    assert eval_condition("answers.ket_hon != true", {"ket_hon": "không"}) is True


def test_eval_condition_rejects_malformed_expression():
    with pytest.raises(ValueError):
        eval_condition("__import__('os')", {})


def test_build_checklist_applies_answers():
    items = build_checklist(
        _khai_sinh(), {"sinh_tai_co_so_y_te": True, "ket_hon": False}
    )
    by_code = {item.requirement_code: item for item in items}
    assert by_code["giay_chung_sinh"].status == "missing"
    assert by_code["van_ban_nguoi_lam_chung"].status == "not_applicable"
    assert by_code["giay_dang_ky_ket_hon"].status == "not_applicable"
    assert by_code["to_khai_khai_sinh"].status == "missing"


def test_build_checklist_keeps_unresolved_items_with_note():
    items = build_checklist(_khai_sinh(), {})
    by_code = {item.requirement_code: item for item in items}
    assert by_code["giay_chung_sinh"].status == "missing"
    assert "cần làm rõ" in (by_code["giay_chung_sinh"].note or "")


def test_every_item_traces_to_requirement_code():
    procedure = _khai_sinh()
    codes = {req.code for req in procedure.requirements}
    for item in build_checklist(procedure, {}):
        assert item.requirement_code in codes


def test_unresolved_condition_keys():
    procedure = _khai_sinh()
    assert set(unresolved_condition_keys(procedure, {})) == {
        "sinh_tai_co_so_y_te",
        "ket_hon",
    }
    assert unresolved_condition_keys(
        procedure, {"sinh_tai_co_so_y_te": True, "ket_hon": True}
    ) == []


def test_specific_negative_answer_does_not_fill_other_boolean():
    questions = _khai_sinh().clarifying_questions
    result = extract_answers("không kết hôn", questions)
    assert result == {"ket_hon": False}
    assert "sinh_tai_co_so_y_te" not in result


def test_generic_boolean_only_answers_first_pending_question():
    questions = _khai_sinh().clarifying_questions
    assert extract_answers("có", questions) == {"ket_hon": True}


@pytest.mark.parametrize(
    "message",
    ["Bé sinh ngày 12/7/2026", "CCCD của mẹ có đuôi 123456"],
)
def test_integer_parser_does_not_take_unrelated_number(message):
    questions = _khai_sinh().clarifying_questions
    assert "so_ngay_tu_khi_sinh" not in extract_answers(message, questions)


def test_choice_and_single_text_have_deterministic_fallback():
    choice = ClarifyingQuestion(
        key="noi_nop",
        text="Chọn nơi nộp",
        answer_type="choice",
        options=["Trực tuyến", "Trực tiếp"],
    )
    text = ClarifyingQuestion(
        key="ghi_chu", text="Bạn cần ghi chú gì?", answer_type="text"
    )
    assert extract_answers("Tôi chọn trực tuyến", [choice]) == {
        "noi_nop": "Trực tuyến"
    }
    assert extract_answers("Cần hỗ trợ bản sao", [text]) == {
        "ghi_chu": "Cần hỗ trợ bản sao"
    }
