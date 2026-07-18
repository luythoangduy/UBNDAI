# Kiến trúc — TTHC Assist

## 1. Tổng quan luồng

### 1.1 Luồng người dân (guidance → nộp)

```
Người dân chat mô tả nhu cầu
  → LangGraph agent: làm rõ (clarify) ⇄ nhận diện thủ tục (retrieval trên catalog TTHC)
  → Sinh checklist cá nhân hoá (từ DocumentRequirement + điều kiện áp dụng)
  → Người dân upload ảnh giấy tờ → OCR: phân loại giấy tờ + trích trường + autofill form
  → Validation: rule engine (YAML theo thủ tục) + AI cross-check mâu thuẫn
  → readiness_score đạt ngưỡng → handoff sang cổng dịch vụ công (API)
```

### 1.2 Luồng cán bộ (ops)

```
Hồ sơ mới → auto-assignment (theo lĩnh vực + tải hiện tại)
  → Dashboard: danh sách theo ưu tiên, tóm tắt hồ sơ (LLM), hàng chờ "AI chưa chắc chắn"
  → Cuối ngày: daily digest (LLM tổng hợp)
  → Metrics pipeline: tỷ lệ hồ sơ lỗi, tỷ lệ trễ hạn theo thời gian
  → Anomaly detection (rolling z-score / so xu hướng ngày thường) → AnomalyAlert
```

## 2. Ranh giới module (bắt buộc — giống C2-App-108 §7)

- `src/agents/` — LangGraph state, nodes, edges, tools, prompts. Chỉ orchestration LLM.
- `src/api/` — route handler mỏng. Không business logic.
- `src/services/` — business logic. Chia 4 nhánh theo owner: `retrieval/` (A), `ocr/` (B), `validation/` (B), `ops/` (C). Ngoài ra `cases.py`, `db.py`, `auth.py` dùng chung (C dựng, mọi người dùng).
- `src/models/` — Pydantic schemas duy nhất. **Không duplicate schema ở bất kỳ đâu khác.** Đây là contract giữa 3 workstream — đổi model phải được cả team review (xem `planning/TEAM_PLAN.md`).

## 3. Data model chính

| Model | File | Vai trò |
|-------|------|---------|
| `Procedure`, `DocumentRequirement`, `FormTemplate`, `FormField` | `models/procedures.py` | Catalog thủ tục — nguồn sự thật cho checklist & autofill mapping |
| `Case`, `ChecklistItem`, `CaseStatus` | `models/cases.py` | Hồ sơ của một người dân — trạng thái trung tâm cả 3 workstream đọc/ghi |
| `ExtractedDocument`, `ExtractedField` | `models/documents.py` | Kết quả OCR một giấy tờ |
| `ValidationIssue`, `ValidationReport` | `models/validation.py` | Kết quả kiểm tra hồ sơ |
| `Assignment`, `CaseSummary`, `DailyDigest`, `MetricPoint`, `AnomalyAlert` | `models/ops.py` | Vận hành nội bộ |

Điểm ghép nối quan trọng:
- `FormField.ocr_sources` khai báo giấy tờ nào điền được trường nào → Dev B autofill không cần hỏi Dev A.
- `ChecklistItem.requirement_code` trỏ về `DocumentRequirement.code` → checklist (A) và validation (B) nói cùng một ngôn ngữ.
- `Case.readiness_score` do `ValidationReport` tính, agent (A) và dashboard (C) chỉ đọc.

## 4. Thiết kế LangGraph (Dev A)

State: `GuidanceState` (`src/agents/state.py`) — typed, explicit.

```
ingest → planner (1 LLM call structured: intent + rewrite + route)
  ├─ clarify        # thiếu thông tin → sinh câu hỏi làm rõ, chờ lượt sau
  ├─ identify       # ưu tiên workflow/raw source; không khớp thì handoff sang open legal RAG
  ├─ checklist      # áp điều kiện (answers) vào DocumentRequirement → checklist cá nhân hoá
  └─ answer         # trả lời hỏi đáp chung, kèm citation về thủ tục/căn cứ pháp lý
```

Bài học mang từ C2 sang: planner LLM-first với rule-based fallback; cần few-shot cho routing câu hỏi follow-up; decompose query trước khi RRF.

Catalog không phải allow-list hỗ trợ. Nó chỉ chứa workflow đã duyệt để bật checklist,
form/OCR và validation. Câu hỏi về thủ tục chưa có catalog vẫn đi qua corpus VBPL và
tìm nguồn Chính phủ; thiếu nguồn thì trả cảnh báo grounding thay vì đoán.

## 5. Bản đồ tái sử dụng từ C2-App-108

| Cần gì | Lấy từ C2-App-108 | Ghi chú |
|--------|-------------------|---------|
| Hybrid retrieval (dense + BM25 + RRF) | `src/services/{chroma_client,bm25_retrieval,retrieval_common,retrieval,embeddings,reranker}.py` | Port gần nguyên vẹn vào `services/retrieval/`; đổi collection sang catalog TTHC |
| Query pipeline | `src/services/{query_normalizer,query_expansion,intent_detector}.py` | Giữ pattern, viết lại few-shot cho domain TTHC |
| LangGraph skeleton | `src/agents/{state,graph}.py`, `nodes/`, `tools/` | Copy pattern, thay nội dung node |
| Auth JWT + refresh token | `src/services/{auth,security,permissions}.py`, `src/models/auth.py`, alembic | Port nguyên vẹn, thêm role `citizen/officer/manager` |
| DB/session/pagination | `src/services/{db,pagination}.py` | Port nguyên vẹn |
| API scaffold, error handling | `src/api/{errors,dependencies,router,health}.py` | Port nguyên vẹn |
| Upload + storage | `src/services/upload_storage.py`, `src/api/uploads.py` | Port, nối vào OCR pipeline |
| Index script | `scripts/index_legal_corpus.py`, `scripts/build_bm25.py` | Sửa thành `index_procedures.py` |
| Frontend Vite setup | `frontend/` (vite.config, tsconfig, cấu trúc src) | Copy config, UI viết mới |

**Viết mới hoàn toàn:** `services/ocr/`, `services/validation/`, `services/ops/`, `rules/`, `data/procedures/`, dashboard frontend.

## 6. OCR (Dev B)

- `OcrEngine` protocol trong `services/ocr/engine.py`; engine chính là **`VisionLlmEngine`**
  (chọn qua `OCR_ENGINE=vision_llm`) — vision LLM đọc cả chữ in lẫn chữ viết tay tiếng Việt,
  trả structured JSON được API đảm bảo đúng schema (`OCR_OUTPUT_SCHEMA`). Provider/model/key
  cấu hình qua bộ env `OCR_LLM_*` (openai `gpt-5-mini` mặc định | anthropic | gemini),
  **tách riêng hoàn toàn với LLM chatbot (`LLM_*`)**. `PaddleOcrEngine`/`GoogleVisionEngine`
  là adapter dự phòng.
- Tiền xử lý (`preprocessing.py`): EXIF → downscale → warp chính diện (perspective) →
  deskew → CLAHE; mọi bước fail đều fallback ảnh gốc, không bao giờ chặn OCR.
- Prompt chuẩn chuyên gia VBHC (`agents/prompts/ocr.py`): trích nguyên văn, không suy đoán
  chữ mờ (`[ILLEGIBLE]`/`[UNCERTAIN: ...]`), tách bút phê viết tay riêng (vị trí + tối đa
  3 phương án kèm %), trường chuẩn văn bản hành chính, `bbox` tương đối 0–1 cho UI highlight.
- Pipeline (`pipeline.py`): ảnh → tiền xử lý → engine (có cache theo hash ảnh —
  `OCR_CACHE_SIZE`) → cross-check doc_type giữa engine hint và keyword `classifier.py` →
  `ExtractedDocument`. Tối ưu tốc độ/chi phí qua `OCR_LLM_REASONING_EFFORT=minimal`.
- `needs_human_review=True` khi: trường/doc_type dưới `OCR_CONFIDENCE_THRESHOLD`, doc_type
  xung đột giữa 2 nguồn, có vùng `[ILLEGIBLE]`, hoặc ocr_confidence tổng thể thấp →
  hiện UI cho người dân sửa, và vào hàng chờ cán bộ xác nhận.
- Autofill (`form_filler.py`): map `ExtractedField.key` → `FormField` qua `ocr_sources`,
  không hardcode theo thủ tục; bỏ qua trường dưới ngưỡng confidence trừ khi người dân đã
  sửa tay (`edited_by_user`); không ghi đè giá trị người dân đã nhập.

## 7. Validation (Dev B)

Hai tầng, chạy tuần tự:

1. **Rule engine** (`services/validation/rule_engine.py`): load `rules/<thủ_tục>.yaml`, ngôn ngữ luật khai báo nhỏ (exists / match / days_since / cross-field). Deterministic, giải thích được, cán bộ sửa YAML không cần deploy code. Đây là tầng quyết định `severity=error`.
2. **AI checker** (`services/validation/ai_checker.py`): LLM soát mâu thuẫn ngữ nghĩa giữa các giấy tờ (tên viết khác dấu, địa chỉ không nhất quán…). Chỉ được sinh `warning`/`info` — không bao giờ tự sinh `error` (nguyên tắc: logic deterministic không giấu trong prompt).

`ValidationReport.readiness_score` = hàm deterministic trên issues + checklist (không phải LLM chấm điểm).

## 8. Ops & anomaly detection (Dev C)

- Assignment: round-robin có trọng số theo lĩnh vực phụ trách + tải hiện tại. Hồ sơ AI không chắc chắn (confidence thấp, issue `uncertain`) được ưu tiên gắn cờ.
- Tóm tắt hồ sơ / daily digest: LLM đọc `Case` + `ValidationReport` structured — chỉ tóm tắt, không quyết định.
- Metrics: job định kỳ ghi `MetricPoint` (error_rate, late_rate, volume) theo giờ/ngày vào DB.
- Anomaly: baseline rolling mean/std theo cùng-giờ-trong-tuần, cảnh báo khi z-score vượt ngưỡng. Đủ tốt cho MVP, nâng cấp STL/Prophet sau nếu cần.

## 9. Tích hợp cổng dịch vụ công

Toàn bộ năng lực expose qua REST API (`/api/v1/...`) + widget chat nhúng được. Handoff: `POST /api/v1/cases/{id}/submit` đóng gói hồ sơ theo schema cổng DVC (adapter riêng trong `services/portal_gateway.py` — stub ở MVP, mock cổng).
