"""Tests cho keyword classifier — chịu được OCR thiếu dấu/sai hoa thường."""

import pytest

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


def test_specific_marriage_declaration_title_beats_generic_marriage_terms():
    doc_type, confidence = classify("TO KHAI DANG KY KET HON")

    assert doc_type == "to_khai_dang_ky_ket_hon"
    assert confidence >= 0.9


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


@pytest.mark.parametrize(
    ("raw_text", "expected_type"),
    [
        ("HO CHIEU / PASSPORT - Socialist Republic of Viet Nam", "ho_chieu"),
        ("TO KHAI DANG KY KET HON - thong tin ben nam va ben nu", "to_khai_dang_ky_ket_hon"),
        ("TO KHAI DANG KY KHAI SINH - thong tin nguoi duoc khai sinh", "to_khai_khai_sinh"),
        ("GIAY TO CHUNG MINH NOI CU TRU cua nguoi yeu cau", "giay_to_cu_tru"),
        ("MAU CT01 - TO KHAI THAY DOI THONG TIN CU TRU", "to_khai_ct01"),
        ("GIAY TO CHUNG MINH CHO O HOP PHAP", "giay_to_cho_o_hop_phap"),
        ("VAN BAN DONG Y CUA NGUOI DAI DIEN THEO PHAP LUAT", "van_ban_dong_y_nguoi_giam_ho"),
        ("VAN BAN CUA NGUOI LAM CHUNG VE VIEC SINH", "van_ban_lam_chung"),
        ("GIAY CAM DOAN VE VIEC SINH", "van_ban_cam_doan_viec_sinh"),
        ("MAU CC01 - PHIEU THU THAP THONG TIN DAN CU", "phieu_cc01"),
        ("MAU DC01 - PHIEU THU THAP THONG TIN DAN CU", "phieu_dc01"),
        ("MAU DC02 - PHIEU CAP NHAT THONG TIN DAN CU", "phieu_dc02"),
        ("GIAY TO PHAP LY VE THONG TIN CONG DAN", "giay_to_phap_ly"),
        ("DON DE NGHI CAP GIAY PHEP XAY DUNG - MAU SO 01", "don_de_nghi_cap_phep"),
        ("GIAY CHUNG NHAN QUYEN SU DUNG DAT", "giay_to_quyen_su_dung_dat"),
        ("BAN VE THIET KE XAY DUNG - MAT BANG MAT DUNG MAT CAT", "ban_ve_thiet_ke_xay_dung"),
        ("VAN BAN Y KIEN CUA CO QUAN QUAN LY VAN HOA CAP TINH", "van_ban_y_kien_van_hoa"),
        ("GIAY CHUNG NHAN THAM DUYET THIET KE PHONG CHAY CHUA CHAY", "giay_chung_nhan_tham_duyet_pccc"),
    ],
)
def test_classifies_all_catalog_document_families(raw_text, expected_type):
    doc_type, confidence = classify(raw_text)

    assert doc_type == expected_type
    assert confidence >= 0.5


def test_multiline_title_is_classified_correctly():
    """Tiêu đề giấy tờ xuống dòng vẫn phải nhận đúng loại.

    Hồi quy lỗi thật: giấy chứng nhận quyền sử dụng đất in "GIẤY CHỨNG NHẬN" ở
    một dòng và "QUYỀN SỬ DỤNG ĐẤT, ..." ở dòng dưới. Trước khi _fold gộp khoảng
    trắng, keyword liền mạch "giay chung nhan quyen su dung dat" không khớp được
    qua ký tự xuống dòng, điểm rơi về keyword phụ, và sổ đỏ bị phân loại thành
    'cccd' — chỉ vì trong đó có dòng "CCCD: ..." của chủ đất. Hệ quả với người
    dùng: đã tải đúng giấy tờ nhưng checklist vẫn báo thiếu.

    Cùng một nguyên nhân từng làm hỏng cả ban_ve_thiet_ke_xay_dung và
    giay_chung_nhan_tham_duyet_pccc, nên test phủ cả ba.
    """
    so_do = (
        "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
        "GIẤY CHỨNG NHẬN\n"
        "QUYỀN SỬ DỤNG ĐẤT, QUYỀN SỞ HỮU TÀI SẢN GẮN LIỀN VỚI ĐẤT\n"
        "1. Người sử dụng đất: Ông Nguyễn Văn A, số CCCD: 123456789012\n"
    )
    doc_type, confidence = classify(so_do)
    assert doc_type == "giay_to_quyen_su_dung_dat", f"nhận nhầm thành {doc_type}"
    assert confidence >= 0.9

    ban_ve, _ = classify("BẢN VẼ THIẾT KẾ\nXÂY DỰNG\nMặt bằng - mặt đứng - mặt cắt")
    assert ban_ve == "ban_ve_thiet_ke_xay_dung"

    pccc, _ = classify("GIẤY CHỨNG NHẬN THẨM DUYỆT\nTHIẾT KẾ PHÒNG CHÁY CHỮA CHÁY")
    assert pccc == "giay_chung_nhan_tham_duyet_pccc"
