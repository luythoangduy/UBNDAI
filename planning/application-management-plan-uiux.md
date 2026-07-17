# Implementation Plan: AI-Assisted Administrative Application Management

## 0. Working Rules for Codex

Before changing code:

1. Read `AGENTS.md`, `ARCHITECTURE.md`, `DESIGN.md`, `REPO_GUIDELINE.md`, `README.md`, and all repository-specific instruction files.
2. Audit the real repository structure. Do not assume the paths in this plan exactly match the codebase.
3. Reuse existing authentication, upload, document parsing, review, activity/history, metrics, API client, layout, and design-system code.
4. Do not rewrite unrelated Chat/RAG/Legal Review functionality.
5. Implement phase by phase. After each phase:
   - summarize changed files;
   - run relevant tests;
   - report remaining failures;
   - do not proceed while the current phase is failing.
6. Do not disable existing tests, bypass types, hardcode mock data in production code, or commit secrets.
7. Backend authorization is mandatory. Hiding a frontend button is not authorization.
8. All status transitions and officer decisions must be auditable.
9. Deterministic validation belongs in backend rules. LLM output is advisory unless confirmed by deterministic logic or a human officer.
10. Keep compatibility with the databases and deployment workflow already used by the repository.

---

# 1. Product Objective

Extend the current system into an officer-facing administrative application management workflow with these capabilities:

1. Automatically identify and tag the type of application/form.
2. Detect anomalies:
   - wrong template;
   - missing required information;
   - missing required documents;
   - invalid field formats;
   - conflicting information;
   - unreadable documents;
   - low-confidence classification;
   - possible duplicates.
3. Show a clear caution state to officers.
4. Give officers exactly two primary actions for a caution application:
   - continue processing with a mandatory reason;
   - return the application to the citizen with selected issues and an editable message.
5. Provide an officer dashboard showing:
   - unique users;
   - total applications;
   - processed, in-process, pending, returned, and caution applications;
   - daily, monthly, and yearly trends;
   - application-type distribution;
   - anomaly distribution.
6. Deliver a polished, modern, accessible UI matching the supplied visual reference.

End-to-end target:

```text
Citizen submits application
→ documents are parsed
→ application type is tagged
→ rules and AI assistance detect anomalies
→ officer reviews caution
→ officer continues or returns
→ action is audited
→ dashboard metrics update
```

---

# 2. Visual Reference

The repository should contain the provided UI mockup at:

```text
docs/ui/application-management-reference.png
```

Codex must inspect this image before implementing frontend screens.

Treat the image as a visual direction, not as a pixel-perfect screenshot to copy. Preserve the repository's existing brand identity where it is already established.

If the image is missing, use the written design system in this plan as the source of truth.

The reference covers:

1. Officer overview dashboard.
2. Application list.
3. Application detail and anomaly review.
4. “Continue processing” dialog.
5. “Return to citizen” dialog.
6. Sidebar navigation and UI tokens.

---

# 3. UI/UX Quality Bar

The frontend is not considered complete merely because the data is visible.

Required qualities:

- professional government/enterprise appearance;
- clear visual hierarchy;
- calm and trustworthy tone;
- responsive from desktop to mobile;
- accessible keyboard navigation;
- readable status and risk indicators;
- polished loading, empty, error, disabled, hover, focus, and success states;
- consistent spacing, typography, borders, radii, icons, and colors;
- no giant empty areas;
- no cramped data tables;
- no decorative effects that reduce readability;
- no hardcoded layout that only works at one screen size;
- no raw JSON shown to officers;
- no generic browser confirmation dialogs.

Codex must prioritize clarity and workflow safety over visual novelty.

---

# 4. Design System

## 4.1 Design Tokens

First inspect the existing design system. Reuse existing CSS variables/Tailwind tokens where possible.

If equivalent tokens do not exist, define semantic tokens rather than scattering hex values:

```text
--color-primary
--color-primary-hover
--color-primary-subtle
--color-success
--color-success-subtle
--color-warning
--color-warning-subtle
--color-danger
--color-danger-subtle
--color-info
--color-info-subtle
--color-surface
--color-surface-muted
--color-border
--color-text
--color-text-muted
```

Visual direction from the reference:

```text
Primary: blue
Secondary/success: green/teal
Warning: amber
Danger: red
Info: light blue
Neutral text: slate
Page background: very light blue-gray
Cards: white
```

Do not use color as the only indication of status. Pair every status color with text and/or an icon.

## 4.2 Typography

Use the repository's current font. If no intentional font exists, prefer a Vietnamese-compatible sans-serif such as Inter.

Suggested hierarchy:

```text
Page title: 24px, semibold/bold
Section title: 18–20px, semibold
Card metric: 24–30px, semibold
Body: 14–16px, regular
Secondary/caption: 12–14px
Table header: 12–13px, medium
```

Avoid excessive bold text.

## 4.3 Spacing and Shape

Use a consistent 4px or 8px spacing scale.

Suggested values:

```text
Page padding desktop: 24px
Page padding tablet: 16px
Page padding mobile: 12px
Card padding: 16–20px
Card radius: 12–16px
Input/button radius: 8–10px
Gap between sections: 20–24px
```

Use restrained shadows. Prefer borders plus subtle elevation.

## 4.4 Icons

Use the icon library already installed. If none exists, add one lightweight icon library consistent with the frontend stack.

Requirements:

- outline icons;
- consistent 18–20px size;
- visible labels for important actions;
- icons must not replace text for destructive or workflow actions.

---

# 5. Information Architecture

Use one React application with role-protected routes unless the repository architecture strongly requires otherwise.

Officer routes:

```text
/officer/dashboard
/officer/applications
/officer/applications/:applicationId
/officer/alerts
/officer/history
```

Suggested sidebar:

```text
Tổng quan
Hồ sơ
Cảnh báo
Lịch sử xử lý
Báo cáo
Cấu hình
Quản lý người dùng
```

Do not implement empty navigation items without a useful placeholder or permission guard. For MVP, hide out-of-scope items or mark them as “Sắp có” only if that pattern already exists.

Citizen-facing routes must remain isolated through role guards.

---

# 6. Repository Audit Phase

Create:

```text
planning/application-management-audit.md
```

The audit must identify:

1. Backend application layout.
2. Existing models and migrations.
3. Existing user/role model.
4. Existing upload and document extraction flow.
5. Existing document guardrails and review services.
6. Existing activity/history/metrics modules.
7. Existing API routing and error conventions.
8. Existing frontend routing.
9. Existing API client and state/query library.
10. Existing component library and design tokens.
11. Existing chart library.
12. Existing test setup.
13. Exact files to reuse.
14. Exact files to modify.
15. Exact new files required.
16. Differences between this plan and the real repository.
17. Risks and backward-compatibility concerns.

Do not begin feature implementation before completing this audit.

---

# 7. Domain Model

## 7.1 Application

Fields:

```text
id
application_code
citizen_id
application_type_code
application_type_name
classification_confidence
classification_method
status
assigned_officer_id
submitted_at
processing_started_at
processed_at
returned_at
created_at
updated_at
```

Rules:

- `application_code` is unique.
- confidence is between 0 and 1.
- status is an enum.
- citizen and officer references use existing user entities where possible.

## 7.2 Application Document

Fields:

```text
id
application_id
document_type
file_name
storage_path
mime_type
extracted_text
template_code
template_version
processing_status
created_at
updated_at
```

Reuse existing document/file storage models if appropriate. Do not duplicate binary storage logic.

## 7.3 Application Anomaly

Fields:

```text
id
application_id
document_id
code
field_name
message
severity
confidence
detected_by
status
evidence
resolution_note
resolved_by
resolved_at
created_at
```

Codes:

```text
WRONG_TEMPLATE
MISSING_REQUIRED_FIELD
MISSING_REQUIRED_DOCUMENT
INVALID_FIELD_FORMAT
CONFLICTING_INFORMATION
UNREADABLE_DOCUMENT
LOW_CLASSIFICATION_CONFIDENCE
POSSIBLE_DUPLICATE
```

Severity:

```text
INFO
WARNING
CRITICAL
```

Status:

```text
OPEN
ACKNOWLEDGED
RESOLVED
IGNORED
```

## 7.4 Application Decision

Fields:

```text
id
application_id
officer_id
decision
note
previous_status
new_status
selected_anomaly_ids
citizen_message
created_at
```

Decisions:

```text
CONTINUE_PROCESSING
RETURN_TO_CITIZEN
MARK_COMPLETED
REOPEN
```

## 7.5 Application Event

Fields:

```text
id
application_id
event_type
actor_type
actor_id
metadata_json
created_at
```

Events:

```text
APPLICATION_SUBMITTED
CLASSIFICATION_STARTED
CLASSIFICATION_COMPLETED
ANOMALY_SCAN_STARTED
ANOMALY_DETECTED
ANOMALY_SCAN_COMPLETED
OFFICER_ASSIGNED
PROCESSING_STARTED
OFFICER_CONTINUED_WITH_WARNING
RETURNED_TO_CITIZEN
CITIZEN_RESUBMITTED
APPLICATION_COMPLETED
```

This table is the source for audit history and may support analytics.

---

# 8. Application State Machine

Statuses:

```text
DRAFT
SUBMITTED
AI_ANALYZING
READY_FOR_PROCESSING
CAUTION_REVIEW_REQUIRED
IN_PROCESS
RETURNED_TO_CITIZEN
RESUBMITTED
COMPLETED
REJECTED
```

Allowed transitions:

```text
DRAFT → SUBMITTED
SUBMITTED → AI_ANALYZING

AI_ANALYZING → READY_FOR_PROCESSING
AI_ANALYZING → CAUTION_REVIEW_REQUIRED

READY_FOR_PROCESSING → IN_PROCESS

CAUTION_REVIEW_REQUIRED → IN_PROCESS
CAUTION_REVIEW_REQUIRED → RETURNED_TO_CITIZEN

RETURNED_TO_CITIZEN → RESUBMITTED
RESUBMITTED → AI_ANALYZING

IN_PROCESS → COMPLETED
IN_PROCESS → RETURNED_TO_CITIZEN
```

Requirements:

- implement a backend transition service;
- frontend cannot set arbitrary status;
- invalid transitions return HTTP 409;
- every transition creates an event;
- caution applications require an officer decision before `IN_PROCESS`.

---

# 9. Procedure Catalog and Application Tagging

Create a versioned procedure catalog, initially JSON/YAML if that best matches the repository.

Example:

```json
{
  "code": "BIRTH_REGISTRATION",
  "name": "Đăng ký khai sinh",
  "keywords": [
    "khai sinh",
    "giấy chứng sinh",
    "thông tin người được khai sinh"
  ],
  "required_fields": [
    "applicant_name",
    "citizen_id",
    "child_name",
    "child_date_of_birth"
  ],
  "required_documents": [
    "APPLICATION_FORM",
    "BIRTH_CERTIFICATE"
  ],
  "accepted_template_codes": [
    "KS-01"
  ]
}
```

Demo categories:

```text
BIRTH_REGISTRATION
MARRIAGE_REGISTRATION
RESIDENCE_CONFIRMATION
BUSINESS_REGISTRATION
UNKNOWN
```

Classification flow:

```text
Extracted text
→ deterministic rules/keywords
→ LLM structured fallback when confidence is low
→ confidence threshold
→ persist type, method, evidence
```

Output:

```json
{
  "application_type_code": "BIRTH_REGISTRATION",
  "application_type_name": "Đăng ký khai sinh",
  "confidence": 0.94,
  "method": "rule_llm_hybrid",
  "evidence": [
    "Tờ khai đăng ký khai sinh",
    "Thông tin người được khai sinh"
  ],
  "needs_manual_review": false
}
```

Rules:

- unknown category must return `UNKNOWN`;
- low confidence creates `LOW_CLASSIFICATION_CONFIDENCE`;
- store no private chain-of-thought;
- store concise evidence only;
- classification must be visible as a tag in list and detail screens.

---

# 10. Anomaly Detection

Pipeline:

```text
Upload
→ text extraction
→ application classification
→ load checklist
→ required-document validation
→ template validation
→ structured field extraction
→ required-field validation
→ format validation
→ cross-document consistency validation
→ persist anomalies
→ derive application status
```

Validators:

```text
RequiredDocumentValidator
RequiredFieldValidator
FieldFormatValidator
TemplateValidator
CrossDocumentConsistencyValidator
ReadabilityValidator
DuplicateValidator
```

Common result schema:

```json
{
  "code": "MISSING_REQUIRED_FIELD",
  "field_name": "citizen_id",
  "message": "Không tìm thấy số CCCD của người nộp.",
  "severity": "WARNING",
  "confidence": 1.0,
  "detected_by": "rule",
  "evidence": "Trường citizen_id không được trích xuất."
}
```

MVP deterministic rules:

- citizen ID must contain exactly 12 digits;
- required strings cannot be null, empty, or whitespace;
- dates must parse and be real dates;
- date of birth cannot be in the future;
- uploaded document types must satisfy the procedure checklist;
- template code/version must be accepted;
- required headings must exist;
- compare applicant name, citizen ID, and date of birth across documents.

LLM may assist with:

- unstructured field extraction;
- possible semantic conflicts;
- wrong-content hints;
- officer/citizen-friendly explanations.

LLM-generated anomalies:

- must have confidence and evidence;
- use `detected_by = "llm"`;
- cannot automatically reject an application;
- appear as officer-review cautions.

Final status:

```text
No warning/critical anomaly → READY_FOR_PROCESSING
At least one warning/critical anomaly → CAUTION_REVIEW_REQUIRED
```

---

# 11. Backend APIs

Applications:

```http
POST /api/v1/applications
GET /api/v1/applications
GET /api/v1/applications/{application_id}
PATCH /api/v1/applications/{application_id}/assignment
POST /api/v1/applications/{application_id}/documents
POST /api/v1/applications/{application_id}/analyze
POST /api/v1/applications/{application_id}/decisions
POST /api/v1/applications/{application_id}/resubmit
GET /api/v1/applications/{application_id}/events
```

Application list filters:

```text
status
application_type_code
has_anomaly
severity
assigned_officer_id
submitted_from
submitted_to
search
page
page_size
sort_by
sort_order
```

Dashboard:

```http
GET /api/v1/officer-dashboard/summary
GET /api/v1/officer-dashboard/timeseries
GET /api/v1/officer-dashboard/status-distribution
GET /api/v1/officer-dashboard/application-types
GET /api/v1/officer-dashboard/anomalies
```

Dashboard filters:

```text
from
to
timezone
granularity=day|month|year
```

All new endpoints require typed request/response schemas, validation, authorization, consistent errors, and tests.

---

# 12. Officer Dashboard UX

Route:

```text
/officer/dashboard
```

## 12.1 Page Header

Show:

- title: `Tổng quan`;
- subtitle: `Thống kê tình hình xử lý hồ sơ`;
- period preset;
- from/to date range;
- export button only if export is implemented; otherwise omit it.

Filters should remain compact and responsive.

## 12.2 KPI Cards

Display:

```text
Người sử dụng
Tổng hồ sơ
Đã xử lý
Đang xử lý
Chưa xử lý
Hồ sơ có cảnh báo
Bị trả lại
Tỷ lệ hoàn thành
```

Each card should include:

- small icon;
- label;
- primary value;
- optional comparison with previous equivalent period;
- semantic status indication;
- tooltip explaining the metric.

Do not show fake period comparison if the API does not return it.

## 12.3 Charts

Minimum charts:

1. Trend line chart:
   - submitted;
   - processed;
   - pending;
   - period grouped by day/month/year.

2. Status donut chart:
   - completed;
   - in process;
   - pending;
   - returned;
   - caution.

3. Application-type horizontal bar chart.

4. Anomaly-type horizontal bar chart.

Requirements:

- charts resize without overflow;
- tooltips show exact values;
- legends use Vietnamese labels;
- axis labels remain readable;
- no rainbow palette;
- loading skeleton;
- empty state;
- error state with retry;
- chart data comes from API;
- missing periods appear with zero values.

## 12.4 Metric Definitions

```text
unique_users:
distinct citizen_id values that submitted within the period

total_applications:
applications submitted within the period

processed_applications:
applications with status COMPLETED

in_process_applications:
applications with status IN_PROCESS

pending_applications:
applications not completed, rejected, or returned

applications_with_caution:
applications with at least one warning/critical anomaly

returned_applications:
applications that entered RETURNED_TO_CITIZEN

completion_rate:
processed / total × 100
```

Do not count applications as users.

---

# 13. Application List UX

Route:

```text
/officer/applications
```

## 13.1 Filters

Show a responsive filter bar:

- text search;
- status;
- application type;
- has anomaly;
- date range;
- officer;
- clear/reset filters.

Reflect filters in URL search params where practical.

## 13.2 Table

Columns:

```text
Mã hồ sơ
Công dân
Loại thủ tục
Độ tin cậy AI
Cảnh báo
Trạng thái
Cán bộ phụ trách
Ngày nộp
Thao tác
```

Requirements:

- application code is a clear link;
- type shown as a compact tag;
- confidence shown as percent plus accessible label;
- anomaly shown as status badge and count;
- status uses text, icon, and color;
- row action menu uses a real button with an accessible label;
- pagination and page-size control;
- sortable only on backend-supported fields;
- table remains usable on tablet;
- on mobile, use stacked cards or a deliberately reduced table, not horizontal overflow as the default.

States:

- skeleton rows while loading;
- empty result with “Xóa bộ lọc” action;
- error state with retry;
- no-data state distinct from filtered-empty state.

---

# 14. Application Detail and Caution UX

Route:

```text
/officer/applications/:applicationId
```

## 14.1 Header

Show:

- breadcrumb;
- application code;
- caution badge if applicable;
- application type;
- AI confidence;
- current status;
- history button;
- action menu.

Keep the most important workflow information above the fold.

## 14.2 Tabs

Suggested tabs:

```text
Thông tin chung
Tài liệu
Thông tin trích xuất
Cảnh báo
Lịch sử
```

Deep-link the active tab through URL state if the router supports it.

## 14.3 Main Layout

Desktop:

- left/main area for application information;
- right rail for anomaly summary and actions.

Tablet/mobile:

- stack sections;
- action panel remains visible near the anomaly section;
- no fixed panel that covers content.

## 14.4 Caution Panel

Show:

- total number of anomalies;
- Critical/Warning/Info counts;
- anomaly title;
- affected field/document;
- date detected;
- evidence;
- source: rule or AI;
- current anomaly status.

Severity styling must be accessible and not depend solely on color.

## 14.5 Extracted Information

Render extracted fields as readable label/value rows.

Allow officers to see source/evidence when available. Do not expose raw model prompts or chain-of-thought.

---

# 15. Officer Decision UX

When status is `CAUTION_REVIEW_REQUIRED`, present two clearly separated primary workflow choices:

```text
Vẫn tiếp tục xử lý
Trả lại cho công dân
```

These are not generic action-menu items. They must appear clearly near the caution information.

## 15.1 Continue Processing Dialog

Title:

```text
Vẫn tiếp tục xử lý hồ sơ
```

Content:

- warning that the application contains cautions;
- mandatory reason textarea;
- checkbox list of anomalies manually verified;
- character count;
- cancel button;
- confirm button.

Rules:

- reason is required;
- minimum 10 characters;
- show inline validation;
- disable confirm during submission;
- prevent accidental duplicate submission;
- after success, close dialog, refresh detail/timeline, show toast;
- focus returns to the trigger button;
- destructive styling is not appropriate; use primary blue.

Request:

```json
{
  "decision": "CONTINUE_PROCESSING",
  "note": "Đã đối chiếu CCCD bản giấy trực tiếp tại quầy.",
  "anomaly_ids": [
    "anomaly-id-1"
  ]
}
```

Backend effects:

- selected anomalies become acknowledged/ignored according to domain rules;
- status becomes `IN_PROCESS`;
- decision and event are recorded.

## 15.2 Return to Citizen Dialog

Title:

```text
Trả lại hồ sơ cho công dân
```

Content:

- warning explaining the action;
- checkbox list of anomalies;
- citizen message textarea;
- optional “Tạo nội dung từ cảnh báo” action;
- editable generated message;
- character count;
- cancel button;
- red/destructive submit button.

Rules:

- at least one anomaly is selected;
- citizen message is required;
- show inline validation;
- confirmation must state that the application is not deleted;
- prevent duplicate submit;
- success toast and timeline refresh.

Request:

```json
{
  "decision": "RETURN_TO_CITIZEN",
  "anomaly_ids": [
    "anomaly-id-1",
    "anomaly-id-2"
  ],
  "citizen_message": "Vui lòng bổ sung số CCCD và sử dụng đúng biểu mẫu."
}
```

Backend effects:

- status becomes `RETURNED_TO_CITIZEN`;
- decision, event, and notification record are created.

Do not integrate real email/SMS in MVP unless the repository already provides it. Use an adapter/interface.

---

# 16. Resubmission UX

Citizen flow:

```text
RETURNED_TO_CITIZEN
→ upload corrected/new documents
→ RESUBMITTED
→ AI_ANALYZING
```

Requirements:

- clearly show return reasons to the citizen;
- preserve old document versions and events;
- do not delete old anomalies;
- mark resolved anomalies when new data passes validation;
- rerun classification and validation;
- show current review status.

---

# 17. Responsive and Accessibility Requirements

Codex must manually verify:

## Desktop

- 1440px and 1280px layouts;
- sidebar and dense dashboard remain readable;
- detail two-column layout works.

## Tablet

- 768–1024px;
- filters wrap cleanly;
- KPI cards use 2–4 columns depending on width;
- detail right rail stacks when needed.

## Mobile

- 320–430px;
- sidebar becomes drawer or existing mobile navigation;
- application list becomes card list or reduced table;
- dialogs fit viewport without clipped controls;
- primary actions remain reachable.

Accessibility:

- keyboard navigation;
- visible focus state;
- semantic headings;
- correct labels for inputs;
- dialog focus trap and Escape behavior through the existing component system;
- status text in addition to color;
- icon-only buttons have accessible names;
- minimum practical touch target around 40–44px;
- reasonable contrast;
- respect reduced-motion preference;
- charts include textual summaries or accessible labels.

---

# 18. Frontend Component Plan

Adapt names to the actual repository.

Expected pages:

```text
frontend/src/pages/officer/OfficerDashboardPage.tsx
frontend/src/pages/officer/ApplicationListPage.tsx
frontend/src/pages/officer/ApplicationDetailPage.tsx
```

Expected shared components:

```text
frontend/src/components/applications/ApplicationTypeTag.tsx
frontend/src/components/applications/ApplicationStatusBadge.tsx
frontend/src/components/applications/ConfidenceIndicator.tsx
frontend/src/components/applications/AnomalyAlert.tsx
frontend/src/components/applications/AnomalyList.tsx
frontend/src/components/applications/OfficerDecisionDialog.tsx
frontend/src/components/applications/ApplicationTimeline.tsx
frontend/src/components/applications/ExtractedFieldsPanel.tsx

frontend/src/components/dashboard/DashboardFilters.tsx
frontend/src/components/dashboard/DashboardSummaryCards.tsx
frontend/src/components/dashboard/ApplicationTrendChart.tsx
frontend/src/components/dashboard/StatusDistributionChart.tsx
frontend/src/components/dashboard/ApplicationTypeChart.tsx
frontend/src/components/dashboard/AnomalyChart.tsx
```

Create reusable primitives only when the repository does not already have equivalents.

Do not create one giant dashboard component or one giant application-detail component.

---

# 19. Authorization

Roles:

```text
CITIZEN
OFFICER
ADMIN
```

Citizen:

- create and view own applications;
- upload/resubmit documents;
- view return reasons;
- cannot access officer dashboard or officer decisions.

Officer:

- view permitted applications;
- review anomalies;
- continue processing;
- return applications;
- view officer dashboard.

Admin:

- officer permissions;
- broader reporting/configuration as supported.

Backend must enforce permissions and ownership.

Expected responses:

- unauthenticated: 401;
- authenticated without permission: 403;
- illegal transition: 409;
- validation errors: 422 or repository-standard equivalent.

---

# 20. Migrations and Seed Data

Create Alembic migrations for new entities/enums.

Requirements:

- no destructive changes to existing tables;
- upgrade succeeds;
- downgrade is valid;
- SQLite local support;
- PostgreSQL support where configured.

Create:

```text
scripts/seed_application_demo_data.py
```

Seed:

- 20 citizens;
- 2 officers;
- 80–120 applications;
- at least 6 months of dates;
- multiple procedure types;
- multiple statuses;
- clean and caution applications;
- returned and completed applications;
- useful trend variation for charts.

Seed should be idempotent or have an explicit reset option.

The dashboard must use database data, not frontend fixtures.

---

# 21. Testing

Backend unit tests:

- classifier;
- confidence threshold;
- required fields;
- citizen ID validation;
- document checklist;
- template validation;
- cross-document consistency;
- state transitions;
- metric calculations;
- day/month/year grouping;
- zero-filled periods.

API tests:

- citizen submission;
- officer list/detail access;
- citizen denied dashboard;
- continue requires a reason;
- return requires selected anomalies and a message;
- invalid transition returns 409;
- audit events are created;
- dashboard date filters;
- dashboard grouping;
- pagination/filter combinations.

Frontend tests if the repository already supports them:

- dashboard cards and filters;
- caution panel;
- continue dialog validation;
- return dialog validation;
- route guards;
- loading/error/empty states.

Visual/manual QA:

- compare screens with `docs/ui/application-management-reference.png`;
- desktop/tablet/mobile;
- keyboard navigation;
- long Vietnamese labels;
- 0, 1, and many anomalies;
- very long citizen message;
- API error during decision submission;
- empty dashboard periods;
- dark mode only if the existing application supports it.

Regression:

- existing auth;
- chat;
- RAG;
- current document review;
- organization/library flows;
- build and lint.

---

# 22. UI Acceptance Criteria

The UI phase is complete only when:

- the visual reference has been reviewed;
- dashboard hierarchy resembles the reference;
- application list is polished and filterable;
- application detail clearly presents type, confidence, status, anomalies, extracted data, and actions;
- the two caution decisions are unmistakable;
- dialogs have inline validation and safe submit states;
- loading, empty, error, and success states exist;
- no production component relies on hardcoded dashboard data;
- responsive behavior is verified;
- accessibility basics are verified;
- all text is natural Vietnamese;
- there are no obvious spacing, overflow, truncation, contrast, or inconsistent-component issues.

Codex must take screenshots of the implemented desktop screens if screenshot tooling is available and record visual differences in:

```text
planning/application-management-ui-review.md
```

Include:

- implemented screens;
- deviations from the reference;
- reasons for intentional deviations;
- responsive checks;
- accessibility checks;
- remaining polish items.

---

# 23. Functional Acceptance Criteria

Tagging:

- every analyzed application has a type or `UNKNOWN`;
- list/detail show type;
- confidence and method are persisted;
- low confidence creates caution.

Anomalies:

- missing required field is detected;
- invalid citizen ID is detected;
- missing document is detected;
- wrong template is detected;
- anomalies persist;
- application status becomes caution when appropriate.

Officer workflow:

- continue requires a reason;
- return requires selected issues and a message;
- actions are authorized;
- status transitions are valid;
- decision and events are recorded;
- timeline updates.

Dashboard:

- unique users is distinct citizens, not application count;
- summary metrics are correct;
- day/month/year work;
- trend, status, type, and anomaly charts work;
- zero periods are returned;
- filters affect all dashboard widgets consistently.

Quality:

- migrations pass;
- backend tests pass;
- existing tests pass;
- lint passes;
- frontend build passes;
- no secrets;
- no critical TODOs.

---

# 24. Implementation Phases

## Phase 1 — Repository Audit

Deliver:

```text
planning/application-management-audit.md
```

No feature implementation yet.

## Phase 2 — Design System and UI Foundation

- inspect visual reference;
- map reference tokens to existing design system;
- define missing semantic tokens;
- establish officer routes, layout, sidebar, page container;
- create status/tag primitives;
- implement static shells using API-shaped placeholder types only;
- no hardcoded production data source.

Deliver:

```text
planning/application-management-ui-spec.md
```

## Phase 3 — Database and State Machine

- entities;
- enums;
- migrations;
- transition service;
- events;
- tests.

## Phase 4 — Classification and Anomaly Pipeline

- catalog;
- classifier;
- validators;
- orchestration;
- persistence;
- tests.

## Phase 5 — Officer Application APIs

- list/detail;
- filters;
- assignment;
- decisions;
- resubmission;
- timeline;
- authorization;
- tests.

## Phase 6 — Application List and Detail UI

- real API integration;
- list filters/table/mobile cards;
- detail tabs;
- anomaly panels;
- extracted fields;
- timeline;
- loading/empty/error states.

## Phase 7 — Decision Dialogs

- continue flow;
- return flow;
- form validation;
- submission states;
- toasts;
- cache refresh;
- tests/manual QA.

## Phase 8 — Dashboard Backend

- summary;
- timeseries;
- distributions;
- filters;
- timezone/granularity;
- tests.

## Phase 9 — Dashboard Frontend

- KPI cards;
- filters;
- charts;
- comparison text only when API-supported;
- responsive behavior;
- accessibility;
- states.

## Phase 10 — Seed, Visual Review, Regression, Documentation

- seed data;
- screenshot/visual review;
- responsive QA;
- accessibility QA;
- tests/lint/build;
- README/API docs;
- known limitations.

---

# 25. Expected Files

Adapt paths to the actual repository.

Backend:

```text
src/models/application.py
src/models/application_document.py
src/models/application_anomaly.py
src/models/application_decision.py
src/models/application_event.py

src/schemas/application.py
src/schemas/application_anomaly.py
src/schemas/application_decision.py
src/schemas/officer_dashboard.py

src/services/application_classifier.py
src/services/application_analysis.py
src/services/application_state_machine.py
src/services/application_validation.py
src/services/officer_dashboard.py

src/api/v1/applications.py
src/api/v1/officer_dashboard.py

src/config/procedures.json
alembic/versions/<revision>_add_application_management.py
```

Frontend:

```text
frontend/src/pages/officer/OfficerDashboardPage.tsx
frontend/src/pages/officer/ApplicationListPage.tsx
frontend/src/pages/officer/ApplicationDetailPage.tsx

frontend/src/components/applications/*
frontend/src/components/dashboard/*
```

Planning/docs:

```text
planning/application-management-audit.md
planning/application-management-ui-spec.md
planning/application-management-ui-review.md
docs/ui/application-management-reference.png
```

Tests and seed:

```text
scripts/seed_application_demo_data.py
tests/test_application_classifier.py
tests/test_application_validation.py
tests/test_application_state_machine.py
tests/test_application_api.py
tests/test_officer_dashboard.py
```

Do not duplicate existing equivalent modules.

---

# 26. Final Verification

Use the repository's actual commands. Expected examples:

```bash
alembic upgrade head
alembic check

pytest tests/ -v --tb=short
ruff check .

cd frontend
npm install
npm run lint
npm run build
```

Smoke test:

```text
1. Citizen submits a birth-registration application.
2. System tags it as “Đăng ký khai sinh”.
3. A missing/invalid citizen ID creates a caution.
4. Officer sees the application in the list.
5. Officer opens detail and sees anomalies and extracted fields.
6. Officer continues processing with a reason.
7. Timeline and status update.
8. Another application is returned with selected issues.
9. Citizen sees the return message and resubmits.
10. Analysis reruns and old history remains.
11. Dashboard metrics and charts reflect the changes.
12. Screens match the intended visual quality on desktop, tablet, and mobile.
```

---

# 27. Definition of Done

The implementation is done when the complete workflow works with real persisted data:

```text
submission
→ type tagging
→ anomaly detection
→ officer caution review
→ continue or return
→ audit history
→ dashboard analytics
```

Final deliverables:

- backend code;
- frontend code;
- migrations;
- tests;
- seed data;
- visual reference integrated into repository documentation;
- UI specification;
- UI review report;
- API documentation;
- updated README;
- manual QA checklist;
- known limitations.
