"""Kiểm tra contract models + dữ liệu mẫu hợp lệ — guard cho Sprint 0."""

import json
import shutil
from datetime import datetime, UTC
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.models import ChatRequest, ClarifyingQuestion, Procedure, ValidationIssue
from src.services import catalog

PROCEDURES_DIR = Path(__file__).resolve().parents[1] / "data" / "procedures"


def test_procedure_catalog_files_are_valid():
    files = list(PROCEDURES_DIR.glob("*.json"))
    assert files, "Catalog rỗng — cần ít nhất 1 thủ tục mẫu"
    for f in files:
        proc = Procedure.model_validate(json.loads(f.read_text(encoding="utf-8")))
        assert proc.requirements, f"{f.name}: thủ tục phải có requirements"


def test_catalog_keeps_planned_core_procedures():
    assert {"khai_sinh", "ket_hon", "tam_tru", "can_cuoc"} <= set(
        catalog.load_catalog()
    )


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
        created_at=datetime.now(UTC),
    )
    assert doc.field_map() == {"cccd.ho_ten": "Nguyễn Văn A"}


def test_chat_request_strips_and_rejects_blank_message():
    assert ChatRequest(message="  xin chào  ").message == "xin chào"
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")


def test_choice_question_requires_options():
    with pytest.raises(ValidationError):
        ClarifyingQuestion(key="loai", text="Chọn loại", answer_type="choice")


@pytest.mark.parametrize("field", ["clarifying_questions", "requirements", "form_templates"])
def test_procedure_rejects_duplicate_catalog_identifiers(field):
    raw = json.loads((PROCEDURES_DIR / "khai_sinh.json").read_text(encoding="utf-8"))
    source = raw[field][0]
    raw[field].append(source)
    with pytest.raises(ValidationError):
        Procedure.model_validate(raw)


@pytest.mark.parametrize("duplicate_field", ["id", "national_code"])
def test_catalog_rejects_duplicate_procedure_identity(tmp_path, duplicate_field):
    source = PROCEDURES_DIR / "khai_sinh.json"
    shutil.copy2(source, tmp_path / "a.json")
    raw = json.loads(source.read_text(encoding="utf-8"))
    if duplicate_field == "id":
        raw["national_code"] = "different-code"
    else:
        raw["id"] = "different-id"
    (tmp_path / "b.json").write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8"
    )
    catalog.clear_cache()
    expected = "Duplicate procedure id" if duplicate_field == "id" else "Duplicate national_code"
    with pytest.raises(ValueError, match=expected):
        catalog.load_catalog(tmp_path)
    catalog.clear_cache()
