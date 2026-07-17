# Application-management Phase 1 audit

Date: 2026-07-18
Scope: repository inspection only; no feature implementation

## 1. Audit inputs and repository discrepancies

I read the repository instruction files before inspecting code:

- `AGENTS.md` (source of agent/coding rules)
- `CLAUDE.md` (pointer to `AGENTS.md`)
- `ARCHITECTURE.md` (module boundaries, contracts, and reuse map)

The plan path named in the request does not exist. The matching, currently
untracked plan is [`planning/application-management-plan-uiux.md`](./application-management-plan-uiux.md).
The plan also references `DESIGN.md` and `REPO_GUIDELINE.md`; neither file
exists. I used the actual `-uiux.md` plan, the architecture document, the
officer PRD, `TEAM_PLAN.md`, and the supplied
[`docs/ui/application-management-reference.png`](../docs/ui/application-management-reference.png).

The PNG is a visual direction for an officer dashboard, application list,
application detail/cautions, and two decision dialogs. It is not evidence that
any of those screens or data contracts already exist.

## 2. Executive finding

The repository already has an officer-review vertical slice. Its canonical
aggregate is `ApplicationCase` in `src/models/officer.py`, persisted (partly)
as `application_cases`, with versioned submissions, documents, OCR fields,
validation findings, decisions, supplement requests, and audit events. The
current API and UI use `/officer/cases`, not the plan's new `/applications`
resource.

The implementation should extend that slice and retain compatibility URLs,
rather than create `Application`, `ApplicationDocument`, and a third case
store. Two incompatible case domains must remain distinct during migration:
the legacy `Case`/raw-SQLite guidance flow and the officer `ApplicationCase`/
SQLAlchemy flow. The most important Phase 2+ prerequisite is replacing the
officer store's partial in-memory persistence with transactional persistence.

## 3. Backend inventory and reuse map

| Concern | Existing implementation | Reuse/audit finding |
|---|---|---|
| Officer application model | `src/models/officer.py`: `ApplicationCase`, `OfficerCaseStatus`, `CaseSubmissionVersion` | Extend these contracts; `case_code` is the plan's application code, `procedure_id`/version is the type/version, and `assigned_to`, timestamps, status, form/checklist, organization scope, and optimistic `version` already exist. Do not add parallel `src/models/application*.py` models. |
| Citizen/guidance case | `src/models/cases.py`, `src/services/cases.py`, `/api/v1/cases` | Separate legacy domain used by chat/guidance. Its status vocabulary and checklist shape differ. Do not rename/drop its `cases` or `case_messages` tables. Bridge deliberately at submission. |
| Documents and OCR | `src/models/officer.py:CaseDocument`, `src/models/documents.py:ExtractedDocument`, `src/models/officer.py:ExtractedFieldRecord`; `src/api/v1/citizen.py`; `src/services/storage.py`; `src/services/ocr/{pipeline,preprocessing,classifier,engine,form_filler}.py` | Reuse private storage, magic-byte checks, upload intent/complete flow, OCR confidence and `needs_human_review`, bounding boxes, and field-edit audit. The standalone OCR pipeline still returns a fake `file_id`; use the citizen/store path for persisted records. |
| Deterministic review | `src/services/validation/rule_engine.py`, `rules/khai_sinh.yaml`, `src/models/validation.py` | Reuse YAML rules, deterministic readiness score, and the invariant that only rule logic may emit `error`. Adapt output to persisted `ValidationFinding` rather than creating a second validation engine. |
| AI review | `src/services/validation/ai_checker.py`, `src/agents/prompts/validation.py` | Reuse advisory warning/info behavior and concise evidence. Never let LLM output create a blocking error or expose chain-of-thought. |
| Officer queue/detail/actions | `src/services/officer_store.py` | Current methods include `list_cases`, `get_case`, `claim`, `transition`, `create_supplement`, `findings_for`, `decide`, `update_field`, `rerun_validation`, and `timeline`. Preserve behavior as a compatibility facade while moving storage and transactions into a repository/service. |
| Existing officer API | `src/api/v1/officer.py`, included by `src/api/v1/__init__.py` | Reuse the `{success, data, pagination}` envelope, masking helpers, organization scope, 401/403/404/409/422 conventions, and existing URLs. The list lacks type/anomaly/date/officer filters; detail currently strips `form_data`/checklist, so add policy-aware DTOs rather than exposing the raw model. |
| Authentication/RBAC | `src/services/auth.py`, `src/services/oidc.py`, `OfficerIdentity`, `TokenClaims` | Backend bearer JWT/HMAC and `require_role` are reusable. Current roles are `citizen`, `officer_reviewer`, `specialist`, `supervisor`; there is no user table and no complete OIDC callback. Map plan roles (`CITIZEN`, `OFFICER`, `ADMIN`) to existing claims; do not invent local user persistence in this phase. |
| Upload/review content access | `src/api/v1/citizen.py`, officer document content/fields routes, `src/services/storage.py` | Reuse owner/org authorization and private object storage. Add document-version retention for resubmission; do not duplicate binary storage. |
| Activity/history | `CaseAuditEvent`, `AuditEventORM` (`case_audit_events`), `OfficerStore._audit/timeline`, `NotificationEventORM` | Reuse as the source for timeline and application events. Existing events cover create/submit/upload/claim/transition/finding/OCR edit/validation rerun. Make decision + transition + notification one transaction later. |
| Metrics/ops | `src/models/ops.py`, `src/api/v1/ops.py`, `src/services/ops/{assignment,anomaly,summarizer}.py` | Assignment, summaries, z-score helper, and legacy zero-filled daily metrics are reusable patterns. Metrics are not persisted; `/ops/anomalies` returns `[]`; officer summary has no date, granularity, trends, or distributions. |
| Persistence | `src/services/persistence.py`, `src/models/orm.py`, `alembic/versions/0001_persistence_baseline.py` | Existing SQLAlchemy tables: `application_cases`, `case_submission_versions`, `case_documents`, `case_audit_events`, `routing_decisions`, `consent_records`, `background_jobs`, `notification_events`. Only cases/submissions/documents/audit are partially saved/loaded by `OfficerStore`; findings, fields, decisions, supplements, consents, idempotency, and metrics are not durable. |
| Tests | `tests/test_officer_api.py`, `test_officer_contracts.py`, `test_persistence.py`, `test_citizen_submission_flow.py`, `test_ocr_*`, `test_rule_engine.py`, `test_ai_checker.py`, `test_validation_api.py`, `tests/conftest.py` | Extend these tests; add migration/repository/state-machine/API/dashboard coverage. The singleton in-memory store makes current tests order-sensitive. |

### Backend status and decision compatibility

The plan's uppercase statuses do not match the persisted lower-case officer
statuses (`submitted_for_precheck`, `ocr_processing`,
`precheck_processing`, `awaiting_officer_review`, `in_officer_review`,
`needs_citizen_update`, `resubmitted`, `precheck_ready`, `closed`, etc.). Keep
the existing values in storage and expose a display/mapping layer. The product
PRD is a pre-check workflow, so `precheck_ready` must not be relabeled as
official approval. Existing `OfficerDecision` is finding-scoped; the two
reference actions are case-scoped and multi-finding. Add a separate append-only
case decision contract/table and compose “return” with the existing
`SupplementRequest`.

## 4. Frontend inventory and reuse map

### Existing stack and structure

- React + TypeScript + Vite: `frontend/package.json`, `vite.config.ts`,
  `tsconfig.json`.
- All screens are in `frontend/src/main.tsx` (636 lines). Reusable symbols:
  `Shell`, `Login`, `CitizenPortal`, `Status`, `Empty`, `OfficerPortal`,
  `Dashboard`, `ReviewWorkspace`, `EvidencePanel`, `DataPanel`, and
  `FindingsPanel`.
- API client: `frontend/src/api.ts` (`api`, `apiBlob`, `ApiError`, bearer
  injection, envelope unwrapping, separate citizen/officer token keys,
  `idempotency`).
- Contracts/helpers: `frontend/src/types.ts` and `frontend/src/utils.ts`.
- Icons: `lucide-react`. TipTap is present for the unrelated document editor.
- State/query/forms: no query/cache library, router, form/schema library, or
  toast/dialog primitive. Server state is local `useState`/`useEffect` with
  manual refresh.
- Charts: no chart library. No table component or general component library.
- Tests/build: `npm test` runs Vitest; `npm run build` runs `tsc -b && vite
  build`; only `frontend/src/utils.test.ts` exists. There is no frontend lint
  script or Testing Library setup.

### Existing design system

`frontend/src/styles.css:1-16` defines the current tokens: `--navy`,
`--navy-2`, `--blue`, `--teal`, `--red`, `--gold`, `--green`, `--line`,
`--muted`, `--paper`, and `--shadow`. Existing button/input/focus, alert,
status badge, empty, skeleton, dashboard-card, review-panel, and responsive
styles are reusable. The root declares an Inter-first Vietnamese-safe stack
but does not load Inter, so Segoe UI is the normal Windows fallback.

The officer UI currently uses tiny operational text and a three-column review
workspace. Extract new officer screens instead of appending to the monolith.

### Routing and authorization gaps

`App()` only checks `location.pathname.startsWith('/officer')`; there is no
React Router, nested route, route parameter, URL filter state, tab deep-link, or
route-level error boundary. The browser UI relies on token presence; server
authorization is the security boundary. There is no refresh token or identity
endpoint in the client.

`src/main.py` mounts `frontend/dist` under `/citizen` and `/officer` with
`StaticFiles(html=True)`. Direct navigation to `/officer/dashboard` or
`/officer/applications/:id` will not reliably receive the SPA index without a
fallback route (or an intentional hash-routing choice).

## 5. Exact files to modify (future implementation phases)

This Phase 1 deliverable does not modify any of these files; the following is
the implementation boundary identified by the audit.

### Backend/persistence

```text
src/models/officer.py
src/models/__init__.py
src/services/persistence.py
src/models/orm.py
src/services/officer_store.py
src/services/auth.py
src/services/oidc.py                 (only if production identity mapping changes)
src/services/ocr/pipeline.py
src/services/validation/rule_engine.py
src/services/validation/ai_checker.py
src/api/v1/officer.py
src/api/v1/citizen.py
src/api/v1/__init__.py
src/main.py
src/config.py
.env.example
alembic/env.py
alembic/versions/0001_persistence_baseline.py
scripts/seed_db.py
README.md
rules/khai_sinh.yaml                  (only when rule coverage is extended)
tests/conftest.py
tests/test_persistence.py
tests/test_officer_contracts.py
tests/test_officer_api.py
tests/test_citizen_submission_flow.py
```

### Frontend

```text
frontend/package.json
frontend/package-lock.json
frontend/src/main.tsx
frontend/src/api.ts
frontend/src/types.ts
frontend/src/utils.ts
frontend/src/styles.css
frontend/vite.config.ts              (only if test/setup or lazy routes require it)
frontend/README.md
frontend/src/utils.test.ts            (extend; do not delete)
```

New generic CSS must be scoped under an officer root (for example
`.officer-app`) so citizen/chat/editor screens are not redesigned.

## 6. Exact files to add (future implementation phases)

### Backend

```text
alembic/versions/0002_add_application_management.py
src/models/officer_dashboard.py
src/services/application_repository.py
src/services/application_state_machine.py
src/services/application_analysis.py
src/services/officer_dashboard.py
src/api/v1/applications.py              (new API surface; retain /officer/cases shims)
src/api/v1/officer_dashboard.py
tests/test_application_migrations.py
tests/test_application_repository.py
tests/test_application_state_machine.py
tests/test_application_analysis.py
tests/test_application_api.py
tests/test_officer_dashboard.py
scripts/seed_application_demo_data.py  (Phase 10, explicit/idempotent only)
```

Do not add `src/schemas/*`: repository instructions make `src/models/` the
single Pydantic contract surface. Do not add `application_documents` or an
independent event table; extend/reuse the existing ORM tables instead.

### Frontend

```text
frontend/src/app/AppRouter.tsx
frontend/src/app/QueryProvider.tsx
frontend/src/auth/RequireRole.tsx
frontend/src/layouts/OfficerLayout.tsx
frontend/src/pages/officer/OfficerDashboardPage.tsx
frontend/src/pages/officer/ApplicationListPage.tsx
frontend/src/pages/officer/ApplicationDetailPage.tsx
frontend/src/api/applications.ts
frontend/src/api/officerDashboard.ts
frontend/src/application-management-types.ts
frontend/src/components/ui/Dialog.tsx
frontend/src/components/ui/LoadingState.tsx
frontend/src/components/ui/ErrorState.tsx
frontend/src/components/ui/EmptyState.tsx
frontend/src/components/applications/ApplicationTypeTag.tsx
frontend/src/components/applications/ApplicationStatusBadge.tsx
frontend/src/components/applications/ConfidenceIndicator.tsx
frontend/src/components/applications/AnomalyAlert.tsx
frontend/src/components/applications/AnomalyList.tsx
frontend/src/components/applications/OfficerDecisionDialog.tsx
frontend/src/components/applications/ApplicationTimeline.tsx
frontend/src/components/applications/ExtractedFieldsPanel.tsx
frontend/src/components/applications/ApplicationFilters.tsx
frontend/src/components/applications/ApplicationTable.tsx
frontend/src/components/applications/ApplicationMobileList.tsx
frontend/src/components/dashboard/DashboardFilters.tsx
frontend/src/components/dashboard/DashboardSummaryCards.tsx
frontend/src/components/dashboard/ApplicationTrendChart.tsx
frontend/src/components/dashboard/StatusDistributionChart.tsx
frontend/src/components/dashboard/ApplicationTypeChart.tsx
frontend/src/components/dashboard/AnomalyChart.tsx
frontend/src/styles/application-management.css
frontend/src/test/setup.ts
frontend/src/auth/RequireRole.test.tsx
frontend/src/components/applications/OfficerDecisionDialog.test.tsx
frontend/src/pages/officer/OfficerDashboardPage.test.tsx
frontend/src/pages/officer/ApplicationListPage.test.tsx
frontend/src/pages/officer/ApplicationDetailPage.test.tsx
```

Recommended dependencies when their phases start (none are installed today):
`react-router-dom`, `@tanstack/react-query`, `recharts`, and Testing Library
packages. Lazy-load officer pages/charts so citizen routes do not pay the
dashboard bundle cost. A headless dialog primitive (or a small, tested local
primitive) is required for focus trap/Escape/restoration behavior.

## 7. Database migration strategy

1. **Freeze the baseline first.** `0001_persistence_baseline.py` currently
   calls dynamic `Base.metadata.create_all()` and `drop_all()`. Once new ORM
   classes are imported, a fresh database could receive future tables from
   0001 and then collide at 0002; downgrade can also drop tables it did not
   create. Replace 0001 with explicit operations for its current eight tables
   and reverse-order explicit downgrade before introducing new metadata.
2. **Use an additive, SQLite-compatible 0002.** Add nullable/backfillable
   classification and processing timestamps to `application_cases`; add only
   necessary template/text/processing fields to `case_documents`. Use
   `op.batch_alter_table` for SQLite. Preserve existing rows and lower-case
   statuses; do not rename or delete `cases`/`case_messages`.
3. **Persist the current in-memory review data.** Add ORM tables for extracted
   field records, validation findings, finding decisions, supplement requests,
   and an append-only case-level decision. Reuse `case_audit_events` for the
   plan's application events and `notification_events` for return
   notifications. Add organization/status/date, finding, and audit indexes.
   Use VARCHAR/JSON and application validation rather than native PostgreSQL
   enums for SQLite/PostgreSQL parity.
4. **Backfill safely.** Derive type/classification from existing
   `procedure_id` and catalog version; do not duplicate mutable procedure
   names unless an explicitly named historical snapshot is required. Map
   existing statuses at the service/API boundary; do not rewrite history in
   the first migration.
5. **Make decisions atomic.** Expected-version checking/row locking must
   commit case status, case decision, finding updates, audit event, and
   notification in one transaction. Add idempotency protection for repeated
   dialog submission and return HTTP 409 on stale/illegal transitions.
6. **Stop runtime schema mutation and automatic demo data.** Remove production
   `create_all` from `src/main.py` and `OfficerStore`; run Alembic explicitly.
   Existing unversioned databases need an operator-reviewed backup/schema
   check before stamping 0001. Keep test-only schema helpers if needed.
7. **Verify both engines.** Test fresh SQLite upgrade, populated-baseline
   SQLite upgrade with row preservation, downgrade/upgrade round trip, and
   PostgreSQL upgrade in CI/container. The current shell lacks an `alembic`
   executable, so migration execution was not claimed as validated here.

## 8. Mapping the supplied UI reference to this design system

| Reference element | Existing system to reuse | Required adaptation |
|---|---|---|
| Sidebar and officer navigation | Existing `Shell`/topbar only; Lucide installed | Add an officer-only `OfficerLayout` with a sidebar/drawer. Do not alter citizen/login shell. Hide or permission-guard reference items with no API (reports/config/users). |
| Blue/green/amber/red/info palette | `--blue`, `--navy-2`, `--green`, `--teal`, `--gold`, `--red`, `--line`, `--paper`, `--muted` | Add semantic aliases and subtle backgrounds; retain the established navy/blue brand instead of copying reference hex values. Every status gets text/icon as well as color. |
| Inter, 12–24px hierarchy | Existing Inter-first stack and page headings | Keep Vietnamese-safe stack; scope sans-serif operational headings to officer pages. Avoid current officer sub-10px styles for new screens. |
| KPI cards | Existing `Dashboard`/`.dashboard-card` | Expand API-backed metrics; no fake period deltas. Reuse card borders/shadows and add loading/empty/error states. |
| Trend/donut/bar charts | No existing chart library | Add `recharts` in dashboard phase; provide Vietnamese legends, zero-filled periods, responsive sizing, textual summaries, and API data only. |
| Application table | Existing queue search/filter/list and `Status`/`Empty` | Extract into a route-backed table with server filters/pagination; use stacked mobile cards rather than default horizontal overflow. |
| Detail header/tabs/right caution rail | Existing `ReviewWorkspace`, `EvidencePanel`, `DataPanel`, `FindingsPanel`, timeline | Recompose existing behavior into tabs and a policy-aware DTO. Keep document viewer/OCR bounding boxes and finding actions. Do not expose raw prompts or unmasked data. |
| Continue/return dialogs | Existing decision box, finding selector, textarea, alerts, disabled buttons | Add a tested accessible dialog, mandatory reason/minimum length, selected-anomaly validation, duplicate-submit prevention, focus restoration, toast, and 409 handling. “Return” should reuse supplement/notification semantics. |
| Responsive behavior | Existing 1250/1000/760/440px breakpoints and stacked review layout | Preserve citizen breakpoints; create officer-specific grid/sidebar/table rules and verify 1440/1280, 768–1024, and 320–430px. |

## 9. Risks, compatibility concerns, and plan deviations

1. **Two case stores:** legacy raw SQLite guidance and SQLAlchemy officer
   workflow share configuration but not tables/contracts. A third application
   model would make this worse; use `ApplicationCase` as the management
   aggregate and bridge at submission.
2. **Partial durability:** `OfficerStore` is in-memory-first and
   `PERSISTENCE_ENABLED=false` by default. Findings, edited fields, decisions,
   supplements, consents, idempotency results, and metrics are lost or not
   reloaded across restart. This is a release blocker for audit guarantees.
3. **Dynamic Alembic baseline:** the 0001 `create_all/drop_all` pattern must be
   frozen before 0002, otherwise fresh installs and downgrades are unsafe.
4. **Status semantics:** plan states and UI words differ from the PRD's
   pre-check statuses. Preserve stored names and explicitly distinguish
   `precheck_ready` from official approval.
5. **Case-level vs finding-level decisions:** existing `OfficerDecision` cannot
   represent “continue with multiple verified anomalies”; add a separate
   case-decision record without breaking finding contracts.
6. **No local user directory:** demo credentials are hard-coded identities;
   production OIDC is validation-only. Do not promise admin/user management
   screens or foreign-key users in this phase.
7. **Security surface:** `/ops/*`, `/documents/*`, `/validation/check`, and
   legacy `/cases/*` are not all officer-authenticated. They must not become
   the new officer surface without explicit authorization review.
8. **API/UI naming:** existing `/officer/cases` and `Case*` contracts are
   already used by tests and the citizen flow. New `/applications` endpoints
   should be additive aliases/adapters, not a breaking rename.
9. **Frontend routing:** nested paths can 404 on direct load under current
   `StaticFiles` mounts. Add an SPA fallback or deliberately choose hash
   routing before linking to deep routes.
10. **Frontend scale:** `main.tsx` and `styles.css` are monoliths (636/708
    lines), with global CSS, manual state, no charts, no dialog primitive, no
    query cache, and only utility tests. Extract feature files and scope styles
    to avoid regressions.
11. **Reference scope exceeds APIs:** export, reports, configuration, and user
    management in the mockup have no current backend support. Omit/guard them;
    do not render dead navigation or fake metrics.
12. **Plan-file/doc drift:** requested `application-management-plan.md`,
    `DESIGN.md`, and `REPO_GUIDELINE.md` are missing; actual inputs are the
    `-uiux.md` plan and existing architecture/PRD. This audit records the
    deviation rather than creating aliases.

## 10. Safe validation performed

- Read-only file inventory and content inspection with `rg`, PowerShell
  `Get-Content`, and `Get-ChildItem`.
- Inspected the reference PNG at original resolution.
- Inspected git status before and after: the only pre-existing untracked inputs
  are `docs/ui/` and `planning/application-management-plan-uiux.md`.
- Confirmed ORM metadata contains the existing eight SQLAlchemy tables.
- No application code, migration, seed, frontend, or test files were changed
  in this Phase 1 audit.
- Alembic commands were not run because the `alembic` executable is not
  available on PATH in this shell; no migration pass is claimed.
