# Application management UI specification

Phase 2 foundation for the officer-facing application workflow. This spec
keeps the existing citizen/chat/OCR/editor surfaces intact and scopes new
styles and routes to the officer application-management area.

## Routes

```text
/officer/dashboard
/officer/applications
/officer/applications/:applicationId
```

The existing `/officer` review workspace and `/officer/cases*` API remain
compatibility paths until the new list/detail screens reach parity. Browser
URLs are canonical history-based paths; the backend must serve the SPA index
for extensionless nested officer routes while continuing to return 404 for
missing assets.

## Reference mapping

| Reference | Existing system | Phase 2 decision |
|---|---|---|
| Blue primary / green success / amber warning / red danger | `--blue`, `--navy-2`, `--green`, `--teal`, `--gold`, `--red` in `frontend/src/styles.css` | Add semantic aliases under `.officer-app`; do not scatter new hex values or alter citizen styles. |
| Sidebar | Existing app has a shared topbar | Add officer-only sidebar/drawer. Keep citizen/login navigation unchanged. |
| KPI cards and charts | Existing `Dashboard` has cards; no chart library | Reuse card geometry; charts are API-backed in Phase 9 and use a restrained five-color palette. |
| Application list | Existing officer queue/search/filter | Add a table on desktop and cards on mobile; retain queue/review compatibility route. |
| Detail and caution rail | Existing `ReviewWorkspace`, evidence, data, findings, timeline panels | Recompose behind new application DTOs; never expose raw prompts, storage keys, or raw JSON. |
| Decision dialogs | Existing decision box and supplement form styles | Add one accessible controlled dialog with `continue` and `return` modes. |

## Semantic tokens

New styles must be nested under `.officer-app` and map to current brand tokens:

```text
--am-primary / --am-primary-hover / --am-primary-subtle
--am-success / --am-success-subtle
--am-warning / --am-warning-subtle
--am-danger / --am-danger-subtle
--am-info / --am-info-subtle
--am-surface / --am-surface-muted / --am-border
--am-text / --am-text-muted
```

Use the existing 4/8px spacing rhythm, 8px controls, 12–16px cards,
restrained border/shadow, 40–44px touch targets, visible focus, and
Vietnamese-safe sans-serif stack. Status always includes text and icon in
addition to color.

## Responsive and accessibility rules

- 1280px+: sidebar + two-column dashboard/detail grids.
- 768–1279px: compact sidebar, wrapping filters, stacked detail rail.
- 320–767px: drawer navigation, filter disclosure, mobile application cards,
  one-column dialogs/actions.
- Dialogs trap focus, close on Escape, restore trigger focus, announce errors,
  and disable submit during mutation.
- Charts include adjacent text/table summaries and respect reduced motion.

## Data boundaries

The UI consumes typed API-shaped data only. It does not contain production
fixtures, calculate dashboard metrics, infer authorization, or persist raw
citizen identifiers. Backend RBAC and organization scope remain authoritative.
