# Evaluation Metrics — UBNDAI

> Các chỉ số đánh giá hệ thống, kèm **baseline đo thật** và lệnh tái lập.
>
> Nguyên tắc chọn chỉ số: với hệ thống hướng dẫn thủ tục hành chính, **"nói sai" tệ hơn nhiều so với "không biết"**. Vì vậy chỉ số quan trọng nhất trong tài liệu này không phải độ chính xác, mà là **tỉ lệ chốt nhầm** — số lần hệ thống tự tin chọn sai thủ tục.

---

## 1. Bảng chỉ số có baseline

| # | Nhóm | Chỉ số | **Baseline** | Cách đo |
|---|---|---|:---:|---|
| 1 | Nhận diện | Độ chính xác — in-catalog | **30/30 = 100%** | `python scripts/eval_identify.py` (bộ A) |
| 2 | Nhận diện | Độ chính xác — **out-of-catalog** | **9/15 = 60%** | `python scripts/eval_identify.py` (bộ B) |
| 3 | **An toàn** | **Tỉ lệ chốt nhầm thủ tục** | **0/45 = 0%** | Cả hai bộ eval |
| 4 | An toàn | Lùi về hỏi lại khi không chắc | 6/15 trên bộ B | Bộ B |
| 5 | Kiểm thử | Toàn bộ suite | **329/330 PASS** | `python -m pytest -q` |
| 6 | Kiểm thử | Rule engine (tầng duy nhất phát `error`) | **11/11** | `pytest tests/test_rule_engine.py` |
| 7 | Kiểm thử | AI checker (chỉ warning/info) | **4/4** | `pytest tests/test_ai_checker.py` |
| 8 | Kiểm thử | OCR pipeline | **19/19** | `pytest tests/test_ocr_pipeline.py` |
| 9 | Kiểm thử | Hồi quy agent | **20/20** | `pytest tests/test_agent_regressions.py` |
| 10 | Kiểm thử | Tình huống người dùng thật | **15/15** | `pytest tests/test_real_user_edge_cases.py` |
| 11 | Kiểm thử | Trung thực nguồn live | **7/7** | `pytest tests/test_chat_experience.py` |
| 12 | Kiểm thử | Khoá URL nguồn theo mã thủ tục | **4/4** | `pytest tests/test_procedure_source_urls.py` |
| 13 | Chi phí | Token tiếng Việt | **2,17 ký tự/token** | `count_tokens` trên prompt planner thật |
| 14 | Chi phí | Chi phí LLM / hồ sơ | **~0,016 USD** | `docs/business-viability-pilot.md` §6 |
| 15 | Độ phủ | Thủ tục · rule khai báo | **5 thủ tục · 17 rule** | `data/procedures/`, `rules/` |
| 16 | Độ phủ | Endpoint API | **75** | `docs/API-Reference.md` §10 |

---

## 2. Kết quả quan trọng nhất: chốt nhầm = 0

```
python scripts/eval_identify.py

BỘ A — in-catalog (hồi quy index)
  Nhận diện đúng : 30/30 = 100.0%
  Chốt NHẦM      : 0/30 = 0.0%
  Lùi về hỏi lại : 0/30

BỘ B — out-of-catalog (độ phủ thật)
  Nhận diện đúng : 9/15 = 60.0%
  Chốt NHẦM      : 0/15 = 0.0%
  Lùi về hỏi lại : 6/15

TỔNG  nhận diện đúng 39/45  ·  chốt nhầm 0/45
```

**Cách đọc kết quả này.**

Trên 15 câu diễn đạt tự nhiên không có trong catalog, hệ thống nhận đúng 9 câu. Sáu câu còn lại nó **không nhận ra** — nhưng trong cả sáu, nó trả `selected_procedure_id = None` và chuyển sang hỏi người dân chọn thủ tục (`pending_action: "select_procedure"`, `src/agents/nodes/identify.py:133`).

Không có ca nào hệ thống tự tin chốt sai thủ tục. Đây là điều quan trọng, vì **chốt nhầm thủ tục làm sai toàn bộ checklist phía sau** — người dân sẽ chuẩn bị đúng một bộ giấy tờ cho sai một thủ tục. Thất bại kiểu "tôi chưa rõ, bạn chọn giúp" tốn một lượt hội thoại; thất bại kiểu "chắc chắn là thủ tục X" tốn một chuyến đi lên phường.

Ba ngưỡng tạo ra hành vi này (`src/config.py:53-55`):

```python
identify_confidence_threshold = 0.55   # dưới ngưỡng → không chốt
identify_min_relevance       = 0.6     # ứng viên yếu bị loại
identify_min_margin          = 0.15    # hai ứng viên sát nhau → hỏi lại
```

Ví dụ minh hoạ: `"tôi và bạn gái muốn ra giấy tờ chính thức"` cho `confidence = 1.00` với ứng viên `can_cuoc` — nhưng điểm liên quan dưới `identify_min_relevance`, nên hệ thống vẫn không chốt. Ngưỡng liên quan chặn được ca mà ngưỡng tự tin bỏ lọt.

---

## 3. Khoảng trống đã lộ ra: độ phủ 60%

Đây là phát hiện đáng giá nhất của đợt đo, và nó là **vấn đề dữ liệu, không phải vấn đề mô hình**.

| Câu trượt | Kỳ vọng | Ứng viên đứng đầu |
|---|---|---|
| "thủ tục đăng ký làm vợ chồng hợp pháp" | `ket_hon` | *(không có)* |
| "tôi và bạn gái muốn ra giấy tờ chính thức" | `ket_hon` | `can_cuoc` |
| "thuê nhà ở quận khác thì phải đăng ký gì với công an" | `tam_tru` | `giay_phep_xay_dung` |
| "ở nhờ nhà người quen lâu dài có phải báo không" | `tam_tru` | `giay_phep_xay_dung` |
| "cccd của tôi hết hạn rồi làm sao" | `can_cuoc` | *(không có)* |
| "mất chứng minh thư thì xin lại kiểu gì" | `can_cuoc` | `ket_hon` |

Quy luật rõ ràng: hệ thống trượt khi người dân dùng **từ dân dã hoặc từ cũ** — "cccd", "chứng minh thư", "vợ chồng hợp pháp", "ở trọ", "ở nhờ". Đây đúng là cách người dân thật nói, đặc biệt nhóm ít thành thạo văn bản hành chính — tức là **đúng nhóm sản phẩm nhắm tới**.

**Cách sửa: bổ sung `aliases` và `negative_keywords` trong `data/procedures/*.json`, không sửa code.** Hai ca "thuê nhà"/"ở nhờ" bị `giay_phep_xay_dung` hút mất cho thấy `negative_keywords` của thủ tục xây dựng cần loại thêm các từ về thuê/trọ/ở nhờ.

Đây là chi phí kiểu "kiểm duyệt dữ liệu" đã nêu ở `docs/business-viability-pilot.md` §6.3 — và là lý do Giai đoạn 2 của pilot đo **giờ công mỗi thủ tục** chứ không đo chi phí hạ tầng.

---

## 4. Giới hạn của phép đo này

Ghi rõ để không ai trích con số ra khỏi ngữ cảnh.

- **Bộ A có tính vòng tròn.** `example_queries` và `aliases` chính là dữ liệu được index, nên 100% là *điều kiện cần*, không chứng minh năng lực hiểu ngôn ngữ. Nó là eval hồi quy để bắt lỗi vỡ index — đúng như mô tả trong `scripts/eval_identify.py`.
- **Bộ B chỉ có 15 câu, do tôi tự viết.** Nó không phải mẫu đại diện thống kê cho cách người dân thật đặt câu hỏi. Con số 60% nên đọc là "có khoảng trống độ phủ rõ rệt", không phải "độ phủ chính xác bằng 60%".
- **Chưa có eval cho chất lượng câu trả lời của node `answer`.** Đây là khoảng trống lớn nhất — xem §6.
- **Chưa đo latency trên môi trường thật.**
- **Chưa đo tỉ lệ OCR rơi vào `needs_human_review`** trên ảnh thật.

---

## 5. Chỉ số vận hành cho pilot

Các chỉ số dưới đây **chưa có baseline** vì chúng cần người dùng thật. Chúng là thứ Giai đoạn 1 của pilot phải đo (`docs/business-viability-pilot.md` §7-8).

| Chỉ số | Vì sao |
|---|---|
| **Tỷ lệ hồ sơ đạt ngay lần nộp đầu** | Chỉ số Bắc Đẩu |
| Số sai sót nội dung do cán bộ báo cáo | Tiêu chí loại — phải bằng 0 |
| Tỷ lệ trả lời "chưa đủ căn cứ" | Cao = catalog thiếu, không phải mô hình kém |
| Tỷ lệ hội thoại phải hỏi lại để chọn thủ tục | Đo trực tiếp khoảng trống ở §3 trên người thật |
| Tỷ lệ OCR → `needs_human_review` | Hiệu chỉnh ngưỡng 0,85 |
| Số lượt trung bình mỗi phiên | Kiểm chứng mô hình chi phí |

**Chỉ số cố tình không dùng:** số lượt chat, thời gian trên trang. Người dân dùng ít mà xong việc là kết quả tốt.

---

## 6. Việc nên làm tiếp

Xếp theo giá trị trên công sức:

1. **Mở rộng `aliases`/`negative_keywords` cho 5 thủ tục** rồi chạy lại bộ B. Sửa JSON, không sửa code. Đây là cách rẻ nhất để đẩy 60% lên.
2. **Mở rộng bộ B lên 50–100 câu**, tốt nhất lấy từ câu hỏi thật ở Bộ phận Một cửa thay vì tự nghĩ.
3. **Xây eval cho node `answer`** — chấm xem câu trả lời có bám nguồn đã truy hồi không, và có nói "chưa đủ căn cứ" đúng lúc không. Đây là guardrail yếu nhất (`docs/GUARDRAILS.md` lớp 4) mà lại chưa có phép đo nào.
4. **Đo latency** trên môi trường thật.
5. **Đưa `scripts/eval_identify.py` vào CI** với ngưỡng chặn: chốt nhầm phải bằng 0. Độ phủ có thể dao động, nhưng chốt nhầm khác 0 là lỗi chặn merge.

---

## 7. Tái lập toàn bộ

```bash
# Nhận diện thủ tục (bộ A + bộ B)
python scripts/eval_identify.py

# Toàn bộ test suite
python -m pytest -q

# Theo nhóm guardrail
pytest tests/test_rule_engine.py tests/test_ai_checker.py \
       tests/test_ocr_pipeline.py tests/test_chat_experience.py \
       tests/test_procedure_source_urls.py -q

# Độ phủ catalog
ls data/procedures/*.json | wc -l
for f in rules/*.yaml; do echo "$f: $(grep -c '^\s*- id:' $f)"; done
```

> **Về 1 test failing.** `test_application_migrations.py::test_application_migration_round_trip_preserves_baseline_data` fail local nhưng **CI xanh trên 5 lần chạy `main` gần nhất**. Artifact môi trường local. Ghi ra thay vì báo 330/330 cho đẹp.
