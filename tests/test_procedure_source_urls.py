"""Catalog phải trỏ vào URL Cổng DVC còn sống và đọc được.

Bối cảnh (đã kiểm chứng bằng cách fetch thật):
- `thutuc.dichvucong.gov.vn` ngừng phục vụ — 503 toàn subdomain.
- `dichvucong.gov.vn` đã dựng lại thành SPA render phía client; bundle của nó không
  hề đọc tham số `ma_thu_tuc`, nên link cũ trả 200 rồi hiện trang trống.
- `vpcp.dichvucong.gov.vn` trả HTML đầy đủ ngay khi fetch, tra theo mã thủ tục quốc
  gia, và có link tải biểu mẫu thật — nên đây là nguồn trích dẫn dùng được.

Test chạy offline: chỉ khoá định dạng URL, không gọi mạng.
"""

import glob
import json
from urllib.parse import parse_qs, urlparse

from src.services.chat_experience import is_official_url

DEAD_HOST = "thutuc.dichvucong.gov.vn"
SOURCE_HOST = "vpcp.dichvucong.gov.vn"


def _catalog() -> list[tuple[str, dict]]:
    return [
        (path, json.load(open(path, encoding="utf-8")))
        for path in sorted(glob.glob("data/procedures/*.json"))
    ]


def test_catalog_is_not_empty():
    assert _catalog(), "không đọc được data/procedures/*.json"


def test_no_procedure_points_at_the_retired_portal():
    offenders = [
        procedure["id"]
        for _, procedure in _catalog()
        if urlparse(procedure.get("source_url", "")).hostname == DEAD_HOST
    ]
    assert not offenders, f"trỏ vào host đã ngừng phục vụ: {offenders}"


def test_source_urls_stay_on_official_government_hosts():
    for _, procedure in _catalog():
        url = procedure.get("source_url", "")
        assert is_official_url(url), f"{procedure['id']}: nguồn không thuộc danh sách chính thức — {url}"


def test_source_url_code_matches_the_procedure_national_code():
    """URL nguồn phải tra đúng mã thủ tục của chính thủ tục đó.

    Đây là ràng buộc grounding: trích dẫn nguồn mà lại mở ra thủ tục khác thì tệ
    hơn không trích dẫn. Kiểm tra này bắt được cả lỗi copy nhầm URL giữa các file.
    """
    for _, procedure in _catalog():
        url = procedure["source_url"]
        assert urlparse(url).hostname == SOURCE_HOST, (
            f"{procedure['id']}: nguồn phải dùng {SOURCE_HOST} (đọc được không cần JS) — {url}"
        )
        code = parse_qs(urlparse(url).query).get("ma_thu_tuc", [None])[0]
        assert code == procedure["national_code"], (
            f"{procedure['id']}: URL tra mã {code} nhưng thủ tục mang mã {procedure['national_code']}"
        )
