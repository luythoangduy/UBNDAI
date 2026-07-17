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
    """Trích xuất chắc chắn trước; câu có/không ngắn gán theo thứ tự câu hỏi."""
    if not questions:
        return {}
    folded = fold_ascii(message)
    extracted: dict[str, Any] = {}

    for question in questions:
        value = _extract_for_key(folded, question)
        if value is not None:
            extracted[question.key] = value

    # "Có, bé sinh ở bệnh viện": location đã map key sinh; "có" trả lời
    # câu boolean đầu tiên còn lại theo đúng thứ tự catalog.
    clauses = [part.strip() for part in re.split(r"[,;.!?\n]+", folded) if part.strip()]
    short_booleans = [_generic_boolean(clause) for clause in clauses]
    short_booleans = [value for value in short_booleans if value is not None]
    remaining = [
        q for q in questions if q.answer_type == "boolean" and q.key not in extracted
    ]
    for question, value in zip(remaining, short_booleans, strict=False):
        extracted[question.key] = value
    return extracted


def _extract_for_key(text: str, question: ClarifyingQuestion) -> Any | None:
    if question.answer_type == "integer":
        match = re.search(r"(?<!\d)(\d{1,6})(?!\d)(?:\s*ngay)?", text)
        return int(match.group(1)) if match else None

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


def _generic_boolean(clause: str) -> bool | None:
    tokens = clause.split()
    if len(tokens) > 3:
        return None
    if any(token in _NO for token in tokens):
        return False
    if any(token in _YES for token in tokens):
        return True
    return None
