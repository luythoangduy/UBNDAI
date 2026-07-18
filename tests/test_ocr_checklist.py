"""Tests cập nhật checklist sau OCR — dùng catalog khai_sinh thật."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.models import Case, ChecklistItem, ExtractedDocument, Procedure
from src.services import catalog
from src.services.ocr.checklist import apply_document_to_checklist, codes_satisfied_by

KHAI_SINH = Path(__file__).resolve().parents[1] / "data" / "procedures" / "khai_sinh.json"


@pytest.fixture()
def procedure() -> Procedure:
    return Procedure.model_validate(json.loads(KHAI_SINH.read_text(encoding="utf-8")))


def _case(checklist: list[ChecklistItem]) -> Case:
    now = datetime.now(UTC)
    return Case(
        id="case_1",
        citizen_id="citizen_1",
        procedure_id="khai_sinh",
        checklist=checklist,
        created_at=now,
        updated_at=now,
    )


def _doc(doc_type: str, needs_review: bool = False) -> ExtractedDocument:
    return ExtractedDocument(
        id=f"doc_{doc_type}",
        case_id="case_1",
        file_id="file_1",
        doc_type=doc_type,
        doc_type_confidence=0.95,
        needs_human_review=needs_review,
        ocr_engine="vision_llm",
        created_at=datetime.now(UTC),
    )


def test_matching_item_becomes_uploaded_with_document_id(procedure):
    case = _case([ChecklistItem(requirement_code="giay_chung_sinh", status="missing")])

    updated = apply_document_to_checklist(case, procedure, _doc("giay_chung_sinh"))

    assert updated[0].status == "uploaded"
    assert updated[0].document_id == "doc_giay_chung_sinh"


def test_needs_human_review_marks_item_uncertain(procedure):
    case = _case([ChecklistItem(requirement_code="giay_chung_sinh", status="missing")])

    updated = apply_document_to_checklist(
        case, procedure, _doc("giay_chung_sinh", needs_review=True)
    )

    assert updated[0].status == "uncertain"


def test_non_matching_items_untouched_and_verified_never_downgraded(procedure):
    case = _case(
        [
            ChecklistItem(requirement_code="cccd_cha_me", status="verified", document_id="old"),
            ChecklistItem(requirement_code="to_khai_khai_sinh", status="missing"),
        ]
    )

    updated = apply_document_to_checklist(case, procedure, _doc("cccd"))

    # cccd khớp accepted_doc_types của cccd_cha_me nhưng item đã verified → giữ nguyên
    assert updated[0].status == "verified" and updated[0].document_id == "old"
    # to_khai_khai_sinh không nhận doc_type cccd → giữ nguyên
    assert updated[1].status == "missing"


def test_original_case_not_mutated(procedure):
    items = [ChecklistItem(requirement_code="giay_chung_sinh", status="missing")]
    case = _case(items)

    apply_document_to_checklist(case, procedure, _doc("giay_chung_sinh"))

    assert case.checklist[0].status == "missing"


def test_every_catalog_requirement_declares_an_accepted_document_type():
    missing = [
        f"{procedure.id}:{requirement.code}"
        for procedure in catalog.load_catalog().values()
        for requirement in procedure.requirements
        if not requirement.accepted_doc_types
    ]

    assert missing == []


@pytest.mark.parametrize(
    ("procedure_id", "document_type", "requirement_code"),
    [
        ("khai_sinh", "ho_chieu", "cccd_cha_me"),
        ("khai_sinh", "van_ban_cam_doan_viec_sinh", "van_ban_nguoi_lam_chung"),
        ("tam_tru", "to_khai_ct01", "y_kien_nguoi_dai_dien"),
    ],
)
def test_catalog_declared_document_alternatives_satisfy_checklist(
    procedure_id, document_type, requirement_code
):
    procedure = catalog.get_procedure(procedure_id)

    assert procedure is not None
    assert requirement_code in codes_satisfied_by(procedure, document_type)
