# Agent Features — UBNDAI

> Mô tả kiến trúc agent: đồ thị LangGraph, vai trò từng node, cơ chế định tuyến, và **những chỗ cố tình KHÔNG dùng LLM**.
>
> Luận điểm trung tâm: đây không phải "chatbot bọc RAG". Nó là **máy trạng thái có LLM ở hai vị trí hẹp**. Phần lớn công việc — nhận diện thủ tục, sinh checklist, kiểm tra hợp lệ — chạy bằng truy hồi và rule khai báo. Đó là lựa chọn thiết kế, không phải thiếu sót.

---

## 1. Đồ thị LangGraph

Định nghĩa: `src/agents/graph.py`

```
                    ┌─────────┐
      (entry) ─────▶│ planner │  ← 1 LLM call (structured output), có điều kiện
                    └────┬────┘
                         │ add_conditional_edges (graph.py:34)
       ┌─────────┬───────┼────────┬──────────┐
       ▼         ▼       ▼        ▼          ▼
  ┌────────┐ ┌────────┐ ┌─────────┐ ┌──────┐ (fallback)
  │clarify │ │identify│ │checklist│ │answer│
  └───┬────┘ └───┬────┘ └────┬────┘ └──┬───┘
      │          │           │         │
      │          └───────────┴─────────┤ add_conditional_edges (graph.py:45)
      │                                │ {"answer": answer, "end": END}
      ▼                                ▼
     END                              END
```

| Node | File | Gọi LLM? | Nhiệm vụ |
|---|---|:---:|---|
| `planner` | `nodes/planner.py` | **Có điều kiện** | Phân loại ý định, viết lại truy vấn, chọn nhánh |
| `clarify` | `nodes/clarify.py` | Không | Hỏi làm rõ theo `clarifying_questions` của thủ tục |
| `identify` | `nodes/identify.py` | Không | Nhận diện thủ tục bằng truy hồi lai |
| `checklist` | `nodes/checklist.py` | Không | Sinh checklist từ catalog + rule engine |
| `answer` | `nodes/answer.py` | **Có** | Hỏi đáp mở trên ngữ cảnh đã truy hồi |

Chỉ **2/5 node** chạm tới LLM. Tái lập: `grep -rn "ainvoke(" src/agents/`

---

## 2. State

`GuidanceState` (`src/agents/state.py:13`) — `TypedDict, total=False`, tích luỹ qua các lượt:

| Nhóm | Trường | Ghi chú |
|---|---|---|
| Hội thoại | `messages` (`add_messages`), `case_id` | Reducer của LangGraph gộp message |
| Kết quả planner | `route`, `rewritten_query`, `primary_intent`, `detected_intents` | 1 LLM call structured |
| Nhận diện | `candidate_procedures`, `selected_procedure_id`, `identify_confidence` | Kèm điểm số để audit |
| Làm rõ | `answers`, `pending_questions`, `pending_question_keys` | `answers` ghi ngược về `Case.answers` |
| Chuyển hướng | `pending_action`, `pending_procedure_ids`, `pending_switch_query`, `reset_procedure` | Xử lý khi người dân đổi ý giữa chừng |
| Truy hồi | `retrieved_chunks`, `citations` | `citations` là cơ sở của khối "Đã kiểm chứng nguồn" |
| Đầu ra | `checklist`, `reply`, `reply_kind` | `reply_kind` để frontend render đúng dạng |

**Điểm đáng chú ý:** `identify_confidence` được giữ trong state chứ không bị vứt sau khi dùng. Nhờ đó hệ thống có thể **thừa nhận nó không chắc** thay vì luôn tỏ ra tự tin — xem §4.

---

## 3. Planner — định tuyến hai tầng

`nodes/planner.py`. Điểm thiết kế quan trọng nhất nằm ở dòng 155:

```python
if detection.primary not in {"general_question", "unknown"} or not llm_is_configured():
```

Nghĩa là: **rule-based intent detection chạy trước**. LLM chỉ được gọi khi bộ luật không phân loại được (`general_question`/`unknown`).

| Tầng | Cơ chế | Chi phí | Khi nào |
|---|---|---|---|
| 1 | `src/services/intent.py` — khớp mẫu | $0 | Luôn chạy trước |
| 2 | LLM structured output → `PlannerDecision` (`planner.py:256`) | ~0,0017 USD | Chỉ khi tầng 1 không chắc |

Khi LLM được gọi, nó dùng `with_structured_output(PlannerDecision)` — đầu ra bị ràng buộc theo schema, không phải văn bản tự do cần parse.

**Fallback:** không cấu hình LLM → hệ thống **vẫn chạy** bằng tầng 1 (`planner.py:239`). Đây là tính chất quan trọng cho demo và cho môi trường cơ quan nhà nước có thể chặn API ngoài.

**Bằng chứng:** `pytest tests/test_intent_routing.py`, `tests/test_agent_regressions.py` → **20/20 PASS**

---

## 4. Identify — truy hồi lai, có ngưỡng thừa nhận không chắc

`nodes/identify.py` + `src/services/retrieval/`. **Không gọi LLM.**

Kết hợp hai tín hiệu:
- **BM25** (`retrieval/bm25.py`) — khớp từ khoá, mạnh với tên thủ tục chính thức
- **Vector** (`retrieval/chroma_client.py` + `embeddings.py`, mặc định BGE-M3) — khớp ngữ nghĩa, mạnh với cách người dân diễn đạt

Catalog còn hỗ trợ nhận diện bằng các trường khai báo trong `data/procedures/*.json`:

| Trường | Tác dụng |
|---|---|
| `aliases` | Cách gọi dân dã ("xin phép xây nhà") |
| `example_queries` | Câu hỏi mẫu thực tế |
| `negative_keywords` | **Chống nhận nhầm** — ví dụ `giay_phep_xay_dung` loại trừ "đăng ký khai sinh" |
| `required_token_groups` | Bắt buộc có đủ nhóm token mới tính là khớp |

Ba ngưỡng kiểm soát (`src/config.py:53-55`):

```python
identify_confidence_threshold: float = 0.55   # dưới ngưỡng → không chốt thủ tục
identify_min_relevance: float = 0.6           # ứng viên yếu bị loại
identify_min_margin: float = 0.15             # hai ứng viên sát nhau → hỏi lại
```

`identify_min_margin` là cơ chế đáng giá nhất: khi hai thủ tục có điểm gần bằng nhau, hệ thống **hỏi lại người dân** thay vì chọn cái nhỉnh hơn. Chọn nhầm thủ tục kéo theo sai toàn bộ checklist phía sau.

---

## 5. Clarify — hỏi theo khai báo, không hỏi tuỳ hứng

`nodes/clarify.py` + `src/services/clarification.py`. **Không gọi LLM.**

Câu hỏi lấy từ `clarifying_questions` trong catalog. Ví dụ `giay_phep_xay_dung`:

```json
{"key": "cong_trinh_yeu_cau_pccc",
 "text": "Công trình có thuộc diện phải thẩm duyệt thiết kế phòng cháy chữa cháy không?",
 "answer_type": "boolean"}
```

Câu trả lời tích luỹ vào `answers`, rồi được `condition` của `DocumentRequirement` tiêu thụ:

```json
{"code": "giay_chung_nhan_tham_duyet_pccc",
 "condition": "answers.cong_trinh_yeu_cau_pccc == true"}
```

Đây là cơ chế tạo ra giá trị cốt lõi của sản phẩm: **checklist theo tình huống, không phải danh sách đầy đủ mọi trường hợp**. Cổng DVC liệt kê tất cả; UBNDAI chỉ liệt kê những gì áp dụng cho người đang hỏi.

Vì câu hỏi là khai báo, cán bộ chuyên môn đọc và duyệt được — điều kiện bắt buộc của pilot Giai đoạn 1.

---

## 6. Checklist — sinh từ catalog, không sinh từ mô hình

`nodes/checklist.py` + `src/services/checklist.py`. **Không gọi LLM.**

Mỗi mục truy ngược về một `DocumentRequirement`. Không tồn tại đường code cho phép mô hình thêm mục mới. Xem `docs/GUARDRAILS.md` lớp 2.

Kết hợp với rule engine (`src/services/validation/rule_engine.py`) — 17 rule khai báo trên 5 thủ tục — để sinh cảnh báo. Chỉ tầng này được phát `severity=error`.

---

## 7. Answer — nơi duy nhất mô hình được viết tự do

`nodes/answer.py:134`. Ngữ cảnh bị giới hạn ở **top-3 đoạn** đã truy hồi.

Ràng buộc hành vi (`prompts/answer.py:9`): thiếu nguồn → nói "chưa đủ căn cứ", không đoán.

Đây là guardrail yếu nhất trong hệ thống vì nó ở tầng prompt. `docs/GUARDRAILS.md` lớp 4 ghi nhận đúng mức độ đó thay vì phóng đại.

---

## 8. Năng lực ngoài đồ thị chính

| Năng lực | Vị trí | LLM |
|---|---|:---:|
| OCR + phân loại giấy tờ | `src/services/ocr/` | `gpt-5-mini` (vision), `reasoning_effort=minimal` |
| Sinh bản nháp kết quả (DOCX/HTML) | `src/services/drafts/` | Không — render từ template |
| Chỉnh sửa bản nháp theo yêu cầu | `src/services/drafts/reviser.py` | Có, khi người dùng yêu cầu |
| Kiểm tra hồ sơ bằng AI | `src/services/validation/ai_checker.py` | Có — **chỉ warning/info** |
| Phát hiện bất thường (cổng cán bộ) | `src/services/ops/anomaly.py` | Không |
| Tóm tắt hồ sơ cho cán bộ | `src/services/ops/summarizer.py` | Có |
| Phân công hồ sơ | `src/services/ops/assignment.py` | Không |
| Chuẩn hoá nguồn khi nạp catalog | `src/services/sources/normalizer.py` | Có — pipeline offline, không tính vào chi phí mỗi hồ sơ |

OCR dùng **provider và key tách riêng** với chatbot (`ocr_llm_provider`, `ocr_llm_api_key` — `src/config.py:60-61`), để đổi một bên không ảnh hưởng bên kia.

Kết quả OCR được cache theo hash ảnh (`ocr_cache_size=128`) — tải lại cùng ảnh không tốn API call.

---

## 9. Vì sao kiến trúc này phù hợp bài toán

| Yêu cầu của lĩnh vực | Cách kiến trúc đáp ứng |
|---|---|
| Câu trả lời phải truy vết được về văn bản chính thức | Nội dung pháp lý đi qua catalog + rule, không qua mô hình |
| Cán bộ phải duyệt được logic | Rule và câu hỏi ở dạng YAML/JSON khai báo, đọc được không cần biết code |
| Không được ra phán quyết sai thẩm quyền | `ValidationIssue` chặn ở tầng kiểu — AI không thể phát `error` |
| Phải chạy được khi không có API ngoài | Rule-based intent + BM25 fallback; `planner.py:239` |
| Chi phí phải đủ thấp để miễn phí cho người dân | Chỉ 2/5 node gọi LLM → ~0,016 USD/hồ sơ |
| Thủ tục thay đổi theo văn bản pháp quy | Thêm/sửa thủ tục = sửa JSON + YAML, không sửa code |

---

## 10. Giới hạn hiện tại

Ghi ra để không ai đọc tài liệu này rồi tưởng hệ thống làm được nhiều hơn thực tế.

- **5 thủ tục.** Khai sinh, kết hôn, tạm trú, căn cước, giấy phép xây dựng. Chưa có cơ chế tự động nạp thủ tục mới từ Cổng DVC ở quy mô lớn.
- **`answer` là điểm yếu nhất về grounding** — guardrail tầng prompt, cần theo dõi bằng chỉ số vận hành.
- **Chưa có đánh giá tự động chất lượng truy hồi** (retrieval accuracy trên eval set chuẩn). Đây là hạng mục nên bổ sung — xem `docs/EVAL-METRICS.md`.
- **Chưa đo latency trên môi trường thật.** Các con số chi phí ở `docs/business-viability-pilot.md` §6 là [MÔ HÌNH] từ token đo thật, nhưng số lượt mỗi phiên chưa kiểm chứng trên người dùng thật.
