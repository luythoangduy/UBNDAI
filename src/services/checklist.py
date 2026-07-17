"""Sinh checklist cá nhân hoá từ catalog — deterministic, không LLM. Owner: Dev A.

AGENTS.md §5: mọi checklist item phải trace về DocumentRequirement.code.
AGENTS.md §6: điều kiện checklist không giấu trong prompt.

Ngôn ngữ condition trong catalog (đủ cho MVP):
    answers.<key> == <literal>   |   answers.<key> != <literal>
với literal là true/false, số nguyên, hoặc chuỗi trong nháy đơn/kép.
"""

from __future__ import annotations

import re
from typing import Any

from src.models import ChecklistItem, DocumentRequirement, Procedure

_CONDITION_PATTERN = re.compile(
    r"^\s*answers\.(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<op>==|!=)\s*(?P<literal>.+?)\s*$"
)


def eval_condition(condition: str | None, answers: dict[str, Any]) -> bool | None:
    """True/False khi đủ dữ liệu; None khi answers chưa có key (cần làm rõ thêm)."""
    if not condition:
        return True
    match = _CONDITION_PATTERN.match(condition)
    if not match:
        raise ValueError(f"Condition không hợp lệ trong catalog: {condition!r}")
    key = match.group("key")
    if key not in answers:
        return None
    expected = _parse_literal(match.group("literal"))
    actual = answers[key]
    equal = _normalize(actual) == _normalize(expected)
    return equal if match.group("op") == "==" else not equal


def build_checklist(
    procedure: Procedure, answers: dict[str, Any]
) -> list[ChecklistItem]:
    """Áp answers vào requirements → checklist. Điều kiện chưa rõ vẫn giữ item
    (status 'missing') kèm note để người dân/cán bộ biết còn tuỳ trường hợp."""
    items: list[ChecklistItem] = []
    for requirement in procedure.requirements:
        applicable = eval_condition(requirement.condition, answers)
        if applicable is False:
            items.append(
                ChecklistItem(
                    requirement_code=requirement.code,
                    status="not_applicable",
                    note=f"Không áp dụng cho trường hợp của bạn ({requirement.condition})",
                )
            )
            continue
        note = requirement.notes
        if applicable is None:
            note = requirement.condition_label or "Tuỳ trường hợp — cần làm rõ thêm"
        items.append(
            ChecklistItem(requirement_code=requirement.code, status="missing", note=note)
        )
    return items


def unresolved_condition_keys(
    procedure: Procedure, answers: dict[str, Any]
) -> list[str]:
    """Các key answers còn thiếu để chốt checklist — đầu vào cho clarify."""
    keys: list[str] = []
    for requirement in procedure.requirements:
        if not requirement.condition:
            continue
        match = _CONDITION_PATTERN.match(requirement.condition)
        if match and match.group("key") not in answers and match.group("key") not in keys:
            keys.append(match.group("key"))
    return keys


def requirement_by_code(
    procedure: Procedure, code: str
) -> DocumentRequirement | None:
    for requirement in procedure.requirements:
        if requirement.code == code:
            return requirement
    return None


def guidance_warnings(procedure: Procedure, answers: dict[str, Any]) -> list[str]:
    """Cảnh báo deterministic khai báo từ catalog, không hardcode pháp lý trong prompt."""
    days = answers.get("so_ngay_tu_khi_sinh")
    if (
        isinstance(days, int)
        and procedure.late_registration_after_days is not None
        and days > procedure.late_registration_after_days
        and procedure.late_registration_warning
    ):
        return [procedure.late_registration_warning]
    return []


def _parse_literal(raw: str) -> Any:
    text = raw.strip()
    lowered = text.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "có", "co", "yes", "rồi", "roi"}:
            return True
        if lowered in {"false", "không", "khong", "no", "chưa", "chua"}:
            return False
        if re.fullmatch(r"-?\d+", lowered):
            return int(lowered)
        return lowered
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return int(value)
    return value
