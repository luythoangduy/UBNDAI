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
    print("\n" + "=" * 60)
    print(f"TỔNG  nhận diện đúng {a_hit + b_hit}/{a_total + b_total}"
          f"  ·  chốt nhầm {a_wrong + b_wrong}/{a_total + b_total}")


if __name__ == "__main__":
    asyncio.run(main())
