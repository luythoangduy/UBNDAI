# Cost Report — UBNDAI

> Chi phí LLM theo mức sử dụng: **mỗi lượt → mỗi hồ sơ → mỗi đơn vị/tháng**.
>
> Mọi con số suy ra từ tham số **đo thật**, công thức công khai để audit lại được. Đây là **ước tính**, không phải hoá đơn. Phần chưa đo được đánh dấu rõ thay vì điền số phỏng đoán.
>
> Tóm tắt cho pitch: `docs/business-viability-pilot.md` §6. Tài liệu này là bản chi tiết.

---

## 1. Tham số đầu vào

| Tham số | Giá trị | Nguồn |
|---|---|---|
| Model chat | `claude-haiku-4-5` | `src/config.py:38` |
| Giá input | **1,00 USD / 1M token** | Bảng giá Anthropic |
| Giá output | **5,00 USD / 1M token** | — |
| **Tỉ lệ token tiếng Việt** | **2,17 ký tự/token** | **[ĐO]** `count_tokens` trên chính prompt planner: 2.703 ký tự → 1.245 token |
| Prompt planner (tĩnh) | 2.594 ký tự | `src/agents/prompts/planner.py` |
| Prompt answer (tĩnh) | 562 ký tự | `src/agents/prompts/answer.py` |
| Ngữ cảnh answer | top-3 đoạn | `src/agents/nodes/answer.py` |
| Cache nguồn | TTL 3.600 s (120 s khi lỗi) | `src/config.py:17,21` |
| Cache OCR | 128 mục, theo hash ảnh | `src/config.py:67` |

> **Vì sao 2,17 là con số quan trọng nhất ở đây.** Tiếng Anh thường ~4 ký tự/token. Tiếng Việt tốn token **gần gấp đôi** trên cùng lượng chữ. Mọi mô hình chi phí quy chiếu từ số liệu tiếng Anh sẽ **thấp hơn thực tế khoảng 2 lần**. Đây là lý do tôi đo thay vì tra.

---

## 2. Điểm mấu chốt: hầu hết luồng **không gọi LLM**

Đây là yếu tố chi phối chi phí, hơn cả giá model.

| Node | Gọi LLM? | Cơ chế thay thế |
|---|:---:|---|
| `planner` | **Có điều kiện** | Rule-based intent chạy trước (`planner.py:155`) |
| `identify` | Không | BM25 + vector |
| `clarify` | Không | Câu hỏi khai báo trong catalog |
| `checklist` | Không | Catalog + rule engine |
| `answer` | **Có** | — |

Chỉ **2/5 node** chạm LLM, và `planner` chỉ chạm khi rule-based không phân loại được.

Tái lập: `grep -rn "ainvoke(" src/agents/ src/services/ --include="*.py"`

---

## 3. Chi phí mỗi lượt

| Lượt | Token vào | Token ra | Chi phí |
|---|---:|---:|---:|
| **Planner** (structured output) | 1.245 **[ĐO]** | ~80 | **~0,0017 USD** |
| **Answer** (prompt + 3 đoạn + lịch sử) | ~2.200 | ~280 | **~0,0036 USD** |
| **Identify / Clarify / Checklist** | — | — | **0,0000 USD** |

Công thức:

```
planner = 1.245 × 1/1e6  +  80 × 5/1e6  = 0,001245 + 0,000400 = 0,001645 USD
answer  = 2.200 × 1/1e6  + 280 × 5/1e6  = 0,002200 + 0,001400 = 0,003600 USD
```

Token vào của `planner` là **[ĐO]**. Token vào của `answer` là **[MÔ HÌNH]** — quy từ kích thước prompt tĩnh (562 ký tự) cộng top-3 đoạn cộng lịch sử, chia cho 2,17.

---

## 4. Chi phí mỗi hồ sơ

Giả định một phiên chuẩn bị hồ sơ = **8 lượt**, trong đó ~3 lượt chạm `planner` và ~3 lượt chạm `answer`; 2 lượt còn lại đi thẳng qua `identify`/`clarify`/`checklist` (miễn phí).

```
3 × 0,001645  (planner)  = 0,004935
3 × 0,003600  (answer)   = 0,010800
2 × 0          (rule)    = 0
                           ─────────
Tổng                     ≈ 0,0157 USD / hồ sơ    (~410 VNĐ @ 26.000 VNĐ/USD)
```

**Giả định chưa kiểm chứng:** số lượt mỗi phiên, tỉ lệ lượt chạm LLM, độ dài câu trả lời. Đây là ba biến duy nhất trong công thức chưa đo trên người dùng thật — Giai đoạn 1 pilot phải đo.

Nếu cả ba lệch gấp đôi so với giả định, chi phí vẫn chỉ ~0,03 USD/hồ sơ. **Kết luận không đổi ngay cả khi sai số lớn** — đó là điều đáng nói, chứ không phải con số chính xác.

---

## 5. Chi phí chưa định lượng được

| Khoản | Trạng thái |
|---|---|
| **OCR** (`gpt-5-mini`, `reasoning_effort=minimal`) | **[CẦN SỐ LIỆU THẬT]** — chưa xác minh bảng giá. Mỗi hồ sơ ~3–5 tài liệu. Có cache theo hash ảnh nên nộp lại cùng ảnh không tốn phí |
| **Hạ tầng** (Render + Vercel) | **[CẦN SỐ LIỆU THẬT]** — chi phí **cố định**, không theo hồ sơ |
| **Embedding** (BGE-M3) | Chạy local khi `LOCAL_EMBEDDING_OFFLINE=true` → 0 USD. Qua HuggingFace Inference → [CẦN SỐ LIỆU THẬT] |
| **Kiểm duyệt dữ liệu thủ tục** | **Khoản chi phối** — xem §7 |

---

## 6. Cơ chế giảm chi phí đã có sẵn

| Cơ chế | Vị trí | Tác dụng |
|---|---|---|
| Rule-based intent trước LLM | `planner.py:155` | Bỏ hẳn lượt planner cho ý định rõ ràng |
| Checklist không dùng LLM | `nodes/checklist.py` | Phần nặng nhất về nội dung tốn 0 đồng |
| Cache kết quả nguồn theo checksum | `config.py:17` | Cùng thủ tục, cùng nguồn → không gọi lại |
| Cache OCR theo hash ảnh | `config.py:67` | Nộp lại cùng ảnh → 0 đồng |
| `reasoning_effort=minimal` cho OCR | `config.py:65` | OCR là trích xuất, không cần suy luận sâu |
| Ngữ cảnh answer giới hạn top-3 | `nodes/answer.py` | Chặn phình token vào |

**Chưa dùng: prompt caching.** Prompt planner tĩnh ~1.200 token được gửi lại mỗi lượt. Bật cache-read sẽ giảm phần này khoảng 90%. Chưa làm vì ở mức chi phí hiện tại nó không đáng ưu tiên — ghi ra để không ai tưởng đã tối ưu hết.

---

## 7. Hệ quả chiến lược

Chi phí biến đổi ~410 VNĐ/hồ sơ nghĩa là:

1. **Chi phí không phải rào cản mở rộng.** Không cần tối ưu chi phí AI trong 12 tháng đầu.
2. **Miễn phí cho người dân là bền vững**, không phải trợ giá tạm thời.
3. **Nút thắt là kiểm duyệt dữ liệu thủ tục**, không phải hạ tầng — thứ cần chuyên môn pháp lý người thật và không tự động hoá được.
4. Vì vậy pilot đo **độ chính xác và niềm tin**, không đo chi phí.

Điểm 3 đã được chứng minh bằng sự cố thật: catalog từng chứa hai văn bản pháp luật không tồn tại, và cả 5 URL nguồn đã chết. Không lỗi nào trong đó liên quan tới chi phí model.

---

## 8. Cách đo chính xác hơn

Để thay [MÔ HÌNH] bằng [ĐO], cần ghi telemetry usage thật:

1. Ghi `usage.input_tokens` / `usage.output_tokens` từ mỗi phản hồi LLM vào log có cấu trúc.
2. Gắn `case_id` để cộng dồn theo hồ sơ.
3. Sau pilot Giai đoạn 1, thay toàn bộ §3–§4 bằng số thật.

Hiện chưa có telemetry này. Đây là hạng mục nên làm cùng lúc với pilot, vì nó cũng cho ra **số lượt trung bình mỗi phiên** — biến còn thiếu ở `docs/business-viability-pilot.md` §10.

---

## 9. Tái lập

```bash
# Tỉ lệ token tiếng Việt: gửi prompt planner tới /v1/messages/count_tokens
# với model claude-haiku-4-5 → 2.703 ký tự trả về 1.245 token.

wc -m src/agents/prompts/planner.py src/agents/prompts/answer.py
grep -rn "ainvoke(" src/agents/ src/services/ --include="*.py"
grep -n "llm_model\|ocr_llm_model\|cache_ttl\|ocr_cache_size" src/config.py
```
