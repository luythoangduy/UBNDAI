"""Parse câu trả lời làm rõ theo key/type trong catalog, không phụ thuộc LLM."""

from __future__ import annotations

import re
from typing import Any

from src.models import ClarifyingQuestion, Procedure
from src.services.retrieval.common import fold_ascii

_YES = {"co", "roi", "dung", "yes"}
_NO = {"khong", "chua", "no"}


def unresolved_questions(
    procedure: Procedure, answers: dict[str, Any]
) -> list[ClarifyingQuestion]:
    return [q for q in procedure.clarifying_questions if q.key not in answers]


def extract_answers(
    message: str,
    questions: list[ClarifyingQuestion],
    *,
    allow_standalone: bool = True,
) -> dict[str, Any]:
    """Parse tuần tự; mỗi clause chỉ được consume một lần."""
    if not questions:
        return {}
    folded = fold_ascii(message)
    extracted: dict[str, Any] = {}
    clauses = [
        clause.strip()
        for clause in re.split(r"[,;.!?\n]+|\bva\b", folded)
        if clause.strip()
    ]
    question_cursor = 0

    for clause in clauses:
        explicit = [
            (index, value)
            for index, question in enumerate(questions)
            if (value := _extract_for_key(clause, question)) is not None
        ]
        if explicit:
            # Clause semantic cụ thể chỉ map key rõ nhất/đầu tiên trong catalog.
            index, value = explicit[0]
            extracted[questions[index].key] = value
            question_cursor = max(question_cursor, index + 1)
            continue
        if not allow_standalone:
            continue
        generic = _standalone_boolean(clause)
        if generic is None:
            continue
        for index in range(question_cursor, len(questions)):
            if questions[index].answer_type != "boolean":
                continue
            extracted[questions[index].key] = generic
            question_cursor = index + 1
            break

    if not extracted and len(questions) == 1 and questions[0].answer_type == "text":
        extracted[questions[0].key] = message.strip()
    return extracted


def _extract_for_key(text: str, question: ClarifyingQuestion) -> Any | None:
    if question.answer_type == "integer":
        # Parser fallback chỉ lấy một số nguyên không mơ hồ; diễn giải ngữ nghĩa
        # theo từng thủ tục thuộc planner LLM, không hard-code key nghiệp vụ.
        matches = re.findall(r"(?<!\d)-?\d+(?!\d)", text)
        match = re.fullmatch(r"\s*(-?\d+)\s*(?:\w+)?\s*", text)
        if not match and len(matches) == 1:
            match = re.search(r"(?<!\d)(-?\d+)(?!\d)", text)
        if not match:
            return None
        value = int(match.group(1))
        if question.minimum is not None and value < question.minimum:
            return None
        if question.maximum is not None and value > question.maximum:
            return None
        return value

    if question.answer_type == "choice":
        matches = [
            option
            for option in question.options
            if fold_ascii(option) in text
        ]
        return matches[0] if len(matches) == 1 else None

    if question.answer_type != "boolean":
        return None

    return None


def _standalone_boolean(text: str) -> bool | None:
    normalized = text.strip()
    for prefix in ("thuc ra", "sua lai", "dinh chinh", "cau tra loi la"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].lstrip(" :,-")
            break
    tokens = normalized.split()
    if len(tokens) > 2:
        return None
    if any(token in _NO for token in tokens):
        return False
    if any(token in _YES for token in tokens):
        return True
    return None


def is_correction_message(message: str) -> bool:
    folded = fold_ascii(message)
    return any(
        marker in folded
        for marker in (
            "sua lai", "dinh chinh", "nham", "khong dung", "thay doi", "thuc ra",
        )
    )
