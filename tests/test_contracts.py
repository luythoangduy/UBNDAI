"""Kiểm tra contract models + dữ liệu mẫu hợp lệ — guard cho Sprint 0."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.models import Procedure, ValidationIssue

PROCEDURES_DIR = Path(__file__).resolve().parents[1] / "data" / "procedures"


def test_procedure_catalog_files_are_valid():
    files = list(PROCEDURES_DIR.glob("*.json"))
    assert files, "Catalog rỗng — cần ít nhất 1 thủ tục mẫu"
    for f in files:
        proc = Procedure.model_validate(json.loads(f.read_text(encoding="utf-8")))
        assert proc.requirements, f"{f.name}: thủ tục phải có requirements"


def test_ai_checker_cannot_emit_error():
    with pytest.raises(ValidationError):
        ValidationIssue(
            rule_id="ai.name_mismatch",
            severity="error",
            message="x",
            source="ai",
        )


def test_form_field_ocr_sources_reference_known_doc_types():
    """ocr_sources phải có dạng '<doc_type>.<field>' để khớp ExtractedDocument.field_map()."""
    for f in PROCEDURES_DIR.glob("*.json"):
        proc = Procedure.model_validate(json.loads(f.read_text(encoding="utf-8")))
        for template in proc.form_templates:
            for field in template.fields:
                for src in field.ocr_sources:
                    assert "." in src, f"{f.name}:{field.key}: ocr_source '{src}' thiếu doc_type prefix"


def test_extracted_document_field_map():
    from src.models import ExtractedDocument, ExtractedField

    doc = ExtractedDocument(
        id="d1",
        case_id="c1",
        file_id="f1",
        doc_type="cccd",
        doc_type_confidence=0.99,
        fields=[ExtractedField(key="ho_ten", value="Nguyễn Văn A", confidence=0.97)],
        ocr_engine="paddleocr",
        created_at=datetime.now(timezone.utc),
    )
    assert doc.field_map() == {"cccd.ho_ten": "Nguyễn Văn A"}
