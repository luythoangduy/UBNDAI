# UBNDAI Officer Flow — Implementation Steps

## Implementation status (2026-07-17)

| Phase | Status | Notes |
|---|---|---|
| Contract freeze | Done | Officer models, canonical statuses and contract tests added. |
| Auth/RBAC/organization scope | Done for local P0 | HMAC/JWT-compatible token path, demo identities and scope checks; production identity store still required. |
| Case workflow/queue | Done for local P0 | Queue, detail, claim lock, transition guard, timeline and dashboard summary. |
| Findings/OCR/validation | Done for local P0 | Rule engine, AI invariant, OCR fallback/classifier and finding decisions. |
| Supplement/versioning | Partial | Supplement create/list and version-scoped finding contract are present; persistent resubmission migration remains. |
| Officer frontend | Done for local P0 | Filterable dashboard/queue, three-column evidence/OCR/finding workspace, decisions, OCR edit/rerun and audit timeline at `/officer`. |
| Citizen frontend | Done for local P0 | Grounded chat assistant plus create/update/upload/consent/submit flow at `/citizen`. |
| PostgreSQL/migrations/deployment hardening | Deferred | Current store is in-memory for the runnable demo; production rollout must complete repository/migration work before deployment. |

## Cách dùng

- Thực hiện tuần tự theo dependency; không bắt đầu task khi gate của task trước chưa đạt.
- Mỗi task phải có test trước implementation theo TDD.
- Không đổi public model/route mà không cập nhật contract test và migration.
- Mỗi task nhỏ nên là một commit/PR có thể review độc lập.
- P0 chỉ cần một thủ tục mẫu `khai_sinh`; thiết kế không hardcode để mở rộng thủ tục sau.

## Phase 0 — Contract freeze

### OF-001 — Baseline và ADR

- **Mục tiêu:** Ghi nhận trạng thái hiện tại và chốt các quyết định PostgreSQL, JWT nội bộ, `/officer` routes, alias compatibility và optimistic locking.
- **Phụ thuộc:** Không.
- **Khu vực:** `ARCHITECTURE.md`, `planning/TEAM_PLAN.md`, `src/models/`, `src/api/v1/`.
- **Test bắt buộc:** Chạy baseline `pytest tests/ -v --tb=short`, `ruff check src/ tests/`; lưu kết quả, không sửa test để pass.
- **Acceptance:** Có checklist contract; mọi thay đổi model/route từ đây được xem là cross-workstream change.

### OF-002 — Canonical status và role matrix

- **Mục tiêu:** Chốt state machine canonical, legacy mapping và quyền cho `officer_reviewer`, `specialist`, `supervisor`, `procedure_admin`.
- **Phụ thuộc:** OF-001.
- **Khu vực:** `src/models/cases.py`, model auth/officer mới, `src/services/cases.py`.
- **Test bắt buộc:** Unit test transition hợp lệ/không hợp lệ và role matrix.
- **Acceptance:** Không còn đường code cho phép set status tùy ý qua `CaseUpdate`.

### OF-003 — Contract tests cho model mới

- **Mục tiêu:** Viết test RED cho submission version, documents, fields, findings, decisions, supplement và audit.
- **Phụ thuộc:** OF-002.
- **Khu vực:** `tests/test_contracts.py`, test files mirror `src/models/`.
- **Test bắt buộc:** Pydantic validation, immutability, AI không tạo `error`, field confidence bounds.
- **Acceptance:** Test mới fail đúng vì model chưa tồn tại hoặc chưa đủ field; sau đó được giữ làm guard.

## Phase 1 — PostgreSQL persistence và migration

### OF-101 — Database engine/session/repository

- **Mục tiêu:** Implement SQLAlchemy engine, session lifecycle và repository interface cho case/read model.
- **Phụ thuộc:** OF-003.
- **Khu vực:** `src/services/db.py`, `src/services/repositories/`.
- **Test bắt buộc:** Repository CRUD, transaction rollback, test database isolation.
- **Acceptance:** Local dùng SQLite được qua interface; production config dùng PostgreSQL không đổi business code.

### OF-102 — Schema và Alembic migration

- **Mục tiêu:** Tạo bảng/foreign key/index cho case, submission version, documents, fields, findings, decisions, supplement, audit.
- **Phụ thuộc:** OF-101.
- **Khu vực:** `alembic/`, `src/models/` ORM mappings.
- **Test bắt buộc:** Upgrade từ empty DB, downgrade trên môi trường test, unique constraints và foreign-key checks.
- **Acceptance:** Migration chạy sạch từ database rỗng; index có cho `organization_id`, `status`, `assigned_to`, `submission_version_id`.

### OF-103 — Seed dữ liệu demo an toàn

- **Mục tiêu:** Seed users/roles, organization, một procedure và cases có finding/OCR edge cases.
- **Phụ thuộc:** OF-102.
- **Khu vực:** `scripts/seed_db.py`, `data/procedures/`.
- **Test bắt buộc:** Seed idempotent, không chứa dữ liệu cá nhân thật.
- **Acceptance:** Có tối thiểu hồ sơ hợp lệ, hồ sơ blocking error và hồ sơ confidence thấp.

## Phase 2 — Authentication, RBAC và scope

### OF-201 — JWT issuer và password/session flow

- **Mục tiêu:** Implement login, access token, refresh token, password hashing và secret configuration.
- **Phụ thuộc:** OF-102, OF-103.
- **Khu vực:** `src/services/auth.py`, `src/models/auth.py`, `src/api/v1/auth.py`, `src/config.py`.
- **Test bắt buộc:** Valid/invalid credentials, expired token, refresh rotation, secret missing at startup.
- **Acceptance:** Anonymous không vào officer routes; không hardcode JWT secret.

### OF-202 — Permission dependencies và organization filtering

- **Mục tiêu:** Tạo FastAPI dependencies cho role và organization scope; áp dụng ở service/repository.
- **Phụ thuộc:** OF-201.
- **Khu vực:** `src/api/dependencies.py`, `src/services/permissions.py`, repositories.
- **Test bắt buộc:** Officer/specialist/supervisor/admin matrix; TC-10 cross-organization isolation.
- **Acceptance:** Forbidden trả `403`; object không tồn tại ngoài scope không leak thành công tin.

### OF-203 — Security baseline

- **Mục tiêu:** Chuẩn hóa error envelope, rate limiting, request ID, CORS/HTTPS config và PII-safe logging.
- **Phụ thuộc:** OF-202.
- **Khu vực:** `src/api/errors.py`, `src/main.py`, config/logging modules.
- **Test bắt buộc:** Error response contract, rate limit auth/mutation, log redaction.
- **Acceptance:** Không log raw CCCD/phone/address/token; response có `success/data/error/pagination`.

## Phase 3 — Case workflow và queue

### OF-301 — State transition service

- **Mục tiêu:** Implement transition matrix, preconditions, reason validation và optimistic lock.
- **Phụ thuộc:** OF-002, OF-102, OF-202.
- **Khu vực:** `src/services/cases.py`, `src/models/cases.py`.
- **Test bắt buộc:** Happy path, forbidden transition, stale version `409`, idempotent retry.
- **Acceptance:** Chỉ transition service được đổi status; mọi transition tạo audit event.

### OF-302 — Claim/assignment/lock

- **Mục tiêu:** Claim atomic, assign/reassign theo role, ghi `assigned_at`, priority và reason.
- **Phụ thuộc:** OF-301.
- **Khu vực:** `src/services/ops/assignment.py`, case repository.
- **Test bắt buộc:** TC-06 concurrent claim, supervisor reassignment, idempotency.
- **Acceptance:** Hai cán bộ không cùng claim thành công một hồ sơ không có cảnh báo.

### OF-303 — Officer case API

- **Mục tiêu:** Implement list/detail/claim/assign/transition/timeline dưới `/api/v1/officer/cases`.
- **Phụ thuộc:** OF-301, OF-302.
- **Khu vực:** `src/api/v1/officer_cases.py`, `src/api/v1/router.py`.
- **Test bắt buộc:** Pagination/filter/sort, scope, response envelope, timeline ordering.
- **Acceptance:** Queue trả server-side pagination; PII được mask; route handlers chỉ gọi services.

### OF-304 — Legacy route aliases

- **Mục tiêu:** Delegate `/api/v1/cases` và `/api/v1/ops` vào service mới, giữ contract cũ nơi có thể.
- **Phụ thuộc:** OF-303.
- **Khu vực:** `src/api/v1/cases.py`, `src/api/v1/ops.py`.
- **Test bắt buộc:** Existing contract tests và alias parity tests.
- **Acceptance:** Không có business logic duplicate giữa alias và officer routes.

## Phase 4 — Findings, OCR và validation

### OF-401 — Version-aware OCR persistence

- **Mục tiêu:** Persist documents/fields theo submission version, confidence, page/bounding box và review state.
- **Phụ thuộc:** OF-102, OF-301.
- **Khu vực:** `src/services/ocr/`, `src/models/documents.py`, document routes.
- **Test bắt buộc:** Field map, confidence threshold, missing OCR fallback, TC-03 setup.
- **Acceptance:** Low confidence luôn gắn `needs_human_review`; file gốc không bị sửa.

### OF-402 — Findings persistence và evidence contract

- **Mục tiêu:** Map rule/AI outputs thành findings stable ID, source/rule version, evidence references và status.
- **Phụ thuộc:** OF-401.
- **Khu vực:** `src/services/validation/`, `src/models/validation.py`.
- **Test bắt buộc:** TC-02, TC-04, TC-08, AI-error invariant, submission-version isolation.
- **Acceptance:** Error chỉ từ rule; finding trỏ được tới document/field/page/bbox và submission version.

### OF-403 — Finding decisions API

- **Mục tiêu:** Implement list/accept/dismiss/escalate/request-update và immutable OfficerDecision.
- **Phụ thuộc:** OF-402, OF-202.
- **Khu vực:** `src/services/review.py`, `src/api/v1/officer_findings.py`.
- **Test bắt buộc:** TC-05, permission matrix, duplicate idempotency, audit event.
- **Acceptance:** Dismiss blocking error bắt buộc reason; không xóa finding/decision.

### OF-404 — OCR edit và rerun validation

- **Mục tiêu:** Cho phép officer/specialist sửa field đã trích xuất, lưu before/after và chạy lại rules bị ảnh hưởng.
- **Phụ thuộc:** OF-403.
- **Khu vực:** `src/services/review.py`, `src/services/validation/`, officer OCR routes.
- **Test bắt buộc:** TC-03, validation failure fallback, stale lock.
- **Acceptance:** Finding cũ được supersede/recompute đúng version; audit có old/new value nhưng không log PII ngoài policy.

### OF-405 — Readiness gate

- **Mục tiêu:** Tính deterministic readiness và chặn `precheck_ready` khi còn blocking error/checklist thiếu/human review unresolved.
- **Phụ thuộc:** OF-402, OF-404.
- **Khu vực:** `src/services/validation/`, `src/services/cases.py`.
- **Test bắt buộc:** TC-01, TC-02, combinations of accepted/dismissed/open findings.
- **Acceptance:** Ready chỉ được tạo bởi service sau khi mọi precondition pass.

## Phase 5 — Supplement và resubmission versioning

### OF-501 — Supplement preview/create/list

- **Mục tiêu:** Sinh preview từ findings, cho officer sửa message, gửi request tối đa ba thao tác UI.
- **Phụ thuộc:** OF-403, OF-405.
- **Khu vực:** `src/services/supplement.py`, `src/api/v1/officer_supplements.py`.
- **Test bắt buộc:** Finding linkage, required message, due date validation, idempotency và audit.
- **Acceptance:** Request chứa finding IDs, public message, creator, due date và chuyển case sang `needs_citizen_update`.

### OF-502 — Submission version creation

- **Mục tiêu:** Khi người dân nộp lại, tạo immutable version mới, snapshot form/checklist/rule version và giữ lịch sử cũ.
- **Phụ thuộc:** OF-501, OF-405.
- **Khu vực:** `src/services/cases.py`, `src/services/portal_gateway.py`, migration/model.
- **Test bắt buộc:** TC-07, duplicate resubmit, old findings ignored, rule version snapshot.
- **Acceptance:** `current_submission_version` tăng đúng một lần; version cũ không bị ghi đè.

### OF-503 — Mock handoff gateway

- **Mục tiêu:** Tạo adapter handoff P0 tới cổng DVC giả lập, không kết luận phê duyệt.
- **Phụ thuộc:** OF-502.
- **Khu vực:** `src/services/portal_gateway.py`, case API.
- **Test bắt buộc:** Blocking error chặn handoff; retry idempotent; gateway failure giữ dữ liệu.
- **Acceptance:** Handoff chỉ đóng gói hồ sơ/version hiện hành và trả receipt giả lập.

## Phase 6 — Officer frontend P0

### OF-601 — Frontend scaffold và API client

- **Mục tiêu:** Tạo React/Vite/TypeScript app, typed API client, auth state, route guards và error handling.
- **Phụ thuộc:** OF-203, OF-303.
- **Khu vực:** `frontend/`.
- **Test bắt buộc:** Typecheck/build, auth guard component tests.
- **Acceptance:** Officer login và redirect unauthorized hoạt động.

### OF-602 — Dashboard và queue UI

- **Mục tiêu:** Dashboard cards, filters, queue table, pagination, mask PII và loading/error states.
- **Phụ thuộc:** OF-601, OF-303.
- **Test bắt buộc:** Component tests, filter query tests, forbidden/empty states.
- **Acceptance:** Click card mở queue đã lọc; không tính aggregate toàn bộ ở frontend.

### OF-603 — Three-column case review workspace

- **Mục tiêu:** File viewer/evidence, structured form/OCR, findings panel và timeline.
- **Phụ thuộc:** OF-401, OF-403, OF-601.
- **Test bắt buộc:** Component tests cho confidence, evidence highlight, field edit, decision modal.
- **Acceptance:** Cán bộ xem được source, field, finding severity/status và audit timeline.

### OF-604 — Action bar và conflict handling

- **Mục tiêu:** Claim, accept/dismiss, supplement, escalate, ready actions; xử lý `409`, permission denied và outage.
- **Phụ thuộc:** OF-503, OF-603.
- **Test bắt buộc:** Playwright critical flow và concurrent lock scenario.
- **Acceptance:** Không cho thao tác ready nếu backend từ chối; UI hiển thị lỗi có thể hành động.

## Phase 7 — Metrics, hardening và deployment

### OF-701 — Dashboard aggregates và metrics

- **Mục tiêu:** Summary, common errors, workload, review time, late rate và supplement rounds.
- **Phụ thuộc:** OF-303, OF-405, OF-501.
- **Khu vực:** `src/services/ops/`, officer dashboard routes.
- **Test bắt buộc:** Aggregate correctness, date/procedure/status filters, cache expiry.
- **Acceptance:** Query server-side; không đưa PII vào aggregate response.

### OF-702 — Observability và outage behavior

- **Mục tiêu:** Structured logs, metrics, health/readiness, LLM/OCR fallback, backup/restore runbook.
- **Phụ thuộc:** OF-701.
- **Test bắt buộc:** LLM outage, OCR outage, DB connectivity/readiness và log redaction.
- **Acceptance:** AI/OCR failure không mất hồ sơ; operator có signal và hướng xử lý.

### OF-703 — Security review và dependency audit

- **Mục tiêu:** Review auth, input validation, file access, secrets, rate limits, SQL queries và PII handling.
- **Phụ thuộc:** OF-702.
- **Test bắt buộc:** Security checklist, `pip audit`/dependency audit nếu môi trường hỗ trợ.
- **Acceptance:** Không còn critical/high issue chưa có mitigation.

### OF-704 — CI/CD và deployment smoke test

- **Mục tiêu:** Docker/config/env, migration step, frontend build, HTTPS/CORS, deploy/rollback.
- **Phụ thuộc:** OF-703.
- **Test bắt buộc:** Clean deploy, migration upgrade, rollback smoke, Playwright against deployed URL.
- **Acceptance:** Public demo chỉ dùng synthetic data, có seed account, rollback và backup instructions.

## Required test matrix

| ID | Scenario | Expected result |
|---|---|---|
| TC-01 | Hồ sơ hợp lệ | Có thể chuyển `precheck_ready`. |
| TC-02 | Thiếu trường bắt buộc | Rule tạo `error`, không thể ready. |
| TC-03 | OCR đọc sai/confidence thấp | Officer sửa, validation chạy lại, lưu before/after. |
| TC-04 | Mâu thuẫn hai tài liệu | Cả hai evidence được link/highlight. |
| TC-05 | Bác bỏ/công nhận finding | Decision immutable; dismiss error cần reason. |
| TC-06 | Hai officer claim đồng thời | Một thành công, một nhận `409`/lock warning. |
| TC-07 | Hồ sơ nộp lại | Tạo version mới; findings cũ không quyết định hiện tại. |
| TC-08 | Rule thay đổi | Case cũ giữ rule version; case mới dùng published version. |
| TC-09 | Không đủ nguồn | Không kết luận chắc chắn; gắn manual review. |
| TC-10 | Truy cập trái phép | Organization khác nhận `403` hoặc not-found policy, không leak dữ liệu. |

## Integration acceptance flow

```text
Login
  -> queue đúng organization scope
  -> claim hồ sơ
  -> mở workspace
  -> xem file/OCR/findings/evidence
  -> sửa OCR field
  -> rerun validation
  -> accept/dismiss finding
  -> preview + sửa + gửi supplement
  -> resubmit tạo version mới
  -> xác nhận không còn blocking error
  -> mark precheck_ready
  -> xem timeline đầy đủ
```

## Final release gate

- `pytest tests/ -v --tb=short` pass.
- `ruff check src/ tests/` pass.
- Frontend typecheck/build pass.
- Coverage >= 80%.
- TC-01 đến TC-10 pass.
- Playwright E2E critical flow pass.
- Migration chạy từ DB rỗng và database backup/restore được kiểm tra.
- Security review không còn critical/high unresolved.
- README/runbook cập nhật nếu setup, env, API hoặc deployment thay đổi.
