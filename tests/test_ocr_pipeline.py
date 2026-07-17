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
