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
) -> dict[str, Any]:
    """Mỗi thông tin trong message chỉ được dùng để trả lời một key."""
    if not questions:
        return {}
    folded = fold_ascii(message)
    extracted: dict[str, Any] = {}

    for question in questions:
        value = _extract_for_key(folded, question)
        if value is not None:
            extracted[question.key] = value

    # Generic boolean chỉ hợp lệ khi toàn bộ message là một câu trả lời ngắn.
    # Không tái sử dụng "không" trong "không kết hôn" cho câu hỏi sinh tại đâu.
    if not extracted:
        generic = _standalone_boolean(folded)
        first_boolean = next(
            (question for question in questions if question.answer_type == "boolean"),
            None,
        )
        if generic is not None and first_boolean:
            extracted[first_boolean.key] = generic

    if not extracted and len(questions) == 1 and questions[0].answer_type == "text":
        extracted[questions[0].key] = message.strip()
    return extracted


def _extract_for_key(text: str, question: ClarifyingQuestion) -> Any | None:
    if question.answer_type == "integer":
        match = re.search(
            r"\b(?:sinh\s+duoc|duoc|da\s+sinh)\s+(\d{1,4})\s+ngay\b",
            text,
        ) or re.fullmatch(r"\s*(\d{1,4})\s*(?:ngay)?\s*", text)
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

    if question.key == "ket_hon":
        if re.search(r"\b(chua|khong)\s+(?:dang ky\s+)?ket hon\b", text):
            return False
        if re.search(r"\b(?:da|co)\s+(?:dang ky\s+)?ket hon\b", text):
            return True
    elif question.key == "sinh_tai_co_so_y_te":
        if re.search(r"\b(?:tai nha|o nha|ngoai co so y te)\b", text):
            return False
        if re.search(r"\b(?:benh vien|co so y te|tram y te|nha ho sinh)\b", text):
            return True
    return None


def _standalone_boolean(text: str) -> bool | None:
    tokens = text.strip().split()
    if len(tokens) > 2:
        return None
    if any(token in _NO for token in tokens):
        return False
    if any(token in _YES for token in tokens):
        return True
    return None
