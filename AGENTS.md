# AI Agent Instructions — TTHC Assist

Entrypoint duy nhất cho quy tắc coding-agent trong repo này. File tool-specific (CLAUDE.md, .cursorrules…) phải ngắn và trỏ về đây.

## 1. Thứ tự ưu tiên nguồn

1. Task/issue/PR hiện tại.
2. `ARCHITECTURE.md` và docs liên quan đến vùng code đang sửa.
3. `AGENTS.md` (file này).
4. `planning/TEAM_PLAN.md` cho phân công và quy trình PR.
5. `README.md` cho setup và lệnh chạy.

Không load mọi tài liệu cho mọi task — chỉ đọc phần liên quan.

## 2. Tổng quan

Trợ lý AI hướng dẫn và kiểm tra hồ sơ thủ tục hành chính Việt Nam: guidance qua chat (LangGraph + hybrid RAG trên catalog thủ tục), OCR giấy tờ + autofill biểu mẫu, kiểm tra hồ sơ trước nộp (rule engine + AI), và vận hành nội bộ cho cán bộ (phân công, tóm tắt, anomaly detection). Hệ thống chỉ hỗ trợ — cơ quan có thẩm quyền ra quyết định cuối cùng.

## 3. Ranh giới kiến trúc (bắt buộc)

- Logic agent/LLM orchestration → `src/agents/`. Prompt tập trung ở `src/agents/prompts/`, không rải rác.
- Route handler mỏng → `src/api/`. Không business logic trong handler.
- Business logic → `src/services/` (`retrieval/`, `ocr/`, `validation/`, `ops/`).
- Schema/Pydantic → `src/models/` duy nhất. Không duplicate. **Đổi model = đổi contract giữa 3 workstream → PR phải tag cả team** (xem TEAM_PLAN §4).
- Luật kiểm tra hồ sơ → `rules/*.yaml` (khai báo), engine ở `services/validation/`. Không hardcode luật trong Python theo từng thủ tục.
- Catalog thủ tục → `data/procedures/*.json`. Checklist phải sinh từ catalog, không sinh từ prompt.

## 4. Lệnh phát triển

- Cài đặt: `pip install -e ".[dev]"` (chỉ khi venv cần cập nhật)
- Chạy: `uvicorn src.main:app --reload`
- Test: `pytest tests/ -v --tb=short`
- Lint (CI gate): `ruff check src/ tests/`

Nếu lệnh không chạy được vì thiếu dependency/env, báo lỗi chính xác + đưa manual test steps. Không tuyên bố check đã pass nếu chưa thực chạy.

## 5. Quy tắc grounding TTHC (tương đương quy tắc citation của C2)

- Không bịa tên thủ tục, mã thủ tục, giấy tờ yêu cầu, lệ phí, thời hạn xử lý, căn cứ pháp lý.
- Mọi checklist item phải trace về `DocumentRequirement` trong catalog; mọi câu trả lời về thủ tục phải kèm nguồn (mã thủ tục / văn bản).
- Thiếu nguồn → trả cảnh báo "chưa đủ căn cứ" và gợi ý hỏi cán bộ, không đoán.
- AI checker chỉ sinh `warning`/`info`; `error` chỉ đến từ rule engine.
- OCR field confidence thấp → bắt buộc `needs_human_review`, không im lặng điền vào form.

## 6. Quy tắc LangGraph

- State typed và explicit (`GuidanceState`). Sửa graph tăng dần, giữ contract node hiện có.
- Không giấu logic deterministic trong prompt (điều kiện checklist, tính readiness_score, luật kiểm tra).
- Planner: 1 LLM call structured cho intent+route, rule-based fallback khi LLM lỗi.

## 7. Verification

- Chạy test targeted cho vùng sửa. Core flow / contract model / API / bugfix → phải kèm test hoặc manual test steps.
- Không xoá test để check pass, trừ khi test lỗi thời và ghi rõ lý do.
- Trước merge: CI ruff + pytest phải pass.

## 8. Docs

- Cập nhật README khi setup/lệnh/env/API/cấu trúc thay đổi.
- Không viết tính năng dự kiến như đã có.
