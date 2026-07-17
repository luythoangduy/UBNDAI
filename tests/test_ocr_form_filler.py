"""Tests cho autofill generic theo FormField.ocr_sources — dùng catalog khai_sinh thật."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.models import Case, ExtractedDocument, ExtractedField, Procedure
from src.services.ocr.form_filler import autofill

KHAI_SINH = Path(__file__).resolve().parents[1] / "data" / "procedures" / "khai_sinh.json"


@pytest.fixture()
def procedure() -> Procedure:
    return Procedure.model_validate(json.loads(KHAI_SINH.read_text(encoding="utf-8")))


def _case(form_data: dict | None = None) -> Case:
    now = datetime.now(UTC)
    return Case(
        id="case_1",
        citizen_id="citizen_1",
        procedure_id="khai_sinh",
        form_data=form_data or {},
        created_at=now,
        updated_at=now,
    )


def _document(
    doc_type: str,
    fields: dict[str, tuple[str, float]],
    *,
    created_at: datetime | None = None,
    edited_keys: set[str] = frozenset(),
) -> ExtractedDocument:
    return ExtractedDocument(
        id=f"doc_{doc_type}",
        case_id="case_1",
        file_id="file_1",
        doc_type=doc_type,
        doc_type_confidence=0.95,
        fields=[
            ExtractedField(
                key=key,
                value=value,
                confidence=confidence,
                edited_by_user=key in edited_keys,
            )
            for key, (value, confidence) in fields.items()
        ],
        ocr_engine="vision_llm",
        created_at=created_at or datetime.now(UTC),
    )


def test_autofill_fills_from_declared_ocr_sources(procedure):
    docs = [
        _document(
            "giay_chung_sinh",
            {
                "ho_ten_con": ("Nguyễn Văn Bé", 0.95),
                "ngay_sinh": ("12/03/2026", 0.9),
                "gioi_tinh": ("Nam", 0.97),
            },
        ),
        _document("cccd", {"ho_ten": ("Nguyễn Thị Mẹ", 0.96), "so_cccd": ("012345678901", 0.99)}),
    ]

    form_data = autofill(_case(), procedure, docs)

    assert form_data["ho_ten_con"] == "Nguyễn Văn Bé"
    assert form_data["ngay_sinh"] == "12/03/2026"
    # ho_ten_me ưu tiên nguồn đầu tiên trong ocr_sources: cccd.ho_ten
    assert form_data["ho_ten_me"] == "Nguyễn Thị Mẹ"
    assert form_data["so_cccd_me"] == "012345678901"


def test_autofill_skips_low_confidence_fields(procedure):
    docs = [_document("giay_chung_sinh", {"ho_ten_con": ("Ngyễn Vân Bé?", 0.4)})]

    form_data = autofill(_case(), procedure, docs)

    assert "ho_ten_con" not in form_data


def test_autofill_uses_low_confidence_field_if_user_edited(procedure):
    docs = [
        _document(
            "giay_chung_sinh",
            {"ho_ten_con": ("Nguyễn Văn Bé", 0.4)},
            edited_keys={"ho_ten_con"},
        )
    ]

    form_data = autofill(_case(), procedure, docs)

    assert form_data["ho_ten_con"] == "Nguyễn Văn Bé"


def test_autofill_never_overwrites_existing_form_values(procedure):
    case = _case(form_data={"ho_ten_con": "Tên Do Người Dân Nhập"})
    docs = [_document("giay_chung_sinh", {"ho_ten_con": ("Tên Từ OCR", 0.99)})]

    form_data = autofill(case, procedure, docs)

    assert form_data["ho_ten_con"] == "Tên Do Người Dân Nhập"


def test_autofill_latest_document_wins_for_same_source(procedure):
    old = _document(
        "giay_chung_sinh",
        {"ho_ten_con": ("Bản Cũ", 0.9)},
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    new = _document(
        "giay_chung_sinh",
        {"ho_ten_con": ("Bản Mới", 0.9)},
        created_at=datetime(2026, 7, 15, tzinfo=UTC),
    )

    form_data = autofill(_case(), procedure, [new, old])

    assert form_data["ho_ten_con"] == "Bản Mới"


def test_autofill_returns_copy_not_mutating_case(procedure):
    case = _case()
    docs = [_document("giay_chung_sinh", {"ho_ten_con": ("Nguyễn Văn Bé", 0.95)})]

    form_data = autofill(case, procedure, docs)

    assert case.form_data == {}
    assert form_data != case.form_data
