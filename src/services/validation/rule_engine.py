"""Rule engine khai báo — tầng duy nhất được sinh severity=error. Owner: Dev B.

Load ``rules/<procedure_id>.yaml``. Ngôn ngữ check MVP (giữ nhỏ, dễ giải thích):
  - exists(doc.<doc_type>)                       # giấy tờ có mặt
  - match(<field_a>, <field_b>)                  # so khớp có chuẩn hoá dấu/hoa thường
  - days_since(<date_field>) <= N
  - answers.<key> == <value>                     # điều kiện theo câu trả lời làm rõ
Field path: '<doc_type>.<field_key>' khớp ExtractedDocument.field_map().

readiness_score (deterministic, không phải LLM):
  1.0 - w_error*n_error - w_warning*n_warning - w_missing*n_checklist_missing, clamp [0,1].
"""

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.models import Case, ExtractedDocument, ValidationIssue, ValidationReport


def run(case: Case, documents: list[ExtractedDocument]) -> ValidationReport:
    docs = {document.doc_type: document for document in documents}
    fields = {key: value for document in documents for key, value in document.field_map().items()}
    issues: list[ValidationIssue] = []
    for rule in load_rules(case.procedure_id):
        if not _when_matches(rule.get("when", ""), case, docs, fields):
            continue
        if not _check_matches(rule.get("check", ""), case, docs, fields):
            issues.append(ValidationIssue(rule_id=rule["id"], severity=rule.get("severity", "warning"), message=rule["message"], suggestion=rule.get("description"), source="rule"))
    missing = sum(item.status == "missing" for item in case.checklist)
    score = max(0.0, min(1.0, 1.0 - 0.35 * sum(i.severity == "error" for i in issues) - 0.1 * sum(i.severity == "warning" for i in issues) - 0.1 * missing))
    return ValidationReport(case_id=case.id, issues=issues, readiness_score=score, checked_at=datetime.now(timezone.utc))


def load_rules(procedure_id: str) -> list[dict]:
    """Đọc và validate rules/<procedure_id>.yaml."""
    path = Path(__file__).resolve().parents[3] / "rules" / f"{procedure_id}.yaml"
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload.get("rules", [])


def _when_matches(expression: str, case: Case, docs: dict[str, ExtractedDocument], fields: dict[str, str]) -> bool:
    expression = expression.strip()
    if not expression:
        return True
    parts = re.split(r"\s+and\s+", expression)
    return all(_condition(part.strip(), case, docs, fields) for part in parts)


def _condition(expression: str, case: Case, docs: dict[str, ExtractedDocument], fields: dict[str, str]) -> bool:
    exists = re.fullmatch(r"exists\(doc\.([\w-]+)\)", expression)
    if exists:
        return exists.group(1) in docs
    answer = re.fullmatch(r"answers\.([\w-]+)\s*==\s*(true|false)", expression, re.I)
    if answer:
        return bool(case.answers.get(answer.group(1))) is (answer.group(2).lower() == "true")
    return False


def _check_matches(expression: str, case: Case, docs: dict[str, ExtractedDocument], fields: dict[str, str]) -> bool:
    exists = re.fullmatch(r"exists\(doc\.([\w-]+)\)", expression)
    if exists:
        return exists.group(1) in docs
    match = re.fullmatch(r"match\(([^,]+),\s*([^\)]+)\)", expression)
    if match:
        left, right = fields.get(match.group(1).strip()), fields.get(match.group(2).strip())
        return bool(left and right and _normalize(left) == _normalize(right))
    filled = re.fullmatch(r"not filled\(form\.([\w-]+)\)", expression)
    if filled:
        return not bool(case.form_data.get(filled.group(1)))
    age = re.fullmatch(r"days_since\(([^\)]+)\)\s*<=\s*(\d+)", expression)
    if age:
        value = fields.get(age.group(1).strip())
        if not value:
            return False
        try:
            parsed = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - parsed).days <= int(age.group(2))
        except ValueError:
            return False
    return True


def _normalize(value: str) -> str:
    return "".join(value.casefold().split())
