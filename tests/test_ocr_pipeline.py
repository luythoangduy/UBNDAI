"""Tests cho pipeline OCR: mapping OcrResult → ExtractedDocument + needs_human_review."""

import cv2
import numpy as np

from src.models import ExtractedDocument
from src.services.ocr import pipeline
from src.services.ocr.engine import OcrField, OcrResult


def _png_bytes() -> bytes:
    ok, encoded = cv2.imencode(".png", np.full((400, 600, 3), 230, dtype=np.uint8))
    assert ok
    return encoded.tobytes()


class FakeEngine:
    def __init__(self, result: OcrResult):
        self.result = result
        self.received: bytes | None = None

    def extract(self, image_bytes: bytes) -> OcrResult:
        self.received = image_bytes
        return self.result


def _install(monkeypatch, result: OcrResult) -> FakeEngine:
    engine = FakeEngine(result)
    monkeypatch.setattr(pipeline, "get_engine", lambda: engine)
    return engine


def _result(doc_conf: float, field_conf: float, doc_type: str = "giay_chung_sinh") -> OcrResult:
    return OcrResult(
        raw_text="Họ tên: Nguyễn Văn A",
        fields=[OcrField(key="ho_ten", value="Nguyễn Văn A", confidence=field_conf)],
        doc_type_hint=doc_type,
        doc_type_confidence=doc_conf,
        engine="fake",
    )


async def test_process_maps_ocr_result_to_contract(monkeypatch):
    _install(monkeypatch, _result(doc_conf=0.95, field_conf=0.9))

    doc = await pipeline.process("case_1", "don.png", _png_bytes())

    assert isinstance(doc, ExtractedDocument)
    assert doc.case_id == "case_1"
    assert doc.doc_type == "giay_chung_sinh"
    assert doc.fields[0].key == "ho_ten"
    assert doc.raw_text == "Họ tên: Nguyễn Văn A"
    assert doc.ocr_engine == "fake"
    assert doc.needs_human_review is False
    assert doc.field_map() == {"giay_chung_sinh.ho_ten": "Nguyễn Văn A"}


async def test_low_field_confidence_forces_human_review(monkeypatch):
    _install(monkeypatch, _result(doc_conf=0.95, field_conf=0.5))

    doc = await pipeline.process("case_1", "don.png", _png_bytes())

    assert doc.needs_human_review is True


async def test_low_doc_type_confidence_forces_human_review(monkeypatch):
    _install(monkeypatch, _result(doc_conf=0.4, field_conf=0.95))

    doc = await pipeline.process("case_1", "don.png", _png_bytes())

    assert doc.needs_human_review is True


async def test_unknown_doc_type_forces_human_review(monkeypatch):
    _install(monkeypatch, _result(doc_conf=0.99, field_conf=0.99, doc_type="unknown"))

    doc = await pipeline.process("case_1", "don.png", _png_bytes())

    assert doc.needs_human_review is True


async def test_process_preprocesses_image_before_engine(monkeypatch):
    engine = _install(monkeypatch, _result(doc_conf=0.95, field_conf=0.9))
    original = _png_bytes()

    await pipeline.process("case_1", "don.png", original)

    # Preprocessing re-encodes to JPEG, so the engine must not see the raw PNG.
    assert engine.received is not None
    assert engine.received != original
    assert engine.received[:3] == b"\xff\xd8\xff"


async def test_undecodable_image_falls_back_to_original_bytes(monkeypatch):
    engine = _install(monkeypatch, _result(doc_conf=0.95, field_conf=0.9))
    junk = b"not-an-image"

    doc = await pipeline.process("case_1", "don.png", junk)

    assert engine.received == junk
    assert isinstance(doc, ExtractedDocument)


async def test_classifier_conflict_with_engine_hint_forces_human_review(monkeypatch):
    # Engine nói cccd nhưng raw_text rõ ràng là giấy chứng sinh → conflict.
    conflicted = OcrResult(
        raw_text="GIẤY CHỨNG SINH\nHọ tên mẹ: Nguyễn Thị B\nNơi sinh: BV Từ Dũ",
        fields=[OcrField(key="ho_ten_me", value="Nguyễn Thị B", confidence=0.95)],
        doc_type_hint="cccd",
        doc_type_confidence=0.95,
        engine="fake",
    )
    _install(monkeypatch, conflicted)

    doc = await pipeline.process("case_1", "don.png", _png_bytes())

    assert doc.doc_type == "cccd"
    assert doc.needs_human_review is True


async def test_classifier_agreement_boosts_doc_type_confidence(monkeypatch):
    # Engine đoán đúng nhưng rụt rè; classifier khớp tiêu đề chuẩn → tin cậy hơn.
    agreeing = OcrResult(
        raw_text="GIẤY CHỨNG SINH\nHọ tên mẹ: Nguyễn Thị B",
        fields=[OcrField(key="ho_ten_me", value="Nguyễn Thị B", confidence=0.95)],
        doc_type_hint="giay_chung_sinh",
        doc_type_confidence=0.6,
        engine="fake",
    )
    _install(monkeypatch, agreeing)

    doc = await pipeline.process("case_1", "don.png", _png_bytes())

    assert doc.doc_type == "giay_chung_sinh"
    assert doc.doc_type_confidence >= 0.85
    assert doc.needs_human_review is False


async def test_engine_unknown_falls_back_to_classifier(monkeypatch):
    fallback = OcrResult(
        raw_text="CĂN CƯỚC CÔNG DÂN\nSố: 012345678901",
        fields=[OcrField(key="so_cccd", value="012345678901", confidence=0.95)],
        doc_type_hint="unknown",
        doc_type_confidence=0.0,
        engine="fake",
    )
    _install(monkeypatch, fallback)

    doc = await pipeline.process("case_1", "don.png", _png_bytes())

    assert doc.doc_type == "cccd"
    assert doc.needs_human_review is False


async def test_illegible_regions_force_human_review(monkeypatch):
    result = OcrResult(
        raw_text="Họ tên: [ILLEGIBLE]",
        fields=[OcrField(key="ho_ten", value="", confidence=0.9)],
        doc_type_hint="giay_chung_sinh",
        doc_type_confidence=0.95,
        engine="fake",
        illegible_regions=["dòng họ tên — mực nhòe"],
    )
    _install(monkeypatch, result)

    doc = await pipeline.process("case_1", "don.png", _png_bytes())

    assert doc.needs_human_review is True


async def test_low_overall_ocr_confidence_forces_human_review(monkeypatch):
    result = OcrResult(
        raw_text="ok",
        fields=[OcrField(key="ho_ten", value="A", confidence=0.95)],
        doc_type_hint="giay_chung_sinh",
        doc_type_confidence=0.95,
        engine="fake",
        ocr_confidence=0.5,
    )
    _install(monkeypatch, result)

    doc = await pipeline.process("case_1", "don.png", _png_bytes())

    assert doc.needs_human_review is True
