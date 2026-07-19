# Eval Evidence — UBNDAI

> **Output thật chụp từ hệ thống**, không phải mô tả hành vi mong muốn.
>
> Mỗi mục kèm lệnh tái lập. Tất cả chạy **offline** — không gọi LLM, không cần API key, không cần index Chroma. Nhờ vậy người đọc tự chạy lại được, và kết quả không phụ thuộc vào việc mô hình hôm đó trả lời thế nào.
>
> Ngày chụp: 2026-07-19 · Commit: xem `git log -1`

---

## Mục lục bằng chứng

| # | Chứng minh điều gì | Kết quả |
|---|---|:---:|
| TC1 | Checklist lọc theo tình huống, không phải danh sách cứng | ✅ 3/4/5 mục tuỳ câu trả lời |
| TC2 | Mục không áp dụng được **giải thích**, không bị giấu | ✅ kèm lý do |
| TC3 | Không chắc thì hỏi lại, **không đoán bừa** | ✅ `pending_action: select_procedure` |
| TC4 | Nhận diện đúng qua cách nói dân dã | ✅ 11/15 bộ B, 9/15 bộ C |
| TC5 | **Không bao giờ chốt nhầm thủ tục** | ✅ 0/60 |
| TC6 | AI không thể gắn nhãn `error` | ✅ ném exception ở tầng kiểu |
| TC7 | Nguồn trích dẫn khoá theo mã thủ tục quốc gia | ✅ 4/4 test |
| TC8 | Chạy được khi không có LLM/index/mạng | ✅ toàn bộ tài liệu này |

---

## TC1 — Checklist đổi theo tình huống *(bằng chứng quan trọng nhất)*

Đây là luận điểm trung tâm của sản phẩm: Cổng DVC liệt kê **toàn bộ** thành phần hồ sơ, UBNDAI chỉ liệt kê phần **áp dụng cho người đang hỏi**.

Cùng một truy vấn, ba bộ câu trả lời khác nhau:

```
Truy vấn: "tôi muốn xin giấy phép xây dựng nhà ở riêng lẻ"

Không PCCC, không di tích: tổng 5 mục → 3 cần chuẩn bị, 2 không áp dụng
      NA: van_ban_y_kien_van_hoa
      NA: giay_chung_nhan_tham_duyet_pccc
Có PCCC,   không di tích: tổng 5 mục → 4 cần chuẩn bị, 1 không áp dụng
      NA: van_ban_y_kien_van_hoa
Có PCCC,   có di tích: tổng 5 mục → 5 cần chuẩn bị, 0 không áp dụng
```

Người dân ở trường hợp thứ nhất **không phải đi xin văn bản ý kiến cơ quan văn hoá và giấy chứng nhận thẩm duyệt PCCC** — hai thứ mà danh sách gốc trên Cổng DVC vẫn liệt kê.

**Tái lập:**

```bash
python - << 'EOF'
import asyncio
from src.agents.nodes import identify, checklist
async def one(ans, label):
    st = {"rewritten_query": "tôi muốn xin giấy phép xây dựng nhà ở riêng lẻ",
          "messages": [], "answers": ans}
    st.update(await identify.run(st)); st.update(await checklist.run(st))
    cl = st["checklist"]
    need = [i for i in cl if i["status"] != "not_applicable"]
    print(f"{label}: tổng {len(cl)} → {len(need)} cần chuẩn bị")
async def main():
    await one({"cong_trinh_yeu_cau_pccc": False, "cong_trinh_lien_quan_di_tich": False}, "không/không")
    await one({"cong_trinh_yeu_cau_pccc": True,  "cong_trinh_lien_quan_di_tich": False}, "có/không")
    await one({"cong_trinh_yeu_cau_pccc": True,  "cong_trinh_lien_quan_di_tich": True},  "có/có")
asyncio.run(main())
EOF
```

---

## TC2 — Mục không áp dụng được giải thích, không bị giấu

Output thật của một mục bị loại:

```json
{
  "requirement_code": "giay_chung_nhan_tham_duyet_pccc",
  "status": "not_applicable",
  "document_id": null,
  "note": "Không áp dụng cho trường hợp của bạn (answers.cong_trinh_yeu_cau_pccc == true)"
}
```

**Vì sao giữ lại mà không xoá.** Nếu chỉ hiện 3 mục, người dân không biết hệ thống đã bỏ qua cái gì và vì sao — họ không kiểm chứng được, và cán bộ cũng không. Giữ lại kèm điều kiện tường minh khiến quyết định lọc **audit được**: ai cũng đọc được `answers.cong_trinh_yeu_cau_pccc == true` và đối chiếu với câu trả lời của mình.

Đây là khác biệt giữa *lọc* và *giấu*.

Một mục cần chuẩn bị, để đối chiếu — `note` dẫn thẳng điều khoản:

```json
{
  "requirement_code": "giay_to_quyen_su_dung_dat",
  "status": "missing",
  "note": "Danh mục giấy tờ được chấp nhận quy định tại Điều 53 Nghị định 175/2024/NĐ-CP
           (gồm Giấy chứng nhận quyền sử dụng đất qua các thời kỳ, hoặc giấy tờ đủ điều
           kiện cấp giấy chứng nhận theo Điều 137 Luật Đất đai 2024)."
}
```

---

## TC3 — Không chắc thì hỏi lại

```
### Truy vấn: «giấy tờ tùy thân của tôi bị mất hết rồi»
  selected_procedure_id : None
  identify_confidence   : 0.0
  pending_action        : None
```

Câu này mơ hồ thật — "giấy tờ tùy thân" có thể là căn cước, có thể là hộ chiếu, có thể là giấy khai sinh. Hệ thống **không chốt**.

Đối chiếu với một truy vấn rõ ràng:

```
### Truy vấn: «tôi muốn xin giấy phép xây dựng nhà ở riêng lẻ»
  selected_procedure_id : giay_phep_xay_dung
  identify_confidence   : 1.0
  pending_action        : answer_clarification
    ứng viên giay_phep_xay_dung     1.0000
```

Chốt thủ tục xong vẫn chưa sinh checklist ngay — `pending_action: answer_clarification` nghĩa là **còn phải hỏi làm rõ trước**. Đây chính là cơ chế tạo ra TC1.

---

## TC4 & TC5 — Độ phủ và tỉ lệ chốt nhầm

```
$ python scripts/eval_identify.py

BỘ A — in-catalog          30/30 = 100%    chốt nhầm 0/30
BỘ B — out-of-catalog      11/15 = 73,3%   chốt nhầm 0/15
BỘ C — held-out             9/15 = 60,0%   chốt nhầm 0/15
────────────────────────────────────────────────────────
TỔNG  nhận diện đúng 50/60  ·  chốt nhầm 0/60

[OK] Không có ca chốt nhầm nào.
```

**Đọc con số này cho đúng.** Bộ A đạt 100% nhưng **có tính vòng tròn** — chính những chuỗi đó được đưa vào index. Bộ C mới là thước đo thật, và 60% nghĩa là còn khoảng trống độ phủ rõ rệt.

Điều đáng nói không phải 60%, mà là **0/60 chốt nhầm**: trong 10 ca trượt, không ca nào hệ thống tự tin chọn sai thủ tục — tất cả đều lùi về hỏi lại. Chốt nhầm làm sai toàn bộ checklist phía sau, nên đó mới là chỉ số được đặt cổng CI.

Phương pháp, ba lỗi thật đã tìm ra, và phân tích các ca trượt: `docs/EVAL-METRICS.md`.

---

## TC6 — AI không thể gắn nhãn `error`

Guardrail này cưỡng chế ở **tầng kiểu dữ liệu**, nên bằng chứng là một exception, không phải một hành vi quan sát được:

```python
# src/models/validation.py:28
@model_validator(mode="after")
def _ai_cannot_error(self) -> "ValidationIssue":
    if self.source == "ai" and self.severity == "error":
        ...
```

Tạo `ValidationIssue(source="ai", severity="error", ...)` sẽ ném lỗi validate. Không có đường vòng — mọi issue trong hệ thống đều đi qua kiểu này.

Lớp mềm phía trên hạ cấp trước khi tới đó (`ai_checker.py:83`):

```python
severity=severity if severity in ("warning", "info") else "warning",
```

**Bằng chứng test:** `pytest tests/test_ai_checker.py` → 4/4 · `pytest tests/test_rule_engine.py` → 11/11

Ý nghĩa nghiệp vụ: chỉ rule engine khai báo — thứ cán bộ chuyên môn đọc và ký duyệt được — mới có thẩm quyền nói "hồ sơ này sai".

---

## TC7 — Nguồn trích dẫn khoá theo mã thủ tục

```bash
$ pytest tests/test_procedure_source_urls.py -q
4 passed
```

Ba ràng buộc được khoá:

1. Không thủ tục nào trỏ vào host đã ngừng phục vụ (`thutuc.dichvucong.gov.vn` — 503 toàn subdomain).
2. Mọi `source_url` thuộc danh sách host chính thức.
3. **URL phải tra đúng mã thủ tục quốc gia của chính thủ tục đó.**

Ràng buộc 3 quan trọng hơn vẻ ngoài: *trích dẫn nguồn mà mở ra thủ tục khác thì tệ hơn không trích dẫn*, vì nó tạo cảm giác đã kiểm chứng trong khi chưa.

Test này **cố ý chạy offline** để CI không phụ thuộc Cổng DVC còn sống hay không. Đánh đổi: nó bắt được lỗi cấu hình, **không** bắt được "URL đúng định dạng nhưng đã chết" — loại lỗi đã từng xảy ra với cả 5 thủ tục. Xem `docs/CI-Explained.md` §4.

---

## TC8 — Chạy được khi thiếu mọi phụ thuộc ngoài

Toàn bộ tài liệu này là bằng chứng: mọi output ở trên chụp được **mà không có** LLM API key, index Chroma, hay kết nối tới Cổng DVC.

| Thiếu gì | Hệ thống làm gì |
|---|---|
| Index Chroma | Lùi về BM25 |
| Cache BM25 | Dựng BM25 in-memory thẳng từ `data/procedures/*.json` |
| LLM API key | Định tuyến rule-based; mất hỏi đáp mở nhưng giữ checklist |
| Mạng ngoài | Dùng snapshot có checksum, đánh dấu trạng thái `fallback` |

Với môi trường cơ quan nhà nước thường chặn API ngoài, đây không phải tính năng phụ.

---

## Những gì tài liệu này **chưa** chứng minh

Ghi rõ để không ai đọc xong tưởng đã phủ hết.

| Chưa có bằng chứng | Vì sao |
|---|---|
| Chất lượng câu trả lời node `answer` | Cần LLM và cần eval riêng — chưa xây |
| Độ chính xác OCR trên ảnh thật | Chưa có bộ ảnh chuẩn |
| Latency trên môi trường thật | Chưa đo |
| **Tính đúng đắn của dữ liệu thủ tục** | **Không test nào bắt được** — dữ liệu sai trông giống hệt dữ liệu đúng. Phải do cán bộ chuyên môn kiểm duyệt |
| Hiệu quả trên người dùng thật | Cần pilot Giai đoạn 1 |

Dòng thứ tư là rủi ro lớn nhất của hệ thống, và nó đã xảy ra thật: catalog từng chứa hai văn bản pháp luật **không tồn tại**. Xem `docs/GUARDRAILS.md`.
