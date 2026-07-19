# API Reference — UBNDAI

> **75 endpoint**, tất cả dưới tiền tố `/api/v1` (trừ `/health` và các trang tài liệu).
>
> Danh sách này **sinh từ router thật**, không viết tay — tái lập bằng đoạn script ở §9. OpenAPI đầy đủ: `GET /openapi.json`, giao diện `GET /docs` (Swagger) hoặc `GET /redoc`.

---

## 1. Bản đồ nhóm

| Nhóm | Tiền tố | Dùng cho | Số endpoint |
|---|---|---|:---:|
| Xác thực | `/auth` | Đăng nhập demo | 1 |
| Chat hướng dẫn | `/chat` | Luồng công dân — trọng tâm sản phẩm | 3 |
| Danh mục thủ tục | `/procedures` | Tra cứu thủ tục, form schema | 4 |
| Hồ sơ (case) | `/cases` | Vòng đời hồ sơ cơ bản | 5 |
| Cổng công dân | `/citizen` | Tải giấy tờ, nộp, theo dõi | 11 |
| Giấy tờ & OCR | `/documents` | Trích xuất, sửa trường | 2 |
| Bản nháp kết quả | `/drafts` | Sinh/xuất/chỉnh sửa DOCX-HTML | 6 |
| Kiểm tra hợp lệ | `/validation` | Rule engine + AI checker | 1 |
| Cổng cán bộ | `/officer` | Xử lý hồ sơ, finding, bổ sung | 14 |
| Dashboard cán bộ | `/officer-dashboard` | Thống kê | 5 |
| Vận hành | `/ops` | Hàng đợi, phân công, bất thường | 6 |
| Quản lý hồ sơ | `/applications` | Vòng đời hồ sơ mở rộng | 9 |
| Hệ thống | `/health`, `/docs`, `/redoc`, `/openapi.json` | — | 5 |

---

## 2. Chat hướng dẫn — luồng chính

Đây là bề mặt API quan trọng nhất; toàn bộ đồ thị LangGraph (`docs/Agent-Features.md`) nằm sau `POST /api/v1/chat`.

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/v1/chat` | Một lượt hội thoại. Lượt đầu không cần `case_id` — hệ thống tự tạo `Case`. |
| `GET` | `/api/v1/chat/starter` | Gợi ý mở đầu (các thủ tục sẵn có) |
| `GET` | `/api/v1/chat/{case_id}/messages` | Lịch sử hội thoại của một hồ sơ |

**Lượt 1 — nhận diện thủ tục:**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "tôi muốn xin giấy phép xây dựng nhà ở riêng lẻ"}'
```

Phản hồi chứa `case_id` — dùng lại cho các lượt sau:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"case_id": "<case_id>", "message": "công trình không thuộc diện thẩm duyệt PCCC"}'
```

**Các trường đáng chú ý trong phản hồi:**

| Trường | Ý nghĩa |
|---|---|
| `reply_kind` | `clarify` \| `checklist` \| `answer` \| `fallback` — frontend render theo dạng này |
| `checklist` | Mục hồ sơ **đã lọc theo tình huống**, mỗi mục truy về một `DocumentRequirement` |
| `citations` | Cơ sở của khối "Đã kiểm chứng nguồn" |
| `evidence` | Các bước kiểm chứng, mỗi bước có `status`: `ready` (đọc được nguồn gốc) hoặc `fallback` (dùng snapshot) — xem `docs/GUARDRAILS.md` lớp 6 |

---

## 3. Danh mục thủ tục

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/procedures` | Liệt kê 5 thủ tục |
| `GET` | `/api/v1/procedures/{procedure_id}` | Chi tiết: `requirements`, `legal_basis`, `source_url`, `processing_days` |
| `GET` | `/api/v1/procedures/{procedure_id}/capabilities` | Năng lực khả dụng (có template bản nháp không, có rule không…) |
| `GET` | `/api/v1/procedures/{procedure_id}/form-schema` | Schema các trường của biểu mẫu |

`procedure_id` hợp lệ: `khai_sinh`, `ket_hon`, `tam_tru`, `can_cuoc`, `giay_phep_xay_dung`.

---

## 4. Hồ sơ & cổng công dân

**Vòng đời cơ bản** (`/cases`):

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/v1/cases` | Tạo hồ sơ |
| `GET` `PATCH` | `/api/v1/cases/{case_id}` | Đọc / cập nhật (gồm `answers` từ các lượt clarify) |
| `POST` | `/api/v1/cases/{case_id}/validate` | Chạy rule engine + AI checker |
| `POST` | `/api/v1/cases/{case_id}/submit` | Nộp |

**Cổng công dân** (`/citizen`) — bản đầy đủ có tải tệp và dòng thời gian:

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/citizen/me` | Thông tin người dùng hiện tại |
| `GET` `POST` | `/api/v1/citizen/cases` | Danh sách / tạo hồ sơ |
| `GET` `PATCH` | `/api/v1/citizen/cases/{case_id}` | Chi tiết / cập nhật |
| `POST` | `/api/v1/citizen/cases/{case_id}/documents/upload-intents` | Xin quyền tải lên (bước 1) |
| `PUT` | `/api/v1/citizen/uploads/{document_id}` | Tải tệp (bước 2) |
| `POST` | `/api/v1/citizen/documents/{document_id}/complete` | Chốt tải lên (bước 3) |
| `POST` | `/api/v1/citizen/documents/{document_id}/preprocess` | Tiền xử lý ảnh trước OCR |
| `POST` | `/api/v1/citizen/format-review` | Kiểm tra chất lượng ảnh **trước** khi tải — chặn ảnh mờ/lệch sớm |
| `POST` | `/api/v1/citizen/cases/{case_id}/submit` | Nộp hồ sơ |
| `GET` | `/api/v1/citizen/cases/{case_id}/timeline` | Dòng thời gian xử lý |

> Quy trình tải lên 3 bước (intent → upload → complete) cho phép lưu tệp ở vùng riêng (`storage_root`) và tách hạn mức, thay vì nhận tệp trực tiếp vào tiến trình API.

**Giới hạn:** 10 tệp/lần, 10 MB/tệp (`src/config.py:84-85`).

---

## 5. OCR & giấy tờ

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/v1/documents/upload` | Tải + trích xuất trong một bước |
| `PATCH` | `/api/v1/documents/{document_id}/fields` | Người dùng sửa lại trường OCR đọc sai |

Kết quả OCR kèm `needs_human_review` — bật khi độ tin cậy dưới `OCR_CONFIDENCE_THRESHOLD` (0,85), có vùng `[ILLEGIBLE]`, hoặc engine và classifier bất đồng về loại giấy tờ. Xem `docs/GUARDRAILS.md` lớp 5.

---

## 6. Bản nháp kết quả

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/drafts/templates/{procedure_id}` | Template + trường bắt buộc |
| `POST` | `/api/v1/drafts/templates/import` | Nhập template từ nguồn đã tra cứu |
| `POST` | `/api/v1/drafts/generate` | Sinh bản nháp (preview HTML) |
| `POST` | `/api/v1/drafts/generate.docx` | Sinh trực tiếp ra DOCX |
| `POST` | `/api/v1/drafts/export.docx` | Xuất bản nháp đã có ra DOCX |
| `POST` | `/api/v1/drafts/revise` | Chỉnh sửa theo yêu cầu bằng LLM |

Render từ template (`src/services/drafts/renderer.py`, `docx_renderer.py`) — **không phải LLM sinh văn bản tự do**. Chỉ `/revise` gọi LLM, và chỉ khi người dùng chủ động yêu cầu.

---

## 7. Cổng cán bộ

**Xử lý hồ sơ** (`/officer`):

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/api/v1/officer/cases` | Danh sách hồ sơ |
| `GET` | `/api/v1/officer/cases/{case_id}` | Chi tiết |
| `POST` | `/api/v1/officer/cases/{case_id}/claim` | Nhận xử lý |
| `POST` | `/api/v1/officer/cases/{case_id}/transition` | Chuyển trạng thái (qua state machine) |
| `POST` | `/api/v1/officer/cases/{case_id}/rerun-validation` | Chạy lại kiểm tra |
| `GET` | `/api/v1/officer/cases/{case_id}/findings` | Danh sách phát hiện |
| `GET` `POST` | `/api/v1/officer/cases/{case_id}/supplement-requests` | Yêu cầu bổ sung |
| `GET` | `/api/v1/officer/cases/{case_id}/timeline` | Dòng thời gian |
| `GET` | `/api/v1/officer/documents/{document_id}/content` · `/fields` | Xem tệp / trường trích xuất |
| `PATCH` | `/api/v1/officer/extracted-fields/{field_id}` | Cán bộ sửa trường |
| `POST` | `/api/v1/officer/findings/{finding_id}/accept` · `/dismiss` · `/escalate` | Xử lý phát hiện |

> **Ba hành động trên finding là thiết kế có chủ đích.** Cán bộ luôn có quyền **bác bỏ** (`dismiss`) phát hiện của AI. AI đề xuất, người quyết định — nhất quán với việc AI không được phát `severity=error`.

**Dashboard** (`/officer-dashboard`): `summary`, `status-distribution`, `application-types`, `timeseries`, `anomalies`.

**Vận hành** (`/ops`): `queue`, `assign`, `metrics`, `digest`, `anomalies`, `cases/{case_id}/summary`.

---

## 8. Quản lý hồ sơ mở rộng

| Method | Path | Mô tả |
|---|---|---|
| `GET` `POST` | `/api/v1/applications` | Danh sách / tạo |
| `GET` | `/api/v1/applications/{application_id}` | Chi tiết |
| `POST` | `/api/v1/applications/{application_id}/documents` | Đính kèm giấy tờ |
| `POST` | `/api/v1/applications/{application_id}/analyze` | Phân tích hồ sơ |
| `POST` | `/api/v1/applications/{application_id}/decisions` | Ra quyết định |
| `PATCH` | `/api/v1/applications/{application_id}/assignment` | Phân công |
| `GET` | `/api/v1/applications/{application_id}/events` | Nhật ký sự kiện |
| `POST` | `/api/v1/applications/{application_id}/resubmit` | Nộp lại sau bổ sung |

Chuyển trạng thái đi qua `src/services/application_state_machine.py` — không cho phép nhảy trạng thái tuỳ tiện.

---

## 9. Xác thực & lỗi

**Đăng nhập:** `POST /api/v1/auth/login`. Ngoài ra hỗ trợ OIDC (`src/services/oidc.py`) với yêu cầu MFA claim — xem `docs/Authorization-Spec.md`.

**Định dạng lỗi.** FastAPI/Pydantic trả `detail` là **chuỗi** với lỗi thường, nhưng là **mảng object** với lỗi validate 422:

```json
{"detail": [{"type": "string_too_short", "loc": ["body", "password"], "msg": "..."}]}
```

Client phải xử lý cả hai dạng. Frontend dùng `extractErrorMessage()` (`frontend/src/api.ts`) — viết ra vì bản đầu hiển thị `[object Object]` cho người dùng.

Lỗi chưa bắt được trả về thông điệp chung, chi tiết chỉ ghi vào log phía server (`src/main.py`).

---

## 10. Tái lập danh sách này

```bash
python -c "
from src.main import app
rows=[]
for r in app.routes:
    m=getattr(r,'methods',None)
    if not m: continue
    m=sorted(m-{'HEAD','OPTIONS'})
    if not m: continue
    rows.append((','.join(m), r.path))
for a,b in sorted(rows,key=lambda x:x[1]): print(f'{a:<12} {b}')
print('Tổng:',len(rows),'endpoint')
"
```

Kiểm thử hợp đồng API: `pytest tests/test_contracts.py tests/test_officer_contracts.py tests/test_application_management_contracts.py`
