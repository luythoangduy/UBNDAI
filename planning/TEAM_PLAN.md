# Kế hoạch team 3 người — TTHC Assist

Nguyên tắc chia việc: **mỗi người sở hữu một nhánh dọc** (backend service + API + phần UI của mình), giao tiếp qua contract trong `src/models/` — không chờ nhau, không giẫm file nhau.

## 1. Phân công & sở hữu thư mục

### Dev A — Guidance & RAG (năng lực 1)
- **Sở hữu:** `src/agents/**`, `src/services/retrieval/**`, `src/api/v1/chat.py`, `data/procedures/**`, `scripts/index_procedures.py`
- **Phạm vi:**
  - Định nghĩa schema catalog thủ tục + nhập 3–5 thủ tục mẫu (khai sinh, kết hôn, CCCD, tạm trú…)
  - Port hybrid retrieval từ C2-App-108 (chroma + BM25 + RRF), index catalog
  - LangGraph: planner → clarify ⇄ identify → checklist → answer (kèm citation)
  - Sinh checklist cá nhân hoá từ `DocumentRequirement` + câu trả lời làm rõ

### Dev B — Documents: OCR & Validation (năng lực 2 + 3)
- **Sở hữu:** `src/services/ocr/**`, `src/services/validation/**`, `rules/**`, `src/api/v1/documents.py`, `src/api/v1/validation.py`
- **Phạm vi:**
  - OcrEngine adapter (PaddleOCR local trước, Google Vision sau), phân loại loại giấy tờ VN (CCCD, giấy chứng sinh, sổ hộ khẩu/CT07, giấy đăng ký kết hôn…)
  - Trích trường + confidence → `ExtractedDocument`; autofill form qua `FormField.ocr_sources`
  - Rule engine YAML + AI cross-check; `ValidationReport` + `readiness_score` deterministic
  - Viết bộ rule cho các thủ tục mẫu của Dev A

### Dev C — Platform, Ops & Frontend (năng lực 4 + nền tảng)
- **Sở hữu:** `src/main.py`, `src/config.py`, `src/api/` (scaffold, auth, cases), `src/services/{db,auth,cases,ops/**}.py`, `alembic/`, `frontend/**`, `.github/**`, Docker
- **Phạm vi:**
  - Sprint 0: dựng skeleton chạy được (FastAPI + DB + auth port từ C2 + CI) để A/B cắm vào
  - Case lifecycle (CRUD, status machine, submit/handoff mock cổng DVC)
  - Ops: auto-assignment, tóm tắt hồ sơ + daily digest (LLM), metrics pipeline, anomaly detection (rolling z-score)
  - Frontend: widget chat người dân (nối API của A/B) + dashboard cán bộ

## 2. Sprint plan (4 sprint × 1 tuần — co giãn theo deadline thực tế)

### Sprint 0 (2–3 ngày đầu) — Contract freeze ⚠️ quan trọng nhất
- **Cả team:** review và chốt toàn bộ `src/models/` (đã có bản nháp trong repo) + route signature trong `src/api/v1/`. Sau khi chốt, đổi model phải qua PR cả 3 approve.
- **C:** skeleton chạy được: `uvicorn` lên, `/health` ok, DB + migration + auth hoạt động, CI xanh.
- **A:** copy stack retrieval từ C2 sang, chốt schema `data/procedures/`.
- **B:** chạy thử PaddleOCR trên ảnh CCCD thật, chốt danh sách doc_type MVP.

### Sprint 1 — Đường xương sống từng nhánh (chưa cần nối nhau)
- **A:** index catalog + retrieval trả đúng thủ tục cho ~20 câu hỏi test; graph clarify→identify chạy được qua `/chat`.
- **B:** upload ảnh → OCR → `ExtractedDocument` lưu DB; phân loại + trích trường CCCD & giấy chứng sinh.
- **C:** Case CRUD + status machine + assignment; khung frontend (chat widget gọi được `/chat` của A, trang upload gọi API của B).

### Sprint 2 — Nối luồng end-to-end use case khai sinh
- **A:** checklist cá nhân hoá ghi vào `Case.checklist`; answer node kèm citation.
- **B:** autofill form từ OCR; rule engine chạy bộ rule khai sinh → `ValidationReport` + readiness_score; AI checker v1.
- **C:** dashboard cán bộ v1 (danh sách hồ sơ, ưu tiên, tóm tắt LLM); metrics pipeline ghi số liệu.
- **🔗 Checkpoint giữa sprint:** demo nội bộ luồng khai sinh: chat → checklist → upload → autofill → validate.

### Sprint 3 — Hoàn thiện + ops nâng cao + demo
- **A:** few-shot cho follow-up routing, xử lý câu hỏi ngoài phạm vi, mở rộng 3–5 thủ tục.
- **B:** hàng chờ human-review cho trường confidence thấp; mở rộng rule các thủ tục còn lại.
- **C:** anomaly detection + alert trên dashboard; daily digest; submit/handoff mock cổng DVC; polish UI demo.
- **Cả team:** eval nhỏ (bộ câu hỏi + bộ ảnh test), fix bug, kịch bản demo.

## 3. Định nghĩa hoàn thành (DoD)

- Có test cho core flow của nhánh mình (pytest, mirror cấu trúc `src/`).
- CI (ruff + pytest) xanh trước khi merge.
- API mới → cập nhật route trong README nếu ảnh hưởng demo.
- Không merge code làm gãy `/chat`, `/cases`, `/documents` đang chạy của người khác.

## 4. Quy trình làm việc

- Branch: `feat/<owner>-<mô-tả>` (vd `feat/a-checklist-node`), PR nhỏ, ít nhất 1 người review.
- **Sửa `src/models/` hoặc route signature = sửa contract → PR phải tag cả 3 người.**
- File dùng chung (`main.py`, `config.py`, `db.py`): chỉ Dev C sửa trực tiếp, A/B gửi PR cho C review.
- Daily sync 10 phút: hôm qua/hôm nay/blocker; blocker về contract giải quyết ngay trong ngày.

## 5. Rủi ro & phương án

| Rủi ro | Phương án |
|--------|-----------|
| OCR tiếng Việt kém trên ảnh chụp điện thoại | Demo bằng ảnh chuẩn; UI luôn cho người dân sửa tay trường trích xuất (đằng nào cũng cần cho human-review) |
| Không có API cổng DVC thật | `portal_gateway.py` mock — trả biên nhận giả lập; kiến trúc adapter để thay sau |
| Dữ liệu thủ tục thay đổi/khó thu thập | Catalog là JSON + rule là YAML → cán bộ sửa không cần deploy; MVP chỉ cần 3–5 thủ tục nhập tay từ Cổng DVC quốc gia |
| LLM latency/quota khi demo | Fallback rule-based cho planner (bài học C2); cache câu trả lời clarify phổ biến |
