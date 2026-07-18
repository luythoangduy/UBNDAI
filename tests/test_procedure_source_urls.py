"""Catalog phải trỏ vào URL Cổng DVC còn sống.

Bối cảnh: Cổng DVC đã đổi kiến trúc. `thutuc.dichvucong.gov.vn` ngừng phục vụ
(503 toàn subdomain) và định dạng cũ `?ma_thu_tuc=…` không còn được đọc — SPA mới
hoàn toàn không tham chiếu tham số đó, nên link cũ chỉ mở ra trang trống. Test này
chạy offline: nó khoá định dạng URL, không gọi mạng.
"""

import glob
import json
from urllib.parse import urlparse

from src.services.chat_experience import is_official_url

DEAD_HOST = "thutuc.dichvucong.gov.vn"
LEGACY_QUERY = "ma_thu_tuc="
NEW_DETAIL_PATH = "/thu-tuc-hanh-chinh/"


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


def test_migrated_procedures_use_the_current_detail_url_format():
    """Thủ tục đã đối chiếu được trên cổng mới phải dùng URL chi tiết hiện hành.

    giay_phep_xay_dung cố tình nằm ngoài: mã 1.007262 không tra được trên Cổng DVC
    mới, và gán đại sang một mã gần giống (vd 1.009122 "có thời hạn" — thủ tục
    khác) sẽ là bịa mã thủ tục, vi phạm AGENTS.md §5.
    """
    migrated = {"can_cuoc", "ket_hon", "khai_sinh", "tam_tru"}
    seen = set()
    for _, procedure in _catalog():
        if procedure["id"] not in migrated:
            continue
        seen.add(procedure["id"])
        url = procedure["source_url"]
        assert NEW_DETAIL_PATH in url, f"{procedure['id']}: chưa dùng URL chi tiết mới — {url}"
        assert LEGACY_QUERY not in url, f"{procedure['id']}: còn sót định dạng cũ — {url}"
    assert seen == migrated, f"thiếu thủ tục trong catalog: {migrated - seen}"
