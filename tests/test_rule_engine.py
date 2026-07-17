from datetime import datetime, timezone

from src.models import Case, ExtractedDocument, ExtractedField
from src.services.validation.rule_engine import load_rules, run


def test_load_rules_and_emit_rule_finding_for_missing_document():
    assert load_rules("khai_sinh")
    case = Case(id="case-1", citizen_id="citizen-1", procedure_id="khai_sinh", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc), answers={"sinh_tai_co_so_y_te": True})
    report = run(case, [])
    assert any(issue.rule_id == "KS-R1" and issue.severity == "error" for issue in report.issues)
    assert report.has_blocking_errors


def test_matching_documents_do_not_emit_cross_document_error():
    case = Case(id="case-1", citizen_id="citizen-1", procedure_id="khai_sinh", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc), answers={"sinh_tai_co_so_y_te": True})
    docs = [
        ExtractedDocument(id="d1", case_id="case-1", file_id="f1", doc_type="giay_chung_sinh", doc_type_confidence=0.99, fields=[ExtractedField(key="ho_ten_me", value="Nguyen Thi B", confidence=0.99)], ocr_engine="test", created_at=datetime.now(timezone.utc)),
        ExtractedDocument(id="d2", case_id="case-1", file_id="f2", doc_type="cccd", doc_type_confidence=0.99, fields=[ExtractedField(key="ho_ten", value="Nguyen Thi B", confidence=0.99)], ocr_engine="test", created_at=datetime.now(timezone.utc)),
    ]
    report = run(case, docs)
    assert not any(issue.rule_id == "KS-R2" for issue in report.issues)
