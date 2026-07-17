"""Rule engine khai báo — tầng duy nhất được sinh severity=error. Owner: Dev B.

Load ``rules/<procedure_id>.yaml``. Ngôn ngữ check MVP (giữ nhỏ, dễ giải thích):
  - exists(doc.<doc_type>)                       # giấy tờ có mặt
  - filled(form.<key>)                           # trường form đã điền
  - match(<field_a>, <field_b>)                  # so khớp có chuẩn hoá dấu/hoa thường
  - days_since(<date_field>) <= N                # (hoặc >= / < / >)
  - answers.<key> == <value>                     # điều kiện theo câu trả lời làm rõ
  - not <term>  |  <term> and <term> ...
Field path: '<doc_type>.<field_key>' khớp ExtractedDocument.field_map();
'form.<key>' đọc Case.form_data.

Không dùng eval() — parser regex từng term, biểu thức không nhận diện được:
- trong ``when``  → rule coi như KHÔNG áp dụng (bỏ qua, log warning);
- trong ``check`` → coi như FAIL (tầng deterministic phải nói được "chưa xác minh
  được" thay vì im lặng cho qua).

readiness_score (deterministic, không phải LLM):
  1.0 - w_error*n_error - w_warning*n_warning - w_missing*n_checklist_missing, clamp [0,1].
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from src.models import Case, ExtractedDocument, ValidationIssue, ValidationReport

logger = logging.getLogger(__name__)

RULES_DIR = Path(__file__).resolve().parents[3] / "rules"

WEIGHT_ERROR = 0.3
WEIGHT_WARNING = 0.1
WEIGHT_CHECKLIST_MISSING = 0.15

_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y")

_RE_EXISTS = re.compile(r"^exists\(\s*doc\.([a-z0-9_]+)\s*\)$")
_RE_FILLED = re.compile(r"^filled\(\s*form\.([a-z0-9_]+)\s*\)$")
_RE_MATCH = re.compile(r"^match\(\s*([a-z0-9_.]+)\s*,\s*([a-z0-9_.]+)\s*\)$")
_RE_DAYS_SINCE = re.compile(r"^days_since\(\s*([a-z0-9_.]+)\s*\)\s*(<=|>=|<|>)\s*(\d+)$")
_RE_ANSWER_EQ = re.compile(r"^answers\.([a-z0-9_]+)\s*==\s*(.+)$")


class RuleFileError(Exception):
    """rules/<procedure_id>.yaml thiếu, sai cấu trúc hoặc không đọc được."""


def load_rules(procedure_id: str) -> list[dict]:
    """Đọc và validate rules/<procedure_id>.yaml."""
    if not re.fullmatch(r"[a-z0-9_]+", procedure_id or ""):
        raise RuleFileError(f"procedure_id không hợp lệ: {procedure_id!r}")
    path = RULES_DIR / f"{procedure_id}.yaml"
    if not path.is_file():
        raise RuleFileError(f"Không tìm thấy bộ rule: {path.name}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise RuleFileError(f"{path.name}: thiếu key 'rules' dạng list")

    rules: list[dict] = []
    for i, rule in enumerate(data["rules"]):
        if not isinstance(rule, dict):
            raise RuleFileError(f"{path.name}: rule #{i} không phải mapping")
        missing = {"id", "check", "severity", "message"} - rule.keys()
        if missing:
            raise RuleFileError(f"{path.name}: rule '{rule.get('id', i)}' thiếu {sorted(missing)}")
        if rule["severity"] not in ("error", "warning", "info"):
            raise RuleFileError(
                f"{path.name}: rule '{rule['id']}' severity không hợp lệ: {rule['severity']}"
            )
        rules.append(rule)
    return rules


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return " ".join(stripped.replace("đ", "d").replace("Đ", "D").casefold().split())


def _parse_date(value: str) -> date | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


class _Context:
    def __init__(self, case: Case, documents: list[ExtractedDocument]) -> None:
        self.case = case
        self.doc_types = {d.doc_type for d in documents}
        # Giấy tờ mới nhất thắng khi trùng key — nhất quán với form_filler.
        self.field_map: dict[str, str] = {}
        for doc in sorted(documents, key=lambda d: d.created_at):
            self.field_map.update(doc.field_map())

    def lookup(self, path: str) -> str:
        if path.startswith("form."):
            value = self.case.form_data.get(path.removeprefix("form."), "")
            return str(value) if value is not None else ""
        return self.field_map.get(path, "")


def _eval_term(term: str, ctx: _Context) -> bool | None:
    """Trả True/False, hoặc None nếu term không nhận diện được."""
    term = term.strip()
    negated = False
    while term.startswith("not "):
        negated = not negated
        term = term[4:].strip()

    result: bool | None = None
    if m := _RE_EXISTS.match(term):
        result = m.group(1) in ctx.doc_types
    elif m := _RE_FILLED.match(term):
        result = bool(ctx.lookup(f"form.{m.group(1)}").strip())
    elif m := _RE_MATCH.match(term):
        left, right = ctx.lookup(m.group(1)), ctx.lookup(m.group(2))
        result = bool(left.strip()) and _fold(left) == _fold(right)
    elif m := _RE_DAYS_SINCE.match(term):
        parsed = _parse_date(ctx.lookup(m.group(1)))
        if parsed is None:
            return None  # ngày thiếu/không đọc được — caller quyết định theo when/check
        days = (datetime.now(UTC).date() - parsed).days
        op, limit = m.group(2), int(m.group(3))
        result = {
            "<=": days <= limit,
            ">=": days >= limit,
            "<": days < limit,
            ">": days > limit,
        }[op]
    elif m := _RE_ANSWER_EQ.match(term):
        raw = m.group(2).strip().strip("'\"")
        expected: object = {"true": True, "false": False}.get(raw.lower(), raw)
        actual = ctx.case.answers.get(m.group(1))
        if isinstance(expected, bool):
            result = actual is expected
        else:
            result = actual is not None and str(actual) == str(expected)

    if result is None:
        return None
    return (not result) if negated else result


def _eval_expr(expr: str, ctx: _Context) -> bool | None:
    """Hội các term nối bằng ' and '. None lan truyền (không nhận diện được)."""
    outcome = True
    for term in re.split(r"\s+and\s+", expr.strip()):
        value = _eval_term(term, ctx)
        if value is None:
            return None
        outcome = outcome and value
    return outcome


def compute_readiness_score(
    n_error: int, n_warning: int, n_checklist_missing: int
) -> float:
    score = (
        1.0
        - WEIGHT_ERROR * n_error
        - WEIGHT_WARNING * n_warning
        - WEIGHT_CHECKLIST_MISSING * n_checklist_missing
    )
    return max(0.0, min(1.0, round(score, 4)))


def run(case: Case, documents: list[ExtractedDocument]) -> ValidationReport:
    if not case.procedure_id:
        raise RuleFileError("Case chưa xác định procedure_id — chưa thể kiểm tra hồ sơ")
    rules = load_rules(case.procedure_id)
    ctx = _Context(case, documents)

    issues: list[ValidationIssue] = []
    for rule in rules:
        when = rule.get("when")
        if when:
            applicable = _eval_expr(str(when), ctx)
            if applicable is None:
                logger.warning(
                    "Rule %s: điều kiện when không nhận diện được (%r) — bỏ qua rule",
                    rule["id"],
                    when,
                )
                continue
            if not applicable:
                continue

        passed = _eval_expr(str(rule["check"]), ctx)
        if passed is None:
            logger.warning(
                "Rule %s: check không xác minh được (%r) — coi như FAIL", rule["id"], rule["check"]
            )
        if not passed:  # False hoặc None đều thành issue
            issues.append(
                ValidationIssue(
                    rule_id=str(rule["id"]),
                    severity=rule["severity"],
                    message=str(rule["message"]),
                    field_keys=_referenced_fields(str(rule["check"])),
                    suggestion=rule.get("suggestion"),
                    source="rule",
                )
            )

    n_missing = sum(1 for item in case.checklist if item.status == "missing")
    score = compute_readiness_score(
        n_error=sum(1 for i in issues if i.severity == "error"),
        n_warning=sum(1 for i in issues if i.severity == "warning"),
        n_checklist_missing=n_missing,
    )
    return ValidationReport(
        case_id=case.id,
        issues=issues,
        readiness_score=score,
        checked_at=datetime.now(UTC),
    )


def _referenced_fields(check: str) -> list[str]:
    """Rút các field path '<doc_type>.<key>' / 'form.<key>' trong check để hiển thị UI."""
    return [p for p in re.findall(r"\b([a-z0-9_]+\.[a-z0-9_]+)\b", check) if "." in p]
