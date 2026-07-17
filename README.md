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
`primary_intent`, `detected_intents`, `clarifying_questions`, và `citations`. Một message
có thể mang nhiều intent (ví dụ `fee` + `processing_time` + `agency` + `checklist`).
Mỗi citation ánh xạ đúng một chunk nguồn qua
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

### Intent routing

| Nhóm | Intent | Hành vi |
|---|---|---|
| Điều hướng | `procedure_discovery`, `clarification_answer` | Identify hoặc cập nhật answers trước khi chọn response |
| Chuyển thủ tục | `switch_procedure`, `switch_confirmation` | Reset answers/checklist; yêu cầu xác nhận trước nếu đã có document |
| Thông tin | `fee`, `processing_time`, `agency`, `legal_basis`, `forms` | Đọc trực tiếp `Procedure`, hỗ trợ nhiều intent cùng lượt |
| Hồ sơ | `checklist` | Sinh từ requirements; có thể ghép cùng câu trả lời thông tin |
| Chưa tích hợp | `status_tracking`, `submission`, `document_upload` | Trả fallback minh bạch, không giả vờ đã tra cứu/nộp |
| Hội thoại | `greeting`, `thanks`, `capabilities` | Trả lời không qua procedure RAG |
| Ngoài phạm vi | `out_of_scope`, `unknown` | Không retrieve thủ tục; hướng người dùng mô tả lại nhu cầu hành chính |

Precedence: pending candidate → deterministic answer extraction → intent rõ → LLM semantic
fallback cho wording `unknown/general` → route. Với mixed intent, state update và response
intent được xử lý độc lập để việc ghi nhận câu làm rõ không làm mất câu hỏi chính.

Identity matching yêu cầu exact name/alias hoặc signature nhiều token; một token như `sinh`
không đủ chọn `khai_sinh`. Negative phrase trong cấu trúc phủ định không chặn positive match.
Clarification parser consume từng clause đúng một lần và vẫn cho phép câu explicit sửa answer
đã lưu. Checklist khi chưa đủ dữ liệu chỉ hiển thị giấy tờ chắc chắn áp dụng, được persist như
checklist tạm và trả lại các câu hỏi còn thiếu cho frontend.

Env chính (xem `src/config.py`, mẫu ở `.env.example`): `LLM_API_KEY` — API key Anthropic,
model mặc định `claude-haiku-4-5` (thiếu key planner/answer tự rơi về rule-based/extractive
fallback, luồng vẫn chạy); `EMBEDDING_PROVIDER` (`auto`/`google`/`bge-m3`/`fake` — phải khớp
lúc index; `google` cần `GOOGLE_API_KEY` riêng); `DATABASE_URL`, `CHROMA_PERSIST_DIR`.

### Sinh bản nháp kết quả thủ tục

Mẫu kết quả không dùng chung một thể thức pháp lý. Mỗi mẫu trong
`data/draft_templates/*.json` gắn với đúng `procedure_id`, khai báo nguồn pháp lý,
phiên bản, trường dữ liệu và layout riêng. Service này dựng dữ liệu deterministic,
không gọi OCR và không tự suy diễn căn cứ pháp lý.

```bash
# Xem template/các trường bắt buộc của thủ tục khai sinh
curl http://localhost:8000/api/v1/drafts/templates/khai_sinh

# Sinh preview Giấy khai sinh (rút gọn dữ liệu minh họa)
curl -X POST http://localhost:8000/api/v1/drafts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "procedure_id": "khai_sinh",
    "values": {
      "ho_ten_con": "Nguyễn An",
      "ngay_sinh": "2026-07-17",
      "gioi_tinh": "Nữ",
      "dan_toc": "Kinh",
      "quoc_tich": "Việt Nam",
      "noi_sinh": "Bệnh viện A, phường X, thành phố Hà Nội",
      "que_quan": "phường X, thành phố Hà Nội",
      "ho_ten_me": "Nguyễn Thị B",
      "nam_sinh_me": "1995",
      "dan_toc_me": "Kinh",
      "quoc_tich_me": "Việt Nam",
      "noi_cu_tru_me": "phường X, thành phố Hà Nội",
      "noi_dang_ky": "Ủy ban nhân dân phường X, thành phố Hà Nội",
      "ngay_dang_ky": "2026-07-18"
    }
  }'

# Tải bản nháp Word với cùng request body
curl -X POST http://localhost:8000/api/v1/drafts/generate.docx \
  -H "Content-Type: application/json" \
  -d @draft-request.json \
  --output giay-khai-sinh-du-thao.docx
```

Giấy khai sinh dùng mẫu/cách ghi theo Thông tư 04/2020/TT-BTP; Tờ khai đăng ký
khai sinh là mẫu đầu vào khác và đã được cập nhật theo Thông tư 04/2024/TT-BTP.
Renderer DOCX dùng `python-docx`; thông số A4, lề, font, cỡ chữ, giãn dòng, kích
thước tiêu đề và bảng mặt sau được khai báo trong `docx_style` của từng template,
không dùng một style chung cho mọi thủ tục. Riêng Giấy khai sinh đang mã hóa theo
Phụ lục 1: Times New Roman Unicode 13 pt, giãn dòng 21,5 pt, tiêu đề 22 pt và bảng
mặt sau 158 x 260 mm. Test kiểm tra trực tiếp các thuộc tính OOXML này.
`python-docx` chỉ ghi tên font, không nhúng bản quyền font vào file; máy mở/in
phải có Times New Roman, nếu không Word/LibreOffice có thể tự thay font và làm
thay đổi ngắt dòng.

API luôn gắn watermark `DỰ THẢO - KHÔNG CÓ GIÁ TRỊ PHÁP LÝ`, để trống quốc huy
bằng khung giữ chỗ 20 x 20 mm và không sinh chữ ký/con dấu. File là bản rà soát
thể thức, không tái tạo nền bảo an và không thay thế phôi do Bộ Tư pháp in, phát
hành. Header phản hồi DOCX có `X-Draft-Legal-Status: review-only` để client không
nhầm với giấy tờ đã phát hành.

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
