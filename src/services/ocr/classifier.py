"""Phân loại loại giấy tờ VN từ ảnh. Owner: Dev B.

MVP doc_types: cccd, giay_chung_sinh, giay_dang_ky_ket_hon, giay_xac_nhan_cu_tru.
Cách tiếp cận MVP: keyword matching trên raw OCR text (tiêu đề giấy tờ chuẩn nhà nước
rất đặc trưng) + layout heuristics. Nâng cấp classifier ML sau nếu cần.
"""


def classify(raw_text: str) -> tuple[str, float]:
    """Trả (doc_type, confidence). doc_type='unknown' khi không khớp."""
    normalized = raw_text.casefold()
    patterns = {
        "giay_chung_sinh": ("giấy chứng sinh", "giay chung sinh", "birth certificate"),
        "cccd": ("căn cước công dân", "can cuoc cong dan", "căn cước", "cccd"),
        "giay_dang_ky_ket_hon": ("đăng ký kết hôn", "dang ky ket hon"),
        "giay_xac_nhan_cu_tru": ("xác nhận cư trú", "xac nhan cu tru"),
    }
    for doc_type, keywords in patterns.items():
        if any(keyword in normalized for keyword in keywords):
            return doc_type, 0.95
    return "unknown", 0.25
