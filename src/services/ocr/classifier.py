"""Phân loại loại giấy tờ VN từ ảnh. Owner: Dev B.

Document types are aligned with the procedure catalog and the Vision structured-output schema.
Cách tiếp cận MVP: keyword matching trên raw OCR text (tiêu đề giấy tờ chuẩn nhà nước
rất đặc trưng) + layout heuristics. Nâng cấp classifier ML sau nếu cần.

Dùng làm cross-check với doc_type_hint của VisionLlmEngine, và là classifier chính
khi engine là PaddleOCR/Google Vision (chỉ trả raw text).
"""

from __future__ import annotations

import unicodedata

# (keyword đã bỏ dấu, trọng số). Tiêu đề chuẩn nhà nước = trọng số cao;
# trường đặc trưng phụ = trọng số thấp, cộng dồn.
_DOC_TYPE_KEYWORDS: dict[str, list[tuple[str, float]]] = {
    "cccd": [
        ("can cuoc cong dan", 0.9),
        ("citizen identity", 0.9),
        ("cccd", 0.7),
        ("can cuoc", 0.7),
        ("so dinh danh ca nhan", 0.3),
        ("quoc tich", 0.1),
        ("dac diem nhan dang", 0.2),
    ],
    "giay_chung_sinh": [
        ("giay chung sinh", 0.9),
        ("nguoi do de", 0.2),
        ("noi sinh", 0.1),
        ("ho ten me", 0.1),
    ],
    "giay_dang_ky_ket_hon": [
        ("giay chung nhan ket hon", 0.9),
        ("dang ky ket hon", 0.8),
        ("ket hon", 0.2),
        ("ho ten vo", 0.1),
        ("ho ten chong", 0.1),
    ],
    "giay_xac_nhan_cu_tru": [
        ("xac nhan thong tin ve cu tru", 0.9),
        ("xac nhan cu tru", 0.8),
        ("ct07", 0.6),
        ("noi thuong tru", 0.2),
        ("chu ho", 0.1),
    ],
    "ho_chieu": [
        ("ho chieu", 0.9),
        ("passport", 0.9),
        ("socialist republic of viet nam", 0.2),
    ],
    "to_khai_dang_ky_ket_hon": [
        ("to khai dang ky ket hon", 0.98),
        ("thong tin ben nam va ben nu", 0.3),
    ],
    "to_khai_khai_sinh": [
        ("to khai dang ky khai sinh", 0.98),
        ("thong tin nguoi duoc khai sinh", 0.3),
    ],
    "giay_to_cu_tru": [
        ("giay to chung minh noi cu tru", 0.9),
        ("giay to chung minh cu tru", 0.9),
    ],
    "to_khai_ct01": [
        ("to khai thay doi thong tin cu tru", 0.9),
        ("mau ct01", 0.9),
        ("ct01", 0.7),
    ],
    "giay_to_cho_o_hop_phap": [
        ("giay to chung minh cho o hop phap", 0.95),
        ("hop dong thue nha", 0.8),
    ],
    "van_ban_dong_y_nguoi_giam_ho": [
        ("van ban dong y cua nguoi dai dien theo phap luat", 0.95),
        ("y kien dong y cua cha me", 0.8),
        ("nguoi giam ho dong y", 0.8),
    ],
    "van_ban_lam_chung": [
        ("van ban cua nguoi lam chung", 0.95),
        ("nguoi lam chung ve viec sinh", 0.8),
    ],
    "van_ban_cam_doan_viec_sinh": [
        ("giay cam doan ve viec sinh", 0.95),
        ("cam doan ve viec sinh", 0.85),
    ],
    "phieu_cc01": [
        ("mau cc01", 0.95),
        ("cc01", 0.8),
        ("phieu thu thap thong tin dan cu", 0.2),
    ],
    "phieu_dc01": [
        ("mau dc01", 0.95),
        ("dc01", 0.8),
        ("phieu thu thap thong tin dan cu", 0.2),
    ],
    "phieu_dc02": [
        ("mau dc02", 0.95),
        ("dc02", 0.8),
        ("phieu cap nhat thong tin dan cu", 0.3),
    ],
    "giay_to_phap_ly": [
        ("giay to phap ly ve thong tin cong dan", 0.95),
        ("giay to phap ly", 0.7),
    ],
    "don_de_nghi_cap_phep": [
        ("don de nghi cap giay phep xay dung", 0.98),
        ("mau so 01 phu luc ii", 0.7),
    ],
    "giay_to_quyen_su_dung_dat": [
        ("giay chung nhan quyen su dung dat", 0.98),
        ("quyet dinh giao dat", 0.8),
        ("hop dong thue dat", 0.8),
    ],
    "ban_ve_thiet_ke_xay_dung": [
        ("ban ve thiet ke xay dung", 0.98),
        ("mat bang mat dung mat cat", 0.7),
    ],
    "van_ban_y_kien_van_hoa": [
        ("van ban y kien cua co quan quan ly van hoa", 0.95),
        ("co quan quan ly van hoa cap tinh", 0.8),
    ],
    "giay_chung_nhan_tham_duyet_pccc": [
        ("giay chung nhan tham duyet thiet ke phong chay chua chay", 0.98),
        ("tham duyet pccc", 0.8),
    ],
}

SUPPORTED_DOCUMENT_TYPES = tuple(_DOC_TYPE_KEYWORDS) + (
    "don_viet_tay",
    "van_ban_hanh_chinh",
)

_MIN_CONFIDENCE = 0.5
_MAX_CONFIDENCE = 0.98


def _fold(text: str) -> str:
    """Bỏ dấu + lowercase để so khớp bền với OCR thiếu dấu/sai dấu."""
    normalized = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D").casefold()


def _keyword_score(folded: str, keywords: list[tuple[str, float]]) -> float:
    matched = [(keyword, weight) for keyword, weight in keywords if keyword in folded]
    return sum(
        weight
        for keyword, weight in matched
        if not any(keyword != other and keyword in other for other, _ in matched)
    )


def classify(raw_text: str) -> tuple[str, float]:
    """Trả (doc_type, confidence). doc_type='unknown' khi không khớp."""
    folded = _fold(raw_text)
    if not folded.strip():
        return "unknown", 0.0

    best_type, best_score = "unknown", 0.0
    for doc_type, keywords in _DOC_TYPE_KEYWORDS.items():
        score = _keyword_score(folded, keywords)
        if score > best_score:
            best_type, best_score = doc_type, score

    confidence = min(_MAX_CONFIDENCE, best_score)
    if confidence < _MIN_CONFIDENCE:
        return "unknown", confidence
    return best_type, confidence
