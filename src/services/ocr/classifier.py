"""Phân loại loại giấy tờ VN từ ảnh. Owner: Dev B.

MVP doc_types: cccd, giay_chung_sinh, giay_dang_ky_ket_hon, giay_xac_nhan_cu_tru.
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
}

_MIN_CONFIDENCE = 0.5
_MAX_CONFIDENCE = 0.98


def _fold(text: str) -> str:
    """Bỏ dấu + lowercase để so khớp bền với OCR thiếu dấu/sai dấu."""
    normalized = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D").casefold()


def classify(raw_text: str) -> tuple[str, float]:
    """Trả (doc_type, confidence). doc_type='unknown' khi không khớp."""
    folded = _fold(raw_text)
    if not folded.strip():
        return "unknown", 0.0

    best_type, best_score = "unknown", 0.0
    for doc_type, keywords in _DOC_TYPE_KEYWORDS.items():
        score = sum(weight for keyword, weight in keywords if keyword in folded)
        if score > best_score:
            best_type, best_score = doc_type, score

    confidence = min(_MAX_CONFIDENCE, best_score)
    if confidence < _MIN_CONFIDENCE:
        return "unknown", confidence
    return best_type, confidence
