# UBNDAI Officer Flow — Implementation Plan

## 1. Capability summary

Xây dựng cổng xử lý hồ sơ cho cán bộ, cho phép cán bộ đăng nhập theo tổ chức/vai trò, nhận và khóa hồ sơ, xem dữ liệu OCR + tài liệu gốc + findings, xác nhận hoặc bác bỏ cảnh báo, chỉnh sửa dữ liệu OCR có kiểm soát, yêu cầu người dân bổ sung, chuyển chuyên môn và đánh dấu hồ sơ `precheck_ready`.

Mọi thay đổi phải truy vết được theo người thao tác, submission version, rule version và thời gian. Đợt triển khai đầu tiên là P0 end-to-end cho một thủ tục mẫu, ưu tiên `khai_sinh`, nhưng contract phải mở rộng được cho các thủ tục khác.

Hệ thống chỉ hỗ trợ kiểm tra và điều phối. Hệ thống không tự động phê duyệt hoặc từ chối hồ sơ hành chính.

## 2. Scope và non-goals

### Trong scope P0

- Đăng nhập cán bộ và RBAC theo organization scope.
- Queue, claim/assignment, lock hồ sơ và dashboard tổng quan tối thiểu.
- Case detail workspace ba cột: file/evidence, dữ liệu có cấu trúc, findings.
- Hiển thị OCR, confidence, page/bounding box và signed URL tới file private.
- Accept/dismiss/escalate/request-update finding.
- Sửa OCR field, lưu before/after và chạy lại validation.
- Tạo yêu cầu người dân bổ sung, resubmission version mới.
- State machine và readiness gate deterministic.
- Audit log append-only cho access và mutation quan trọng.
- Một thủ tục mẫu end-to-end, dữ liệu demo không chứa PII thật.

### Ngoài scope

- Tự động phê duyệt/từ chối hồ sơ.
- Ký số, thu phí hoặc kết nối Cổng DVC thật.
- Xử lý toàn bộ catalog thủ tục ngay trong đợt đầu.
- Sửa nội dung tài liệu gốc.
- Active learning, rule discovery và bulk operation nâng cao.
- AI summary/Q&A là nguồn sự thật; các năng lực này là P1 sau khi P0 ổn định.

## 3. Fixed decisions và constraints

- Persistence production: PostgreSQL + SQLAlchemy + Alembic; SQLite chỉ dùng local/test qua cùng repository interface.
- Authentication: JWT issuer nội bộ với claims tối thiểu `user_id`, `organization_id`, `roles`; secret lấy từ environment/secret manager.
- API: thêm `/api/v1/officer/*`; giữ `/api/v1/cases` và `/api/v1/ops` làm alias tương thích, cùng gọi service layer và đánh dấu deprecated.
- RBAC và organization scope bắt buộc được kiểm tra ở backend; frontend không được là lớp bảo mật.
- File gốc lưu private storage; chỉ phát signed URL có thời hạn.
- Danh sách và log không được chứa PII thô (CCCD, điện thoại, địa chỉ).
- `ValidationIssue` severity `error` chỉ đến từ rule engine; AI chỉ sinh `warning`/`info`.
- `precheck_ready` không đồng nghĩa với phê duyệt hành chính.
- Không xóa finding, decision hoặc audit event; chỉ tạo decision/state mới.
- Mutation quan trọng dùng optimistic locking và idempotency key.
- Lỗi LLM/OCR không được làm mất dữ liệu; fallback phải vẫn hiển thị dữ liệu DB và rule findings.

## 4. Canonical state machine

Mở rộng `CaseStatus` hiện có thành enum hợp nhất. Các giá trị legacy được giữ để tương thích nhưng không dùng cho workflow mới nếu đã có trạng thái canonical.

```text
draft
  -> submitted_for_precheck
  -> ocr_processing
  -> precheck_processing
  -> awaiting_officer_review
  -> in_officer_review
```

Từ `in_officer_review`:

- `needs_citizen_update`: còn thông tin/tài liệu cần bổ sung.
- `escalated`: chuyển specialist hoặc supervisor.
- `precheck_ready`: không còn blocking error, checklist bắt buộc đạt và low-confidence OCR đã được human review.
- `cancelled`/`closed`: chỉ role có quyền mới thực hiện.

Khi người dân nộp lại:

```text
needs_citizen_update -> resubmitted -> ocr_processing
```

Không cho phép đổi trạng thái bằng `PATCH` trực tiếp. Chỉ transition service được phép đổi trạng thái sau khi kiểm tra quyền, trạng thái hiện tại, submission version, lock và lý do.

## 5. Data model contract

Tất cả schema dùng `src/models/` làm single source of truth. Mọi thay đổi model phải được review theo contract giữa các workstream và có Alembic migration.

### ApplicationCase

- `id`, `case_code`, `organization_id`, `citizen_id`.
- `procedure_id`, `procedure_version_id`.
- `status`, `source_channel`, `priority`.
- `assigned_to`, `assigned_at`, `submitted_at`, `sla_due_at`.
- `current_submission_version`, `version`/optimistic-lock field.

### CaseSubmissionVersion

- `id`, `case_id`, `version`.
- Immutable `form_data`, checklist snapshot.
- `procedure_version_id`, `procedure_rule_version`.
- `created_at`, actor/source metadata.

### CaseDocument và ExtractedField

- Document gắn với `submission_version_id`, private file URI, OCR status/engine/version.
- Field có raw/normalized value, confidence, page, bounding box, review status và edit metadata.
- Confidence dưới threshold bắt buộc `needs_human_review`; không được âm thầm autofill.

### ValidationFinding và OfficerDecision

- Finding có stable ID, submission version, type, severity, source, rule ID/version, confidence, evidence và field/document references.
- Status: `open`, `accepted`, `dismissed`, `escalated`, `superseded`.
- `OfficerDecision` immutable, ghi officer, decision, reason, timestamp.
- Dismiss finding severity `error` bắt buộc reason.
- AI không thể tạo finding `error`.

### SupplementRequest và CaseAuditEvent

- Supplement request chứa public message, finding IDs, due date, creator, status và submission version.
- Audit event append-only, chứa actor, organization, event/object type, object ID, metadata và timestamp.
- Audit cả access vào hồ sơ nhạy cảm, không chỉ mutation.

## 6. Service và API contract

### Service boundaries

- `case_service`: repository CRUD, transition, claim, assignment và lock.
- `review_service`: findings, officer decisions, readiness gate và OCR field edits.
- `supplement_service`: preview/create/list supplement request.
- `audit_service`: append-only audit cho access/mutation.
- `auth/permission_service`: JWT verification, role check và organization scope.
- `dashboard_service`: aggregate query, filter, pagination và cache ngắn hạn.
- `ocr`/`validation`: xử lý theo submission version; rerun validation sau OCR edit.
- `portal_gateway`: adapter mock ở P0, không mô phỏng quyết định hành chính.

### Officer routes

```text
GET    /api/v1/officer/cases
GET    /api/v1/officer/cases/{case_id}
POST   /api/v1/officer/cases/{case_id}/claim
POST   /api/v1/officer/cases/{case_id}/assign
POST   /api/v1/officer/cases/{case_id}/transition
GET    /api/v1/officer/cases/{case_id}/timeline

GET    /api/v1/officer/cases/{case_id}/findings
POST   /api/v1/officer/findings/{finding_id}/accept
POST   /api/v1/officer/findings/{finding_id}/dismiss
POST   /api/v1/officer/findings/{finding_id}/escalate
POST   /api/v1/officer/findings/{finding_id}/request-update

GET    /api/v1/officer/documents/{document_id}/fields
PATCH  /api/v1/officer/extracted-fields/{field_id}
POST   /api/v1/officer/cases/{case_id}/rerun-validation

POST   /api/v1/officer/cases/{case_id}/supplement-requests/preview
POST   /api/v1/officer/cases/{case_id}/supplement-requests
GET    /api/v1/officer/cases/{case_id}/supplement-requests

GET    /api/v1/officer/dashboard/summary
GET    /api/v1/officer/dashboard/common-errors
GET    /api/v1/officer/dashboard/workload
```

Các route cũ `/api/v1/cases` và `/api/v1/ops` delegate cùng service để tránh hai behavior khác nhau. Response dùng envelope thống nhất `success`, `data`, `error`, `pagination`; lỗi chuẩn hóa `401/403/404/409/422/429`.

## 7. Security, performance và reliability

- HTTPS, JWT rotation/refresh, password hashing và rate limit cho auth/mutation.
- Organization filter được áp dụng ở repository/service, không chỉ ở query frontend.
- Private storage, signed URL expiry, PII masking và không log PII.
- Server-side pagination/filter/sort cho queue.
- Dashboard dùng aggregate query và cache ngắn hạn.
- AI summary cache theo submission version; không gọi LLM khi chỉ cần DB/rule.
- Validation rerun theo rule bị ảnh hưởng khi có thể.
- Idempotency key cho transition, decision, supplement request và OCR edit.
- Optimistic lock trả `409` khi version conflict.
- Health/readiness checks, structured logs, backup/restore runbook.

## 8. Frontend contract

Tạo React + Vite + TypeScript vì repo chưa có `frontend/`.

- Login và route guard.
- Dashboard cards click được để mở queue đã lọc.
- Queue có search/filter/sort/pagination và mask PII.
- Workspace ba cột: document/evidence, structured form, findings.
- Highlight page/bounding box cho evidence.
- Footer action bar cho claim, decision, supplement, escalation và ready.
- Timeline audit.
- Loading, empty, forbidden, conflict, OCR failure và LLM unavailable states.

## 9. Test strategy

Áp dụng TDD, coverage tối thiểu 80%.

### Required scenarios

- TC-01: hồ sơ hợp lệ đạt `precheck_ready`.
- TC-02: thiếu trường bắt buộc tạo blocking error và chặn ready.
- TC-03: OCR sai/confidence thấp, officer sửa, rerun validation, lưu before/after.
- TC-04: conflict giữa hai tài liệu có evidence links/highlight đúng.
- TC-05: accept/dismiss finding; dismiss `error` bắt buộc reason và audit.
- TC-06: hai officer claim đồng thời, chỉ một thành công; bên còn lại nhận `409`.
- TC-07: resubmission tạo version mới, findings cũ không ảnh hưởng version hiện hành.
- TC-08: rule version mới chỉ áp dụng hồ sơ mới; hồ sơ cũ giữ version cũ.
- TC-09: thiếu nguồn không được kết luận chắc chắn, gắn human review.
- TC-10: organization A không đọc/ghi được hồ sơ organization B.

### Test layers

- Unit/contract cho models, state machine, readiness, RBAC, masking, signed URL.
- Integration/API cho PostgreSQL repository, migrations, routes, lock, idempotency và audit.
- Playwright E2E: login → queue → claim → review → OCR edit → finding decision → supplement → resubmission → ready → timeline.

## 10. Definition of Done

- PostgreSQL migration và seed demo chạy từ môi trường sạch.
- Một thủ tục mẫu hoạt động end-to-end từ citizen/OCR output tới officer review.
- Mọi mutation/access quan trọng có audit đúng actor/scope/version.
- RBAC, organization isolation, private file access và PII masking đã có test.
- Không còn `NotImplemented` trên P0 path; route handler không chứa business logic.
- `pytest`, `ruff`, frontend build, migration check và Playwright pass.
- Coverage >= 80%.
- Có runbook deploy/rollback, backup/restore và xử lý LLM/OCR outage.
- Demo không chứa PII thật.

## 11. Handoff

Thực hiện theo thứ tự: contract/TDD → persistence/security → case workflow → review/OCR/validation → supplement/versioning → frontend → hardening/deploy. Trước merge bắt buộc security review, code review và verification loop.
