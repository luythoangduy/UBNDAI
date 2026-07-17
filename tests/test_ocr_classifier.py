"""Tests cho keyword classifier — chịu được OCR thiếu dấu/sai hoa thường."""

from src.services.ocr.classifier import classify


def test_classifies_cccd_from_standard_title():
    doc_type, confidence = classify(
        "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nCĂN CƯỚC CÔNG DÂN\nSố: 0123456789"
    )
    assert doc_type == "cccd"
    assert confidence >= 0.9


def test_classifies_without_diacritics():
    doc_type, _ = classify("GIAY CHUNG SINH\nHo ten me: Nguyen Thi B\nNoi sinh: BV Tu Du")
    assert doc_type == "giay_chung_sinh"


def test_classifies_marriage_certificate():
    doc_type, confidence = classify("GIẤY CHỨNG NHẬN KẾT HÔN\nHọ tên vợ: ...\nHọ tên chồng: ...")
    assert doc_type == "giay_dang_ky_ket_hon"
    assert confidence > 0.9


def test_classifies_residence_confirmation_by_form_code():
    doc_type, _ = classify("Mẫu CT07\nXác nhận thông tin về cư trú\nNơi thường trú: ...")
    assert doc_type == "giay_xac_nhan_cu_tru"


def test_unrelated_text_is_unknown():
    doc_type, confidence = classify("Biên bản họp lớp ngày 20/11, danh sách đóng quỹ")
    assert doc_type == "unknown"
    assert confidence < 0.5


def test_empty_text_is_unknown():
    assert classify("") == ("unknown", 0.0)
    assert classify("   \n  ") == ("unknown", 0.0)
