"""Deterministic, catalog-grounded analysis helpers for application intake."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
import unicodedata
from typing import Any
from collections.abc import Iterable, Mapping


@dataclass(frozen=True)
class ApplicationClassification:
    code: str
    name: str
    confidence: float
    method: str
    evidence: tuple[str, ...] = ()
    needs_manual_review: bool = False


@dataclass(frozen=True)
class ApplicationAnomaly:
    code: str
    message: str
    field_name: str | None = None
    severity: str = "warning"
    confidence: float = 1.0
    detected_by: str = "rule_engine"
    evidence: tuple[str, ...] = ()


def _plain(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def classify_application(text: str, catalog: Iterable[Mapping[str, Any]]) -> ApplicationClassification:
    """Match only against supplied catalog entries; never invent a procedure."""
    normalized = _plain(text)
    best: tuple[int, Mapping[str, Any], list[str]] | None = None
    for entry in catalog:
        matched = [str(keyword) for keyword in entry.get("keywords", ()) if _plain(keyword) in normalized]
        name = str(entry.get("name", ""))
        if name and _plain(name) in normalized:
            matched.append(name)
        score = len(matched)
        if score and (best is None or score > best[0]):
            best = (score, entry, matched)
    if best is None:
        return ApplicationClassification("UNKNOWN", "Chưa xác định", 0.0, "keyword_catalog", (), True)
    _, entry, evidence = best
    return ApplicationClassification(
        str(entry["code"]), str(entry.get("name", entry["code"])),
        min(0.99, 0.65 + 0.15 * (len(evidence) - 1)), "keyword_catalog",
        tuple(dict.fromkeys(evidence)), False,
    )


def validate_citizen_id(value: Any) -> bool:
    return bool(re.fullmatch(r"\d{12}", str(value or "").strip()))


def validate_required_fields(form_data: Mapping[str, Any], required_fields: Iterable[str]) -> list[ApplicationAnomaly]:
    issues: list[ApplicationAnomaly] = []
    for field_name in required_fields:
        value = form_data.get(field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            issues.append(ApplicationAnomaly(
                code="MISSING_REQUIRED_FIELD",
                message=f"Thiếu trường bắt buộc: {field_name}",
                field_name=field_name,
            ))
    return issues


def validate_required_documents(document_types: Iterable[str], required_types: Iterable[str]) -> list[ApplicationAnomaly]:
    available = {_plain(item) for item in document_types}
    return [ApplicationAnomaly("MISSING_REQUIRED_DOCUMENT", f"Thiếu giấy tờ bắt buộc: {item}", evidence=(item,))
            for item in required_types if _plain(item) not in available]


def validate_date(value: Any, field_name: str, *, today: date | None = None) -> list[ApplicationAnomaly]:
    raw = str(value or "").strip()
    parsed = None
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(raw, pattern).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return [ApplicationAnomaly("INVALID_DATE", f"Ngày không hợp lệ: {field_name}", field_name)]
    if parsed > (today or date.today()):
        return [ApplicationAnomaly("FUTURE_DATE", f"Ngày không được ở tương lai: {field_name}", field_name)]
    return []


def validate_template(actual_code: str | None, actual_version: str | None, expected_code: str, expected_version: str) -> list[ApplicationAnomaly]:
    if actual_code != expected_code or actual_version != expected_version:
        return [ApplicationAnomaly("WRONG_TEMPLATE_VERSION", "Biểu mẫu hoặc phiên bản không đúng", evidence=(expected_code, expected_version))]
    return []


def validate_readability(text: str | None, confidence: float | None, *, threshold: float = 0.75) -> list[ApplicationAnomaly]:
    if not (text or "").strip() or confidence is None or confidence < threshold:
        return [ApplicationAnomaly("LOW_READABILITY", "Tài liệu khó đọc và cần cán bộ kiểm tra", confidence=confidence or 0.0)]
    return []


def detect_duplicates(hashes: Iterable[str]) -> list[ApplicationAnomaly]:
    seen: set[str] = set()
    issues: list[ApplicationAnomaly] = []
    for digest in hashes:
        if digest in seen:
            issues.append(ApplicationAnomaly("DUPLICATE_DOCUMENT", "Tài liệu bị trùng lặp", evidence=(digest,)))
        seen.add(digest)
    return issues


def validate_cross_document(records: Iterable[Mapping[str, Any]], fields: Iterable[str] = ("ho_ten", "cccd", "ngay_sinh")) -> list[ApplicationAnomaly]:
    records = list(records)
    issues: list[ApplicationAnomaly] = []
    for field in fields:
        values = {_plain(record.get(field)) for record in records if record.get(field) not in (None, "")}
        if len(values) > 1:
            issues.append(ApplicationAnomaly("CROSS_DOCUMENT_MISMATCH", f"Thông tin {field} không khớp giữa các giấy tờ", field, evidence=tuple(sorted(values))))
    return issues


def normalize_ai_anomalies(items: Iterable[Mapping[str, Any]]) -> list[ApplicationAnomaly]:
    """Enforce the invariant that AI cannot create blocking errors."""
    result: list[ApplicationAnomaly] = []
    for item in items:
        severity = str(item.get("severity", "warning")).lower()
        result.append(ApplicationAnomaly(
            code=str(item.get("code", "AI_REVIEW")), message=str(item.get("message", "Cần cán bộ kiểm tra")),
            field_name=item.get("field_name"), severity=severity if severity in {"warning", "info"} else "warning",
            confidence=max(0.0, min(1.0, float(item.get("confidence", 0.5)))), detected_by="ai",
            evidence=tuple(str(value) for value in item.get("evidence", ())),
        ))
    return result
