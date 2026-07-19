# Guardrails — UBNDAI

> Liệt kê các cơ chế an toàn & tin cậy của hệ thống, kèm **vị trí code** và **bằng chứng kiểm thử**.
>
> Triết lý: **cưỡng chế bằng kiến trúc, không bằng lời dặn trong prompt.** Một guardrail chỉ tồn tại trong system prompt là một guardrail có thể bị mô hình bỏ qua. Ở đây, các ràng buộc quan trọng nhất được đưa xuống tầng kiểu dữ liệu và tầng schema — nơi vi phạm sẽ **ném exception**, không phải chỉ "hy vọng mô hình nghe lời".
>
> Bối cảnh rủi ro đặc thù: đây là hệ thống hướng dẫn **thủ tục hành chính**. Một câu trả lời sai không gây khó chịu — nó khiến người dân đi lại vô ích, hoặc tệ hơn, xây nhà không phép. Vì vậy nguyên tắc xuyên suốt là **thà nói "chưa đủ căn cứ" còn hơn đoán**.

## Tổng quan các lớp

| Lớp | Guardrail | Vị trí | Khi nào chạy | Cưỡng chế bằng |
|----|-----------|--------|--------------|----------------|
| 1 | AI không được phát `error` | `src/models/validation.py:28` | Lúc khởi tạo mọi `ValidationIssue` | **Kiểu dữ liệu** (Pydantic validator) |
| 2 | Checklist chỉ sinh từ catalog | `src/services/checklist.py`, `src/agents/nodes/checklist.py` | Trong graph, **không gọi LLM** | Kiến trúc (không có đường để LLM chèn mục) |
| 3 | Rule engine khai báo | `src/services/validation/rule_engine.py` | Sau khi có dữ liệu hồ sơ | Schema YAML validate lúc nạp |
| 4 | Trả lời thiếu nguồn → "chưa đủ căn cứ" | `src/agents/nodes/answer.py:3`, `src/agents/prompts/answer.py:9` | Trong node `answer` | Prompt + thiết kế ngữ cảnh |
| 5 | OCR độ tin cậy thấp → `needs_human_review` | `src/services/ocr/pipeline.py:9` | Sau OCR, trước khi điền form | Ngưỡng số (`OCR_CONFIDENCE_THRESHOLD`) |
| 6 | Trung thực về nguồn live | `src/services/chat_experience.py` | Mỗi lần dựng evidence | Trạng thái `ready`/`fallback` tách bạch |
| 7 | Khoá URL nguồn theo mã thủ tục | `tests/test_procedure_source_urls.py` | CI | Test tự động |

---

## Lớp 1 — AI không thể phát `error` (cưỡng chế ở tầng kiểu)

Đây là guardrail quan trọng nhất, và nó **không thể bị lách**.

`ValidationIssue` có `model_validator` chặn thẳng tổ hợp `source="ai"` + `severity="error"`:

```python
# src/models/validation.py:28
@model_validator(mode="after")
def _ai_cannot_error(self) -> "ValidationIssue":
    if self.source == "ai" and self.severity == "error":
        ...
```

Ý nghĩa: **chỉ rule engine khai báo mới được nói "hồ sơ này sai"**. AI chỉ được phép gợi ý (`warning`) hoặc cung cấp thông tin (`info`). Kể cả khi mô hình trả về `severity: "error"`, `ai_checker` cũng hạ cấp trước khi dựng object:

```python
# src/services/validation/ai_checker.py:83
severity=severity if severity in ("warning", "info") else "warning",
```

Hai lớp chồng nhau: `ai_checker` hạ cấp (lớp mềm), và nếu lớp mềm có bug thì Pydantic ném lỗi (lớp cứng).

**Vì sao thiết kế thế này.** Cán bộ tiếp nhận và người dân đối xử với `error` như phán quyết. Một mô hình ngôn ngữ không có thẩm quyền pháp lý để ra phán quyết về tính hợp lệ của hồ sơ. Ranh giới thẩm quyền đó được mã hoá vào kiểu dữ liệu.

**Bằng chứng:** `pytest tests/test_ai_checker.py` → **4/4 PASS** · `pytest tests/test_rule_engine.py` → **11/11 PASS**

---

## Lớp 2 — Checklist không do LLM sinh ra

Luồng hướng dẫn chính **không gọi LLM ở bước sinh checklist**. Node `identify` dùng truy hồi lai (BM25 + vector), node `checklist` sinh từ catalog + rule engine.

Mọi mục trong checklist truy ngược được về một `DocumentRequirement` trong `data/procedures/*.json`. Không có đường code nào cho phép mô hình thêm một mục giấy tờ mới.

Trong toàn bộ pipeline chỉ có **hai** điểm gọi LLM cho luồng công dân:

| Điểm gọi | Vị trí | Điều kiện |
|---|---|---|
| `planner` | `src/agents/nodes/planner.py:257` | Chỉ khi ý định là `general_question`/`unknown` (`planner.py:155`) |
| `answer` | `src/agents/nodes/answer.py:134` | Hỏi đáp mở |

Tái lập: `grep -rn "ainvoke(" src/agents/ src/services/ --include="*.py"`

**Hệ quả kép:** vừa là guardrail (mô hình không chạm được vào nội dung pháp lý), vừa là lợi thế chi phí (~0,016 USD/hồ sơ — xem `docs/business-viability-pilot.md` §6).

---

## Lớp 3 — Rule engine khai báo

Tầng **duy nhất** được sinh `severity=error`. Rule viết bằng YAML, không phải code:

```
rules/khai_sinh.yaml            4 rule
rules/tam_tru.yaml              4 rule
rules/can_cuoc.yaml             3 rule
rules/ket_hon.yaml              3 rule
rules/giay_phep_xay_dung.yaml   3 rule
                                ───────
Tổng                            17 rule
```

Schema được validate lúc nạp (`rule_engine.py:71`): thiếu `id`/`check`/`severity`/`message` → lỗi ngay; `severity` ngoài `error|warning|info` → lỗi ngay (`rule_engine.py:74`).

**Vì sao khai báo thay vì code.** Rule thủ tục hành chính thay đổi theo văn bản pháp quy. Dạng khai báo cho phép cán bộ chuyên môn đọc và ký duyệt rule mà không cần đọc Python — đây là điều kiện bắt buộc của quy trình kiểm duyệt trong pilot Giai đoạn 1.

**Bằng chứng:** `pytest tests/test_rule_engine.py` → **11/11 PASS** · `pytest tests/test_officer_rule_integration.py`

---

## Lớp 4 — Thiếu nguồn thì nói "chưa đủ căn cứ"

Node `answer` được chỉ thị rõ (`src/agents/prompts/answer.py:9`):

> *Nguồn không đủ để trả lời → nói rõ "chưa đủ căn cứ" và khuyên hỏi cán bộ tiếp nhận, không đoán.*

Đây là guardrail hành vi (prompt-level), nên nó **yếu hơn lớp 1–3**. Tài liệu này ghi nhận đúng mức độ đó thay vì phóng đại: nó dựa vào việc mô hình tuân thủ, và cần theo dõi bằng chỉ số vận hành.

Bù lại bằng thiết kế ngữ cảnh: node `answer` chỉ nhận top-3 đoạn đã truy hồi (`src/agents/nodes/answer.py`, lát cắt `[:3]`) — mô hình không có sẵn kiến thức nền về thủ tục để mà bịa, vì thủ tục hành chính Việt Nam thay đổi liên tục và không nằm trong tri thức huấn luyện một cách đáng tin.

**Chỉ số theo dõi:** tỷ lệ hội thoại kết thúc bằng "chưa đủ căn cứ". Chỉ số này **cao là dấu hiệu catalog thiếu**, không phải mô hình kém — xem `docs/business-viability-pilot.md` §8.

---

## Lớp 5 — OCR độ tin cậy thấp → chuyển người thật

`src/services/ocr/pipeline.py:9` — `needs_human_review=True` khi **bất kỳ** điều nào sau xảy ra:

1. Trường hoặc `doc_type` dưới ngưỡng `OCR_CONFIDENCE_THRESHOLD` (mặc định **0,85**, `src/config.py:58`)
2. Có vùng `[ILLEGIBLE]` trong kết quả
3. `ocr_confidence` tổng thể dưới ngưỡng

Thêm một lớp đối chiếu chéo: nếu **engine OCR** và **classifier** cho ra `doc_type` khác nhau trong khi classifier đang rất chắc chắn (`_CLASSIFIER_STRONG_CONFIDENCE`, `pipeline.py:85`) → đánh dấu `conflicting=True`. Hai nguồn độc lập bất đồng là tín hiệu cần người xem, không phải chọn bừa một bên.

**Nguyên tắc:** hệ thống **không im lặng điền form** bằng dữ liệu nó không chắc. Một trường điền sai trong đơn còn tệ hơn một trường để trống, vì trường trống thì người dân nhìn thấy, còn trường sai thì không.

**Bằng chứng:** `pytest tests/test_ocr_pipeline.py` → **19/19 PASS** · thêm `test_ocr_engine`, `test_ocr_classifier`, `test_ocr_form_filler`, `test_ocr_preprocessing`, `test_ocr_pdf`, `test_ocr_checklist`

---

## Lớp 6 — Trung thực về nguồn live

Khi dựng khối "Đã kiểm chứng nguồn", hệ thống phân biệt rạch ròi hai trạng thái (`src/services/chat_experience.py`):

| Trạng thái | Khi nào | Hiển thị |
|---|---|---|
| `ready` | Kéo được trang gốc **và** bóc được ≥1 tệp biểu mẫu | "Đã kiểm tra trang gốc · N tệp biểu mẫu" |
| `fallback` | Không kéo được, **hoặc** HTTP 200 nhưng không bóc được tệp nào | "Trang gốc không đọc được biểu mẫu; dùng snapshot đã kiểm duyệt" |

Điểm tinh tế đã được sửa: **HTTP 200 không đồng nghĩa với đọc được**. Cổng DVC nay render phía client, nên fetch trả 200 với trang rỗng. Gắn dấu ✓ "đã kiểm tra" cho thứ chưa thực sự đọc được là nói dối người dùng, dù về mặt kỹ thuật request đã thành công.

Kèm cơ chế tự hồi phục: khi kéo nguồn thất bại, kết quả suy giảm được cache bằng TTL ngắn **120 s** thay vì 3.600 s (`src/config.py:21`) — một cú 503 thoáng qua không bị "đóng băng" nguyên tiếng đồng hồ.

**Bằng chứng:** `pytest tests/test_chat_experience.py` → **7/7 PASS**

---

## Lớp 7 — Khoá URL nguồn bằng test

`tests/test_procedure_source_urls.py` (**4/4 PASS**) chặn ba loại lỗi:

1. Không thủ tục nào được trỏ vào host đã ngừng phục vụ (`thutuc.dichvucong.gov.vn` — 503 toàn subdomain).
2. Mọi `source_url` phải thuộc danh sách host chính thức (`is_official_url`).
3. **URL phải tra đúng mã thủ tục của chính thủ tục đó** — bắt lỗi copy nhầm URL giữa các file.

Điểm 3 quan trọng hơn vẻ ngoài: *trích dẫn nguồn mà mở ra thủ tục khác thì tệ hơn không trích dẫn*, vì nó tạo cảm giác đã kiểm chứng trong khi chưa.

---

## Sự cố thật đã xảy ra và bài học

Ghi lại vì nó định hình toàn bộ thiết kế trên, và vì giấu đi thì tài liệu này thành quảng cáo.

**Sự cố 1 — Căn cứ pháp lý bịa.** Catalog `giay_phep_xay_dung` từng chứa *"Luật Xây dựng số 135/2025/QH15"* và *"Nghị định 217/2026/NĐ-CP"* — **cả hai không tồn tại** — kèm ghi chú sai rằng nhà ở riêng lẻ được miễn giấy phép từ 01/7/2026. Nếu đến tay người dân, hậu quả là xây dựng không phép.

**Sự cố 2 — Toàn bộ 5 URL nguồn đã chết.** `thutuc.dichvucong.gov.vn` ngừng phục vụ; `dichvucong.gov.vn` dựng lại thành SPA không đọc tham số `ma_thu_tuc`, nên link cũ trả 200 rồi hiện trang trống. Tính năng "kéo nguồn trực tiếp" chưa từng hoạt động thật cho tới khi chuyển sang `vpcp.dichvucong.gov.vn`.

**Bài học chung:** rủi ro lớn nhất của hệ thống này **không nằm ở tầng mô hình**. Mô hình bị khoá chặt bởi lớp 1–3. Rủi ro nằm ở **dữ liệu thủ tục sai hoặc hết hiệu lực** — thứ mà không guardrail kỹ thuật nào bắt được, vì dữ liệu sai trông giống hệt dữ liệu đúng.

Hệ quả tới quy trình, không phải tới code:
- Giai đoạn 1 pilot **bắt buộc** cán bộ chuyên môn ký duyệt catalog trước khi bật cho người dân.
- Tiêu chí **0 sai sót về căn cứ pháp lý** là điều kiện dừng pilot, không phải chỉ tiêu phấn đấu.
- Lớp 7 tồn tại chính vì sự cố 2.

---

## Bảo mật & dữ liệu cá nhân

| Cơ chế | Vị trí |
|---|---|
| Xác thực OIDC + yêu cầu MFA claim | `src/services/oidc.py`, `src/config.py:79-83` |
| Phân quyền theo vai trò (công dân / cán bộ) | `src/services/auth.py` |
| Lưu tệp tải lên ở vùng riêng | `storage_root=./uploads/private` (`src/config.py:78`) |
| Giới hạn tải lên | 10 tệp · 10 MB/tệp (`src/config.py:84-85`) |
| Không lộ chi tiết lỗi nội bộ ra client | `src/main.py` — handler trả thông điệp chung, log đầy đủ phía server |

**Bằng chứng:** `pytest tests/test_oidc.py` → **2/2 PASS**

---

## Tổng hợp bằng chứng kiểm thử

```
python -m pytest -q
→ 329 passed, 1 failed
```

Chi tiết theo nhóm guardrail:

| Nhóm | Test | Kết quả |
|---|---|:---:|
| Rule engine (tầng duy nhất phát `error`) | `test_rule_engine.py` | 11/11 |
| AI checker (chỉ warning/info) | `test_ai_checker.py` | 4/4 |
| OCR pipeline (ngưỡng tin cậy) | `test_ocr_pipeline.py` | 19/19 |
| Trung thực nguồn live | `test_chat_experience.py` | 7/7 |
| Khoá URL nguồn | `test_procedure_source_urls.py` | 4/4 |
| Tình huống người dùng thật | `test_real_user_edge_cases.py` | 15/15 |
| Hồi quy agent | `test_agent_regressions.py` | 20/20 |
| OIDC | `test_oidc.py` | 2/2 |

> **Về 1 test failing.** `test_application_migrations.py::test_application_migration_round_trip_preserves_baseline_data` fail trên máy local nhưng **CI xanh trên cả 5 lần chạy `main` gần nhất** (kiểm bằng `gh run list`). Đây là artifact môi trường local, không phải lỗi sản phẩm. Ghi ra đây thay vì báo "330/330 PASS" cho đẹp.
