"""Đo chất lượng nhận diện thủ tục — hai bộ eval, hai mục đích khác nhau.

Bộ A (in-catalog): lấy thẳng `example_queries` + `aliases` từ data/procedures/*.json.
    Đây là eval *hồi quy*, không phải eval năng lực: chính những chuỗi này được đưa
    vào index, nên điểm cao là điều kiện cần chứ không chứng minh gì về khả năng
    hiểu cách diễn đạt tự do. Nó tồn tại để bắt lỗi vỡ index/vỡ catalog.

Bộ B (out-of-catalog): câu người dân hay nói, cố ý viết sao cho KHÔNG trùng
    alias/example_query nào. Đây mới là thước đo độ phủ thật.

Chỉ số quan trọng nhất không phải accuracy mà là **tỉ lệ chốt nhầm**: số lần hệ
thống tự tin chọn sai thủ tục. Chốt nhầm kéo theo sai toàn bộ checklist phía sau,
nên nó tệ hơn nhiều so với việc thành thật hỏi lại (AGENTS.md §5).

Chạy: python scripts/eval_identify.py
"""

import asyncio
import glob
import json

from src.agents.nodes import identify

# Bộ B — diễn đạt tự nhiên, không có trong catalog.
OUT_OF_CATALOG: list[tuple[str, str]] = [
    ("khai_sinh", "vợ tôi mới sinh em bé, giờ phải làm gì để bé có giấy tờ"),
    ("khai_sinh", "bé nhà mình sinh ở bệnh viện tuần trước, cần đăng ký gì không"),
    ("khai_sinh", "làm giấy tờ cho trẻ sơ sinh ở đâu"),
    ("ket_hon", "hai đứa tụi mình muốn cưới, ra phường làm gì"),
    ("ket_hon", "thủ tục đăng ký làm vợ chồng hợp pháp"),
    ("ket_hon", "tôi và bạn gái muốn ra giấy tờ chính thức"),
    ("tam_tru", "tôi mới chuyển lên thành phố ở trọ, cần khai báo gì"),
    ("tam_tru", "thuê nhà ở quận khác thì phải đăng ký gì với công an"),
    ("tam_tru", "ở nhờ nhà người quen lâu dài có phải báo không"),
    ("can_cuoc", "cccd của tôi hết hạn rồi làm sao"),
    ("can_cuoc", "mất chứng minh thư thì xin lại kiểu gì"),
    ("can_cuoc", "con tôi đủ 14 tuổi rồi cần làm giấy tờ tùy thân"),
    ("giay_phep_xay_dung", "tôi định xây nhà 2 tầng trên đất của mình"),
    ("giay_phep_xay_dung", "sửa nhà lớn có cần xin phép phường không"),
    ("giay_phep_xay_dung", "muốn cất nhà mới thì thủ tục thế nào"),
]

# Bộ C — GIỮ RIÊNG. Viết ra TRƯỚC khi tinh chỉnh aliases và không được dùng để
# tinh chỉnh, nếu không nó mất giá trị. Bộ B đo "đã sửa được cái đã biết chưa";
# bộ C đo "sửa xong có tổng quát hoá không hay chỉ vá đúng 15 câu kia".
HELD_OUT: list[tuple[str, str]] = [
    ("khai_sinh", "con mới đẻ cần làm thủ tục gì đầu tiên"),
    ("khai_sinh", "đăng ký tên cho con vào sổ hộ tịch"),
    ("khai_sinh", "cháu nhà tôi chưa có giấy tờ gì cả"),
    ("ket_hon", "tụi mình định về chung một nhà, cần giấy tờ gì"),
    ("ket_hon", "xin giấy chứng nhận hai người là vợ chồng"),
    ("ket_hon", "làm đám cưới xong có phải ra phường không"),
    ("tam_tru", "sinh viên thuê phòng trọ có phải khai báo không"),
    ("tam_tru", "tôi ở nhà người thân mấy tháng, cần báo công an không"),
    ("tam_tru", "chuyển chỗ ở mới thì đăng ký thế nào"),
    ("can_cuoc", "thẻ căn cước bị hỏng muốn làm cái mới"),
    ("can_cuoc", "giấy tờ tùy thân của tôi bị mất hết rồi"),
    ("can_cuoc", "cmnd cũ giờ còn dùng được không hay phải đổi"),
    ("giay_phep_xay_dung", "tôi muốn dựng nhà trên mảnh đất mới mua"),
    ("giay_phep_xay_dung", "xây thêm tầng có phải xin phép không"),
    ("giay_phep_xay_dung", "thủ tục cấp phép công trình nhà ở"),
]


def in_catalog_set() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for path in sorted(glob.glob("data/procedures/*.json")):
        procedure = json.load(open(path, encoding="utf-8"))
        for query in procedure.get("example_queries", []) + procedure.get("aliases", [])[:3]:
            pairs.append((procedure["id"], query))
    return pairs


async def run(name: str, cases: list[tuple[str, str]]) -> tuple[int, int, int]:
    hit = 0
    wrong_commit = 0
    misses: list[str] = []
    for expected, query in cases:
        state = await identify.run({"rewritten_query": query, "messages": []})
        chosen = state.get("selected_procedure_id")
        candidates = state.get("candidate_procedures", [])
        top = candidates[0]["procedure_id"] if candidates else None
        if chosen == expected or (chosen is None and top == expected):
            hit += 1
        else:
            # Chốt hẳn một thủ tục khác = chốt nhầm. Trả None = thành thật hỏi lại.
            if chosen is not None:
                wrong_commit += 1
            misses.append(f"    kỳ vọng={expected:<20} chốt={chosen} top={top}  «{query[:44]}»")

    total = len(cases)
    print(f"\n{name}")
    print(f"  Nhận diện đúng : {hit}/{total} = {hit / total * 100:.1f}%")
    print(f"  Chốt NHẦM      : {wrong_commit}/{total} = {wrong_commit / total * 100:.1f}%  ← chỉ số an toàn")
    print(f"  Lùi về hỏi lại : {total - hit - wrong_commit}/{total}")
    if misses:
        print("  Trượt:")
        print("\n".join(misses))
    return hit, wrong_commit, total


async def main() -> None:
    a_hit, a_wrong, a_total = await run("BỘ A — in-catalog (hồi quy index)", in_catalog_set())
    b_hit, b_wrong, b_total = await run("BỘ B — out-of-catalog (độ phủ thật)", OUT_OF_CATALOG)
    c_hit, c_wrong, c_total = await run("BỘ C — held-out (kiểm tổng quát hoá)", HELD_OUT)
    hit, wrong, total = a_hit + b_hit + c_hit, a_wrong + b_wrong + c_wrong, a_total + b_total + c_total
    print("\n" + "=" * 60)
    print(f"TỔNG  nhận diện đúng {hit}/{total}  ·  chốt nhầm {wrong}/{total}")
    return wrong


if __name__ == "__main__":
    # Cổng CI: chỉ chặn trên tỉ lệ chốt nhầm, KHÔNG chặn trên độ chính xác.
    #
    # Độ phủ được phép dao động — nó phụ thuộc từ vựng catalog và sẽ lên xuống mỗi
    # lần thêm/sửa thủ tục, nên đặt ngưỡng cứng ở đó chỉ tạo ra test giòn. Ngược
    # lại, chốt nhầm thủ tục làm sai toàn bộ checklist phía sau: người dân chuẩn bị
    # đúng một bộ giấy tờ cho sai một thủ tục. Đó là lỗi chặn merge, không phải chỉ
    # số cần cải thiện dần (AGENTS.md §5 — thà nói "chưa đủ căn cứ" còn hơn đoán).
    wrong_commits = asyncio.run(main())
    if wrong_commits:
        print(
            f"\n[FAIL] {wrong_commits} ca chốt nhầm thủ tục. Ngưỡng cho phép: 0.\n"
            "       Hệ thống phải lùi về hỏi lại khi không chắc, không được chốt bừa."
        )
        raise SystemExit(1)
    print("\n[OK] Không có ca chốt nhầm nào.")
