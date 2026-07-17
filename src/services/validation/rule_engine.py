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

from src.models import Case, ExtractedDocument, ValidationReport


def run(case: Case, documents: list[ExtractedDocument]) -> ValidationReport:
    raise NotImplementedError  # TODO(B) Sprint 2


def load_rules(procedure_id: str) -> list[dict]:
    """Đọc và validate rules/<procedure_id>.yaml."""
    raise NotImplementedError  # TODO(B)
