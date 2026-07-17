import pytest

from src.services.ocr.classifier import classify
from src.services.ocr.pipeline import process


def test_classifier_uses_document_keywords():
    assert classify("GIẤY CHỨNG SINH") == ("giay_chung_sinh", 0.95)


@pytest.mark.asyncio
async def test_pipeline_rejects_unsafe_upload_and_flags_low_confidence():
    with pytest.raises(ValueError):
        await process("case-1", "payload.exe", b"x")
    document = await process("case-1", "document.png", "CCCD\nNguyen Van A".encode())
    assert document.needs_human_review is True
    assert document.doc_type == "cccd"
