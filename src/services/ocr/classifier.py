"""Phân loại loại giấy tờ VN từ ảnh. Owner: Dev B.

MVP doc_types: cccd, giay_chung_sinh, giay_dang_ky_ket_hon, giay_xac_nhan_cu_tru.
Cách tiếp cận MVP: keyword matching trên raw OCR text (tiêu đề giấy tờ chuẩn nhà nước
rất đặc trưng) + layout heuristics. Nâng cấp classifier ML sau nếu cần.
"""


def classify(raw_text: str) -> tuple[str, float]:
    """Trả (doc_type, confidence). doc_type='unknown' khi không khớp."""
    raise NotImplementedError  # TODO(B) Sprint 1
