# TTHC Assist — Trợ lý AI hướng dẫn và kiểm tra hồ sơ thủ tục hành chính

> Người dân mô tả nhu cầu bằng ngôn ngữ tự nhiên → nhận checklist cá nhân hoá → chụp ảnh giấy tờ, hệ thống OCR và tự điền biểu mẫu → kiểm tra hồ sơ trước khi nộp → chuyển cổng dịch vụ công. Cán bộ theo dõi, phân công, tóm tắt và nhận cảnh báo bất thường trên dashboard.

## 1. Vấn đề

- Người dân không biết chính xác cần làm thủ tục gì, chuẩn bị giấy tờ nào; chỉ phát hiện thiếu/sai sau khi nộp → đi lại nhiều lần.
- Nhập tay thông tin từ giấy tờ gốc vào biểu mẫu tốn thời gian, dễ sai.
- Cán bộ trả lời câu hỏi lặp lại, khó theo dõi tiến độ, khó phát hiện sớm bất thường vận hành; quy định và biểu mẫu thay đổi thường xuyên.

## 2. Bốn năng lực chính

| # | Năng lực | Module chính | Owner |
|---|----------|--------------|-------|
| 1 | Hướng dẫn thủ tục thông minh (NL → làm rõ → checklist cá nhân hoá) | `src/agents/`, `src/services/retrieval/` | Dev A |
| 2 | OCR trích xuất dữ liệu từ ảnh/scan, tự điền biểu mẫu | `src/services/ocr/` | Dev B |
| 3 | Kiểm tra hồ sơ trước khi nộp (rule engine + AI) | `src/services/validation/`, `rules/` | Dev B |
| 4 | Vận hành nội bộ: theo dõi, phân công, tóm tắt, phát hiện bất thường chuỗi thời gian | `src/services/ops/`, `frontend/` | Dev C |

**Nguyên tắc sản phẩm:** hệ thống chỉ *hỗ trợ hướng dẫn và kiểm tra* — cơ quan có thẩm quyền vẫn tiếp nhận, thẩm định và ra quyết định cuối cùng. Mọi hướng dẫn phải truy vết được về thủ tục/căn cứ pháp lý trong catalog; AI không được bịa yêu cầu giấy tờ.

## 3. Đối tượng sử dụng

- **Người dân:** chat mô tả nhu cầu, nhận checklist, upload giấy tờ, kiểm tra hồ sơ trước khi nộp.
- **Cán bộ:** dashboard hồ sơ, tự phân công, xác nhận trường hợp AI chưa chắc chắn, cập nhật thủ tục/biểu mẫu.
- **Cơ quan quản lý:** số liệu tổng hợp, chất lượng phục vụ, cảnh báo bất thường.

## 4. Tech stack

Kế thừa trực tiếp từ `C2-App-108` (xem `ARCHITECTURE.md §5` — bản đồ tái sử dụng):

- Backend: FastAPI, Python `>=3.11.9,<3.12`
- AI orchestration: LangGraph (một LLM call structured cho rewrite + route + clarify, rule-based fallback)
- Retrieval: Chroma dense + BM25, reciprocal rank fusion (hybrid mặc định)
- OCR: adapter pattern (PaddleOCR local / Google Vision cloud)
- DB: SQLite dev / PostgreSQL prod, SQLAlchemy + Alembic
- Frontend: React + Vite + TypeScript
- Test/lint: pytest, ruff

## 5. Chạy dự án

```bash
pip install -e ".[dev]"

# Dev server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Tests
pytest tests/ -v --tb=short

# Lint (CI gate)
ruff check src/ tests/

# Index catalog thủ tục vào Chroma + build BM25 cache (tuỳ chọn —
# không index vẫn chat được: retrieval tự fallback BM25 in-memory từ catalog)
python scripts/index_procedures.py --source data/procedures --build-bm25

# Seed DB demo
python scripts/seed_db.py
```

### Chat guidance (luồng người dân)

```bash
# Lượt 1 — nhận diện thủ tục (không cần case_id, hệ thống tự tạo Case)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "tôi muốn đăng ký khai sinh cho con mới sinh"}'

# Các lượt sau — kèm case_id nhận được từ lượt 1
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"case_id": "<case_id>", "message": "đã kết hôn, bé sinh ở bệnh viện, được 5 ngày"}'
```

Response (`ChatResponse`): `reply`, `kind` (`clarify` | `checklist` | `answer` | `fallback`),
`clarifying_questions`, và `citations`. Mỗi citation ánh xạ đúng một chunk nguồn qua
`index`, `procedure_id`, `chunk_id`, `section`, `excerpt` và `source_url`; chỉ dấu `[n]`
trong `reply` khớp với `citations[].index`. Tin nhắn được strip và giới hạn 4.000 ký tự.
Mọi câu trả lời về thủ tục đều kèm nguồn; thiếu nguồn thì trả cảnh báo "chưa đủ căn cứ".

Nhận diện thủ tục chỉ dùng identity metadata (`name`, `aliases`, `example_queries`,
`negative_keywords`), tách biệt với content index chứa hồ sơ/lệ phí/biểu mẫu. Trạng thái
chờ chọn thủ tục và chờ trả lời làm rõ được persist trong `Case`, nên người dùng có thể
trả lời bằng số thứ tự ở lượt kế tiếp.

SQLite là cấu hình MVP và chỉ nên chạy một worker. Optimistic-lock conflict trả HTTP 409
thay vì 500. Trước khi public deployment vẫn phải nối JWT ownership (`case.citizen_id`),
rate limit, case expiration và idempotency key; `case_id` không được xem là cơ chế auth.

Env chính (xem `src/config.py`, mẫu ở `.env.example`): `LLM_API_KEY` — API key Anthropic,
model mặc định `claude-haiku-4-5` (thiếu key planner/answer tự rơi về rule-based/extractive
fallback, luồng vẫn chạy); `EMBEDDING_PROVIDER` (`auto`/`google`/`bge-m3`/`fake` — phải khớp
lúc index; `google` cần `GOOGLE_API_KEY` riêng); `DATABASE_URL`, `CHROMA_PERSIST_DIR`.

## 6. Cấu trúc repo

```
src/
  agents/        # LangGraph: state, graph, nodes, tools, prompts (Dev A)
  api/v1/        # FastAPI routes — handler mỏng, gọi services (chia theo owner)
  services/
    retrieval/   # hybrid retrieval — port từ C2-App-108 (Dev A)
    ocr/         # OCR engine, phân loại giấy tờ, autofill form (Dev B)
    validation/  # rule engine + AI cross-check (Dev B)
    ops/         # phân công, tóm tắt, anomaly detection (Dev C)
  models/        # Pydantic contracts — SINGLE SOURCE OF TRUTH, viết trước ở Sprint 0
rules/           # luật kiểm tra khai báo dạng YAML, theo từng thủ tục
data/procedures/ # catalog thủ tục (JSON) — nguồn sự thật cho checklist
scripts/         # index, seed, build BM25
tests/           # pytest, mirror cấu trúc src/
frontend/        # React/Vite (Dev C)
planning/        # TEAM_PLAN.md — kế hoạch 3 người, sprint, contract freeze
```

## 7. Tài liệu

| Tài liệu | Nội dung |
|----------|----------|
| `ARCHITECTURE.md` | Kiến trúc, data flow, data model, bản đồ tái sử dụng từ C2-App-108 |
| `AGENTS.md` | Quy tắc cho AI coding agent |
| `planning/TEAM_PLAN.md` | Phân công 3 dev, sprint plan, integration checkpoint |
