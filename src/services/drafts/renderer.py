"""Renderer deterministic cho bản nháp; không gọi LLM và không phụ thuộc OCR."""

from __future__ import annotations

import re
from datetime import date, datetime, UTC
from typing import Any
from uuid import uuid4

from src.models import (
    DraftFieldSpec,
    DraftGenerateRequest,
    DraftLayoutBlock,
    DraftTemplate,
    GeneratedDraft,
)
from src.services.drafts.registry import get_template

WATERMARK = "DỰ THẢO - KHÔNG CÓ GIÁ TRỊ PHÁP LÝ"


class DraftDataError(ValueError):
    def __init__(self, message: str, *, fields: list[str] | None = None) -> None:
        super().__init__(message)
        self.fields = fields or []


def generate(payload: DraftGenerateRequest) -> GeneratedDraft:
    template = get_template(payload.procedure_id, payload.template_id)
    normalized = _normalize_values(template, payload.values)
    missing = _missing_required_fields(template, normalized)
    if missing and not payload.allow_incomplete:
        raise DraftDataError(
            "Thiếu trường bắt buộc để sinh bản nháp: " + ", ".join(missing),
            fields=missing,
        )

    rendered = [WATERMARK, ""]
    rendered.extend(_render_block(block, template, normalized) for block in template.layout)
    rendered.extend(["", template.disclaimer])
    warnings = [
        "Đây chỉ là bản nháp để rà soát; cơ quan có thẩm quyền phải kiểm tra, ký và phát hành."
    ]
    if missing:
        warnings.append("Bản nháp còn thiếu: " + ", ".join(missing))
    return GeneratedDraft(
        id=str(uuid4()),
        procedure_id=template.procedure_id,
        template_id=template.id,
        output_name=template.output_name,
        template_version=template.version,
        watermark=WATERMARK,
        normalized_values=normalized,
        rendered_text="\n".join(rendered).strip(),
        missing_required_fields=missing,
        ready_for_review=not missing,
        warnings=warnings,
        legal_sources=template.legal_sources,
        disclaimer=template.disclaimer,
        generated_at=datetime.now(UTC),
    )


def _normalize_values(
    template: DraftTemplate, values: dict[str, Any]
) -> dict[str, str]:
    specs = {field.key: field for field in template.fields}
    unknown = sorted(set(values) - set(specs))
    if unknown:
        raise DraftDataError(
            "Template không khai báo các field: " + ", ".join(unknown),
            fields=unknown,
        )

    normalized: dict[str, str] = {}
    for key, value in values.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        normalized[key] = _normalize_value(specs[key], value)
    return normalized


def _normalize_value(spec: DraftFieldSpec, value: Any) -> str:
    if spec.input_type == "date":
        normalized = _parse_date(value).isoformat()
    elif spec.input_type == "year":
        normalized = str(value).strip()
        if not re.fullmatch(r"\d{4}", normalized):
            raise DraftDataError(
                spec.validation_message or f"{spec.label} phải là năm gồm 4 chữ số",
                fields=[spec.key],
            )
    else:
        normalized = str(value).strip()

    if spec.allowed_values:
        canonical = {
            option.casefold(): option for option in spec.allowed_values
        }.get(normalized.casefold())
        if canonical is None:
            raise DraftDataError(
                spec.validation_message
                or f"{spec.label} phải là một trong: {', '.join(spec.allowed_values)}",
                fields=[spec.key],
            )
        normalized = canonical
    if spec.pattern and not re.fullmatch(spec.pattern, normalized):
        raise DraftDataError(
            spec.validation_message or f"{spec.label} không đúng định dạng",
            fields=[spec.key],
        )
    if spec.normalize == "uppercase":
        normalized = normalized.upper()
    return normalized


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    raise DraftDataError(
        "Ngày phải theo định dạng YYYY-MM-DD hoặc DD/MM/YYYY"
    )


def _missing_required_fields(
    template: DraftTemplate, values: dict[str, str]
) -> list[str]:
    missing = [field.key for field in template.fields if field.required and field.key not in values]
    for group in template.conditional_groups:
        if any(values.get(key) for key in group.trigger_fields):
            missing.extend(key for key in group.required_fields if not values.get(key))
    return list(dict.fromkeys(missing))


def _render_block(
    block: DraftLayoutBlock,
    template: DraftTemplate,
    values: dict[str, str],
) -> str:
    if block.kind == "spacer":
        return ""
    if block.kind in {"title", "text"}:
        return block.text or ""
    labels = {field.key: field.label for field in template.fields}
    if block.kind == "field":
        key = block.field or ""
        label = block.label or labels[key]
        return f"{label}: {_display_value(key, block.value_format, values, label)}"
    parts = []
    for item in block.items:
        label = item.label or labels[item.field]
        value = _display_value(item.field, item.value_format, values, label)
        parts.append(f"{label}: {value}")
    return " | ".join(parts)


def _display_value(
    key: str,
    value_format: str,
    values: dict[str, str],
    label: str,
) -> str:
    value = values.get(key)
    if not value:
        return f"[CHƯA CÓ: {label}]"
    if value_format == "uppercase":
        return value.upper()
    if value_format in {"date_numeric", "date_words"}:
        parsed = date.fromisoformat(value)
        if value_format == "date_numeric":
            return parsed.strftime("%d/%m/%Y")
        return _date_in_words(parsed)
    return value


def _date_in_words(value: date) -> str:
    return (
        f"Ngày {_number_in_words(value.day)} tháng {_number_in_words(value.month)} "
        f"năm {_number_in_words(value.year)}"
    )


def _number_in_words(number: int) -> str:
    if not 0 <= number <= 9999:
        raise ValueError("Chỉ hỗ trợ đọc số từ 0 đến 9999")
    ones = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
    if number < 10:
        return ones[number]

    def read_two(value: int) -> str:
        tens, unit = divmod(value, 10)
        if tens == 0:
            return ones[unit]
        prefix = "mười" if tens == 1 else f"{ones[tens]} mươi"
        if unit == 0:
            return prefix
        unit_word = "mốt" if unit == 1 and tens > 1 else "lăm" if unit == 5 else ones[unit]
        return f"{prefix} {unit_word}"

    def read_three(value: int, *, full: bool = False) -> str:
        hundreds, remainder = divmod(value, 100)
        parts: list[str] = []
        if hundreds or full:
            parts.append(f"{ones[hundreds]} trăm")
        if remainder:
            if remainder < 10 and (hundreds or full):
                parts.append("linh")
            parts.append(read_two(remainder))
        return " ".join(parts)

    thousands, remainder = divmod(number, 1000)
    if not thousands:
        return read_three(remainder)
    result = f"{ones[thousands]} nghìn"
    if remainder:
        result += " " + read_three(remainder, full=remainder < 100)
    return result
