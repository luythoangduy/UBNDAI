# Evaluation Metrics — UBNDAI

> Các chỉ số đánh giá hệ thống, kèm **baseline đo thật** và lệnh tái lập.
>
> Nguyên tắc chọn chỉ số: với hệ thống hướng dẫn thủ tục hành chính, **"nói sai" tệ hơn nhiều so với "không biết"**. Vì vậy chỉ số quan trọng nhất trong tài liệu này không phải độ chính xác, mà là **tỉ lệ chốt nhầm** — số lần hệ thống tự tin chọn sai thủ tục. Chốt nhầm làm sai toàn bộ checklist phía sau: người dân chuẩn bị đúng một bộ giấy tờ cho sai một thủ tục.

---

## 1. Bảng chỉ số có baseline

| # | Nhóm | Chỉ số | **Baseline** | Cách đo |
|---|---|---|:---:|---|
| 1 | **An toàn** | **Tỉ lệ chốt nhầm thủ tục** | **0/60 = 0%** | `python scripts/eval_identify.py` |
| 2 | Nhận diện | Độ chính xác — in-catalog (bộ A) | **30/30 = 100%** | bộ A |
| 3 | Nhận diện | Độ chính xác — out-of-catalog (bộ B) | **11/15 = 73,3%** | bộ B |
| 4 | Nhận diện | Độ chính xác — **held-out (bộ C)** | **9/15 = 60,0%** | bộ C |
| 5 | An toàn | Lùi về hỏi lại khi không chắc | 10/30 trên B+C | bộ B, C |
| 6 | Kiểm thử | Toàn bộ suite | **329/330 PASS** | `python -m pytest -q` |
| 7 | Kiểm thử | Rule engine (tầng duy nhất phát `error`) | **11/11** | `pytest tests/test_rule_engine.py` |
| 8 | Kiểm thử | AI checker (chỉ warning/info) | **4/4** | `pytest tests/test_ai_checker.py` |
| 9 | Kiểm thử | OCR pipeline | **19/19** | `pytest tests/test_ocr_pipeline.py` |
| 10 | Kiểm thử | Truy hồi (gồm 2 test hồi quy mới) | **8/8** | `pytest tests/test_retrieval.py` |
| 11 | Kiểm thử | Hồi quy agent | **20/20** | `pytest tests/test_agent_regressions.py` |
| 12 | Kiểm thử | Tình huống người dùng thật | **15/15** | `pytest tests/test_real_user_edge_cases.py` |
| 13 | Kiểm thử | Trung thực nguồn live | **7/7** | `pytest tests/test_chat_experience.py` |
| 14 | Kiểm thử | Khoá URL nguồn theo mã thủ tục | **4/4** | `pytest tests/test_procedure_source_urls.py` |
| 15 | Chi phí | Token tiếng Việt | **2,17 ký tự/token** | `count_tokens` trên prompt planner thật |
| 16 | Chi phí | Chi phí LLM / hồ sơ | **~0,016 USD** | `docs/business-viability-pilot.md` §6 |
| 17 | Độ phủ | Thủ tục · rule khai báo | **5 thủ tục · 17 rule** | `data/procedures/`, `rules/` |
| 18 | Độ phủ | Endpoint API | **75** | `docs/API-Reference.md` §10 |

---

## 2. Thiết kế eval: ba bộ, ba mục đích

Tách bộ là điểm quan trọng nhất của phép đo này. Một con số gộp sẽ che mất cả điểm mạnh lẫn điểm yếu.

| Bộ | Nguồn câu hỏi | Trả lời câu hỏi gì |
|---|---|---|
| **A** — in-catalog (30 câu) | `example_queries` + `aliases` trong catalog | "Index có vỡ không?" |
| **B** — out-of-catalog (15 câu) | Diễn đạt tự nhiên, tự viết | "Độ phủ thật đến đâu?" |
| **C** — held-out (15 câu) | Viết **trước** khi tinh chỉnh, **không** dùng để tinh chỉnh | "Sửa xong có tổng quát hoá không, hay chỉ vá đúng bộ B?" |

**Bộ A có tính vòng tròn** — chính những chuỗi đó được đưa vào index, nên 100% là *điều kiện cần*, không chứng minh năng lực hiểu ngôn ngữ. Báo cáo riêng con số này sẽ là đánh lừa.

**Bộ C tồn tại vì bộ B không đủ.** Sau khi tinh chỉnh catalog theo các ca trượt của bộ B, bộ B đương nhiên tăng — đó là overfit. Chỉ bộ C mới nói được thật.

---

## 3. Kết quả

```
python scripts/eval_identify.py

BỘ A — in-catalog          30/30 = 100%    chốt nhầm 0/30
BỘ B — out-of-catalog      11/15 = 73,3%   chốt nhầm 0/15
BỘ C — held-out             9/15 = 60,0%   chốt nhầm 0/15
────────────────────────────────────────────────────────
TỔNG  nhận diện đúng 50/60  ·  chốt nhầm 0/60
```

**So với trước khi tinh chỉnh catalog:**

| | Trước | Sau |
|---|:---:|:---:|
| Bộ B | 9/15 (60,0%) | **11/15 (73,3%)** |
| Bộ C (held-out) | 7/15 (46,7%) | **9/15 (60,0%)** |
| Tổng đúng | 46/60 | **50/60** |
| **Chốt nhầm** | **1/60** | **0/60** |

Bộ C tăng 46,7% → 60% cho thấy việc bổ sung từ vựng **có tổng quát hoá**, không chỉ vá riêng bộ B.

---

## 4. Lỗi thật mà bộ held-out phát hiện

Đây là lý do bộ C đáng công viết ra.

Bộ B cho kết quả chốt nhầm 0/45 và tôi đã suýt ghi vào tài liệu rằng "hệ thống không bao giờ chốt nhầm". Bộ C bác bỏ ngay: câu `"sinh viên thuê phòng trọ có phải khai báo không"` bị **chốt hẳn** `khai_sinh`.

**Nguyên nhân:** `required_token_groups` của `khai_sinh` là `['khai','sinh']`, và cơ chế khớp là *túi từ, không xét liền kề*. Câu trên có "**khai** báo" và "**sinh** viên" → đủ hai token → 0.95 điểm.

Sửa xong ca đó thì bộ C lộ tiếp một ca thứ hai, tinh vi hơn: `"tụi mình định về chung một nhà, cần giấy tờ gì"` → chốt hẳn `can_cuoc` với điểm 0.80.

**Nguyên nhân — lỗi đặc thù tiếng Việt.** Alias `"chứng minh thư"` sau khi bỏ dấu (`fold_ascii`) và loại token chung còn đúng `{chung, minh}`. Câu hỏi trên chứa "về **chung** một nhà" và "tụi **mình**" — trùng khít cả hai token → `procedure_coverage = 1.0` → điểm `0.7 × 1.0 + 0.3 × 0.18 = 0.80`, vượt `identify_min_relevance = 0.6`.

Nói cách khác: **bỏ dấu làm "chứng minh" ≡ "chung mình"**. Bất kỳ alias nào rút gọn còn 2 token đều là bẫy tương tự.

**Cách sửa** (`src/services/retrieval/__init__.py`): cụm còn dưới 3 token sau khi fold **không được chấm fuzzy**. Cụm ngắn vẫn khớp chính xác ở nhánh substring phía trên nên không mất khả năng nhận diện — `test_short_alias_still_matches_when_written_out` khoá tính chất này.

Hai test hồi quy: `tests/test_retrieval.py::test_short_phrase_does_not_fuzzy_match_after_diacritic_folding` và `::test_short_alias_still_matches_when_written_out`. Đã xác minh test **fail trên code trước khi sửa** (điểm 0.8) và pass sau khi sửa.

**Đánh đổi đã chấp nhận:** bản sửa làm tổng số nhận đúng giảm từ 52 xuống 50, vì hai ca trước đây đúng nhờ chính cơ chế fuzzy 2-token vừa bị chặn. Đổi lại chốt nhầm về 0. Với hệ thống này đó là đánh đổi đúng.

---

## 4b. Lỗi thứ ba — do rà soát dữ liệu phát hiện, eval không bắt được

Sau khi sửa §4, một đợt rà toàn bộ cụm ngắn trong catalog (68 cụm ≤2 token) cho thấy **cơ chế khớp còn một lỗ hổng riêng biệt**: nhánh khớp chính xác dùng `substring` thuần, **không xét ranh giới từ**.

Hai ca, cả hai đều cho điểm **1.0 — tức chốt chắc chắn**:

| Câu hỏi | Bị chốt nhầm | Vì sao |
|---|---|---|
| "cho **nhỏ** nhà tôi mượn giấy tờ" | `tam_tru` | alias "ở nhờ" → `o nho`, nằm gọn giữa `cho nho` |
| "nộp hồ sơ vào **cuối** năm" | `ket_hon` | alias "cưới" → `cuoi`, trùng khít `cuối` |

Hai lỗi này **không nằm trong bộ B lẫn bộ C** — không câu eval nào chứa "cho nhỏ" hay "cuối năm". Chúng chỉ lộ ra khi rà dữ liệu một cách hệ thống. Đây là giới hạn của eval bằng mẫu: nó chỉ đo được cái nó có mẫu.

**Hai cách sửa cho hai bản chất khác nhau:**

1. **Ranh giới từ** (`_contains_phrase`, `src/services/retrieval/__init__.py:106`) — sửa được ca "ở nhờ"/"cho nhỏ", và bảo vệ cả các alias có sẵn từ trước chứ không riêng alias mới thêm.
2. **Gỡ alias "cưới"** — ranh giới từ **không cứu được** ca này, vì "cưới" và "cuối" là **đồng tự sau khi bỏ dấu**: cả hai đều fold thành `cuoi`. Đã thay bằng cụm dài hơn (`"đám cưới"`, `"muốn cưới"`, `"làm đám cưới"`) — những cụm này không có đồng tự vì "đám cuối"/"muốn cuối" không phải tiếng Việt.

Bài học rút ra cho catalog: **alias càng ngắn càng nguy hiểm**, và trong tiếng Việt mức nguy hiểm bị nhân lên vì bỏ dấu gộp nhiều từ khác nghĩa thành một chuỗi. Khi thêm alias mới, phải kiểm cả hai loại va chạm — lọt giữa từ khác, và đồng tự sau khi bỏ dấu.

Test hồi quy: `test_short_alias_does_not_match_inside_another_word`, `test_word_boundary_fix_keeps_genuine_matches`. Đã xác minh fail trên code trước khi sửa (điểm 1.0 với ngưỡng 0.6).

---

## 5. Khoảng trống còn lại

10 ca trượt còn lại (tất cả đều **lùi về hỏi lại**, không ca nào chốt sai):

| Nhóm trượt | Ví dụ | Bản chất |
|---|---|---|
| `khai_sinh` với cách nói vòng | "con mới đẻ cần làm thủ tục gì đầu tiên", "đăng ký tên cho con vào sổ hộ tịch" | Thiếu từ vựng "mới đẻ", "sổ hộ tịch" |
| `ket_hon` với cách nói ẩn dụ | "về chung một nhà", "ra giấy tờ chính thức" | Khó — không có từ khoá nào về hôn nhân |
| Câu quá mơ hồ | "cháu nhà tôi chưa có giấy tờ gì cả", "giấy tờ tùy thân bị mất hết rồi" | **Hỏi lại là hành vi đúng**, không nên tính là lỗi |

Nhóm thứ ba đáng chú ý: với những câu này, hỏi lại mới là hành vi mong muốn. Chỉ số "độ chính xác" đang **phạt oan** hệ thống ở đó. Bản eval sau nên tách riêng nhóm "mơ hồ chính đáng".

Quy luật chung của các ca trượt: hệ thống yếu ở **từ dân dã và từ cũ**, đúng cách nói của nhóm ít thành thạo văn bản hành chính — tức **đúng nhóm người dùng sản phẩm nhắm tới**. Đây là chi phí kiểu "kiểm duyệt dữ liệu" nêu ở `docs/business-viability-pilot.md` §6.3.

---

## 6. Giới hạn của phép đo

- **Bộ B và C mỗi bộ chỉ 15 câu, do tôi tự viết.** Không phải mẫu đại diện thống kê. Con số 73%/60% nên đọc là "có khoảng trống độ phủ rõ rệt", không phải giá trị chính xác.
- **Chưa có eval cho chất lượng câu trả lời của node `answer`** — guardrail yếu nhất (`docs/GUARDRAILS.md` lớp 4) mà lại chưa có phép đo nào. Đây là khoảng trống lớn nhất.
- **Chưa đo latency** trên môi trường thật.
- **Chưa đo tỉ lệ OCR rơi vào `needs_human_review`** trên ảnh thật.
- Chỉ số "độ chính xác" chưa tách nhóm câu mơ hồ chính đáng (§5).

---

## 7. Chỉ số vận hành cho pilot

Chưa có baseline vì cần người dùng thật — Giai đoạn 1 pilot phải đo (`docs/business-viability-pilot.md` §7-8).

| Chỉ số | Vì sao |
|---|---|
| **Tỷ lệ hồ sơ đạt ngay lần nộp đầu** | Chỉ số Bắc Đẩu |
| Số sai sót nội dung do cán bộ báo cáo | Tiêu chí loại — phải bằng 0 |
| Tỷ lệ trả lời "chưa đủ căn cứ" | Cao = catalog thiếu, không phải mô hình kém |
| Tỷ lệ hội thoại phải hỏi lại để chọn thủ tục | Đo khoảng trống ở §5 trên người thật |
| Tỷ lệ OCR → `needs_human_review` | Hiệu chỉnh ngưỡng 0,85 |
| Số lượt trung bình mỗi phiên | Kiểm chứng mô hình chi phí |

**Chỉ số cố tình không dùng:** số lượt chat, thời gian trên trang. Người dân dùng ít mà xong việc là kết quả tốt.

---

## 8. Việc nên làm tiếp

1. ~~Đưa `scripts/eval_identify.py` vào CI với ngưỡng chặn `chốt nhầm == 0`.~~ **Đã làm** — `.github/workflows/ci.yml`, xem §8b.
2. ~~Rà soát toàn bộ alias 2 token trong catalog.~~ **Đã làm** — kết quả ở §4b.
3. **Mở rộng bộ B/C lên 50–100 câu**, lấy từ câu hỏi thật ở Bộ phận Một cửa thay vì tự nghĩ.
4. **Tách nhóm "mơ hồ chính đáng"** khỏi chỉ số độ chính xác.
5. **Xây eval cho node `answer`** — chấm độ bám nguồn và độ đúng lúc của "chưa đủ căn cứ".
6. **Thêm kiểm tra tự động cho alias mới**: cảnh báo khi một alias fold xuống dưới 3 token hoặc trùng đồng tự với từ thông dụng (bài học §4b). Hiện việc này vẫn làm thủ công.
7. **Đo latency** trên môi trường thật.

---

## 8b. Cổng CI

`.github/workflows/ci.yml` chạy `python scripts/eval_identify.py` sau `pytest`. Script trả **exit code 1 khi có bất kỳ ca chốt nhầm nào**.

Chạy hoàn toàn offline — BM25 in-memory dựng thẳng từ catalog, không cần index Chroma hay LLM API key.

**Cổng chỉ chặn trên tỉ lệ chốt nhầm, không chặn trên độ chính xác.** Độ phủ phụ thuộc từ vựng catalog và sẽ lên xuống mỗi lần thêm/sửa thủ tục; đặt ngưỡng cứng ở đó chỉ tạo ra test giòn mà đội phải nới liên tục cho đến khi nó vô nghĩa. Ngược lại, chốt nhầm là lỗi đúng/sai rạch ròi và hậu quả rơi thẳng vào người dân.

Đã kiểm cả hai nhánh: thêm một alias sai lệch vào catalog → exit 1 kèm thông báo; gỡ ra → exit 0.

---

## 9. Tái lập

```bash
python scripts/eval_identify.py          # nhận diện thủ tục, 3 bộ
python -m pytest -q                      # toàn bộ suite
pytest tests/test_retrieval.py -q        # gồm 2 test hồi quy lỗi bỏ dấu
```

> **Về 1 test failing.** `test_application_migrations.py::test_application_migration_round_trip_preserves_baseline_data` fail local (`no such table: application_cases`) nhưng **CI xanh trên 5 lần chạy `main` gần nhất**. Artifact môi trường local. Ghi ra thay vì báo 330/330 cho đẹp.
