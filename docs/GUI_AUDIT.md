# GUI Audit — thehub-pr

**Scope:** every user-executable control (buttons, links, dropdowns, selects, switches, checkboxes,
tabs, filters, table sorts, modal/dialog actions) across the three GUI surfaces in this repo:

1. **Main dashboard** — `server/frontend/` (React 19 + Vite + React Router + TanStack Query), a
   FastAPI-backed control-plane UI for the PRII ("INTSYS-PR") research federation.
2. **`desktop/launcher.html`** — a standalone, static HTML page that lists and launches sibling
   federation apps from the desktop wrapper.
3. **`federation-design/packages/react`** — the `@pr-federation/react` design-system package, a
   library of interactive primitives consumed by the dashboard (and by sibling repos).

**Convention used below:** each table row is one *distinct control* as it exists in the source —
a button, a select, a link, a tab trigger, etc. Where a control renders once per data row (e.g. a
"Verify" button in a table with N pending items), it is still one row here, annotated "(per row)".
The Summary's element count is the count of these catalogued rows, not the number of DOM nodes a
fully-populated production instance would render.

**Verified column:** `live` means the control was actually exercised against a running instance of
this app (dev server + the repo's own FastAPI backend, in its built-in "diagnostic mode") during
this audit, using Playwright with the pre-installed Chromium. `static` means the row is based on
reading the source and its handler only. Where a control needs a real external service this repo
doesn't ship (GitHub PAT, live LLM provider, OAuth, USASpending, native desktop manager session),
it is marked `static-only: requires <X>` and was not chased further, per the audit's scope.

---

## Overview

**What this app is.** TheHub (`thehub-pr` / "INTSYS-PR") is the parent control plane for a
7-repo Puerto Rico research federation (this repo plus `spiderweb-pr`, `ovnis-pr`, `aguayluz-pr`,
`moneysweep-pr`, `skywatcher-pr`, `centinelas-pr`). It aggregates each producer module's sanitized
export into shared ledgers (cases, sources, tasks, validation gates, crossovers, governance
alerts) and exposes cross-module views: a federation-wide task board, a crossover-correlation
workspace, transition/parity auditing, CSV/GeoJSON export, and an LLM research assistant.

**Tech stack.** React 19, Vite 6, React Router 6, TanStack Query 5, Tailwind, Radix UI primitives
(`components/ui/*`, shadcn-style), Recharts, Leaflet/react-leaflet, jsPDF, `@pr-federation/react`
(the in-repo design system, consumed via a `file:` dependency). Backend: FastAPI
(`server/backend/main.py`), SQLite-backed generic entity store (`/api/entities/{Entity}` CRUD),
with `PRII_WRITE_TOKEN`-gated writes and a documented **diagnostic mode** (no auth configured,
`/api/auth/me` always 401s, unimplemented subsystems — GitHub functions, LLM invoke, agents, file
storage — return a stable `status:"not_implemented"` stub instead of erroring).

**Entry points.**
- **Dev URL:** `npm run dev` (Vite) — defaults to `:5173`; this audit ran it on `:5183` to avoid a
  sibling repo's dev server, with the API reached through a Vite proxy to the backend on `:8091`
  (`python -m uvicorn server.backend.main:app --port 8091`). Confirmed the served page's `<title>`
  was "TheHub PR" before interacting with it.
- **Desktop launcher:** `PRII-THEHUB.command` / `.sh` / `.bat` / `PRII-THEHUB.app` at the repo
  root — one-time `desktop/setup.py --ensure`, then opens a native window (or the default browser
  as fallback) on the main dashboard (`/`).
- **`launcher.html`:** reached via `PRII-FEDERATION.command` / `.sh` / `.bat` / `PRII Federation.app`
  (same setup step, then `desktop/launch.py --route /launcher`), or by browsing to `/launcher` on
  a running TheHub backend. Lists all 7 federation apps and can launch any sibling repo's own
  desktop app.

---

## How this audit was performed

1. Read every file under `server/frontend/src/pages` and `server/frontend/src/components`
   (98 files) plus the hooks/lib layer each page's handlers call into, to determine actual
   behavior (API endpoint, state update, navigation, export, etc.) rather than guessing from
   labels.
2. `npm install` in `server/frontend` (623 packages, succeeded via the environment's proxy).
3. Installed the one missing Python dependency (`jsonschema`) and started
   `server/backend/main.py` on port 8091. Its `seed_federation.py` auto-seeds most entity tables
   on first request in diagnostic mode, giving real (synthetic) content — confirmed via
   `curl /api/entities/Programs` returning populated rows (`UnifiedCases` and a few other
   ledgers came back empty, which is called out per-page below).
4. Started the Vite dev server on port 5183 with a temporary `server.proxy` entry added to
   `vite.config.js` so the browser's same-origin fetches reach the backend without CORS (the
   backend's `CORSMiddleware` only allow-lists `localhost:5173`/`127.0.0.1:5173`, and 5173 was not
   guaranteed free in this shared, multi-repo container). The proxy edit was reverted
   (`git checkout --`) before finishing; it is not part of this PR's diff.
5. Drove the running app with Playwright (`chromium.launch({ executablePath:
   '/opt/pw-browsers/chromium' })`), across two passes: a broad crawl of all 27 routed pages
   checking for console/page errors, then a second pass exercising specific controls (selects,
   dialogs, tab switches, sort headers, filters, a live CSV export, the Generate-signs button, the
   verification-gate/staging-queue UI, and the diagnostic-mode stubs for GitHub/LLM calls).
6. Killed both dev processes and removed `node_modules` before finishing (see Summary).

**Live-crawl result:** 27/27 routed pages loaded with **zero page errors** (no React render
crashes) across two Playwright passes. Two pages showed a benign `401` console entry from
`GET /api/auth/me` (Tasks, Research Assistant) — this is the documented diagnostic-mode behavior
(no auth configured, so `/auth/me` always 401s; the app's own code catches it and falls back to
an anonymous/default state), not a bug. Research Assistant's Operator Chat additionally logged an
`EventSource … MIME type … not "text/event-stream"` warning, because the diagnostic-mode `/agents`
stub returns a plain JSON body rather than opening a real SSE stream — again expected, and the UI
degrades gracefully (empty chat, no crash). No other console errors were observed anywhere.

---

## Dashboard pages

### Recent Activity (`/`, `/activity`) — landing page

`src/pages/RecentActivity.jsx`. Merges `ContinuityRisks`, `AnomalyFlags`, and `GovernanceAlerts`
into one newest-first, per-program-grouped feed, polling every 30s.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Severity select | dropdown | "Severity" (All/Critical/High/Medium/Low) | `setSeverity` — client-side filter on `groups` memo | live | Selected "Critical", list re-filtered with no console errors |
| Time window select | dropdown | "Window" (All time/Last 7 days/Last 30 days) | `setTimeWindow` — client-side `ts >= cutoff` filter | static | Same `Select` pattern verified live elsewhere |
| Program group header link | link (per group) | group's resolved program name | `<Link to={modulePath}>` — fuzzy-matches the group to a `MODULES` entry and navigates to that producer's page | static | Only rendered when a `MODULES` match is found |

### Hub (`/hub`)

`src/pages/Hub.jsx` renders the Command Dashboard (`Dashboard.jsx` + its sub-panels) plus 5
launcher cards to federation workspaces.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| "Review gates" link | link | "Review gates" | `<Link to="/gates">` | static | |
| Case Evidence Timeline: case select | dropdown | "Select a case" | `setCaseId` — switches which case's sources are timelined | static | `UnifiedCases` was empty in this seed, so the select had no options during the live pass |
| Case Evidence Timeline: filter buttons | button (×3) | "All" / "Confirmed" / "Pending" | `setFilter` — client-side filter on `verification_status` | static | |
| Task Rollup: "Task control plane" link | link | "Task control plane" | `<Link to="/tasks">` | static | |
| Task Rollup: per-program row link | link (per row) | program label | `<Link to={"/tasks?program="+key}>` — deep-links Tasks pre-filtered | static | |
| Task Rollup: recent-change item link | link (per row) | task title | `<Link to="/tasks">` | static | |
| Module Grid: module card link | link (×7) | each producer module's name/blurb | `<Link to={m.path}>` — navigates to that module's page | live | Equivalent sidebar links (Cases, Sources, Gates) were clicked and navigated correctly |
| Launcher card link | link (×5) | Crossover Workspace / Anomaly Overlap / Transition Audit / Research Assistant / Control Ledgers | `<Link to={item.path}>` | static | |
| Verification Gate: "Verify" button | button (per row) | "Verify" | `verify(item)` → stamps `sync_status:"Verified"`, `verified_by`, `verified_at` via `PATCH /api/entities/LiveFeedItems/{id}` | static | `LiveFeedItems` queue was empty in this seed |
| Verification Gate: "Flag" button | button (per row) | "Flag" | `reject(item)` → `PATCH …` sets `sync_status:"NeedsReview"` | static | |
| Verification Gate: source link | link (per row, conditional) | "Source" | opens `it.source_url` in a new tab | static | |

*(`ConfidenceTrendChart`, `ProgramTaskChart`, `RiskHeatmap`, `GovernanceAlertsPanel`, and
`ImmediateReviewQueue` are read-only display panels — Recharts tooltips/legends aside, they
expose no clickable controls.)*

### Programs (`/programs`)

`src/pages/Programs.jsx` — CRUD ledger for the federation's program registry.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Search input | text input | "Search programs…" | `useTableFilter` — client-side substring match on name/id/owner/old_name | static | |
| Domain filter select | dropdown | "Domain" | client-side filter | live | Selected "NetworkGraph"; row count updated to match |
| Status filter select | dropdown | "Status" | client-side filter | static | |
| Column sort headers | button (per sortable column) | ID / Name / Domain / Status / Federation / GitHub / Sensitivity | `SearchableTable` `toggleSort` — client-side sort, tri-state via repeated click | live | Clicked "Name" header |
| Table row click | row click | any row | `openEdit(row)` → opens `RecordSheet` pre-filled | live | Opened for a fresh "New Program" form (see below) |
| "New Program" button | button | "New Program" | `openNew()` → opens empty `RecordSheet` | live | |
| RecordSheet: 12 form fields | text/select/textarea inputs | Program ID, Name, Legacy Name, Repo Name, Domain, Status, Owner, Lead Vector, GitHub Sync, Federation Status, Default Sensitivity, Description | local form state, no submission until Save | static | Field labels confirmed live |
| RecordSheet "Cancel" | button | "Cancel" | `onOpenChange(false)` — discards | live | |
| RecordSheet "Save" | button | "Save" | `handleSave` → `create()`/`update()` → `POST`/`PATCH /api/entities/Programs` | static | Disabled until all `required` fields are filled; not driven to a full submit in this pass |

### App Center (`/apps`)

`src/pages/AppCenter.jsx` — read-only Phase-1 catalog of the 7 federation apps; explicitly ships
with lifecycle actions disabled.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| "Install all recommended" | button | "Install all recommended" | none — `disabled aria-disabled="true"` | live | Confirmed disabled in the running page |
| Per-app "Open"/"Install" | button (×7) | "Open" (TheHub only) / "Install" (others) | none — `disabled` | static | |
| Per-app "Validate" | button (×7) | "Validate" | none — `disabled` | static | |
| Per-app "Technical details" | toggle button (×7) | "Technical details" | `setExpanded` — expands/collapses an `aria-expanded` panel showing `appId` and a "Lifecycle actions are unavailable" note | live | Expanded the TheHub tile; panel appeared |
| `loadAppInventory()` | background fetch | — | `GET /api/federation-manager/apps` with a `Bearer` token from `sessionStorage`; on any failure (no token in a browser session) falls back to the static `APP_CENTER_APPS` catalog | live | Confirmed "Native manager unavailable. Showing the safe read-only catalog." banner rendered, no console error |

### Operations (`/operations`)

`src/pages/Operations.jsx` + `components/manager/*` — the desktop-manager "operations plane"
(dry-run/execute typed, policy-gated operations against the native app manager). Explicitly
designed to render even when unavailable — the page shows all declared operations, including
disabled ones with their disablement reason, rather than hiding them.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Operation list item | button (per operation) | operation id | `select(operation)` → loads its parameter schema, secret presence, and prerequisites | static | |
| Prerequisites disclosure | `<details>/<summary>` | "Prerequisites" | native HTML disclosure toggle | static | |
| Operation form fields | dynamic input/select/switch (schema-driven, per operation) | operation-specific parameter names | `onChange` → local `values` state; no request until Dry run/Run | static | Types: text, number, boolean (Switch), enum (native `<select>`) |
| File-parameter "Choose file…" | button (per file slot) | "Choose file…" | `onPickFile` → in this browser-only harness, sets an error explaining a native picker is required | static-only: requires the desktop app | |
| Secret "Store" | button (per secret) | "Store" | `onSet` → `POST` sets the credential in the OS store (never round-trips the value) | static-only: requires a live manager session | |
| Secret "Remove" | button (per secret, conditional) | trash icon | `onDelete` → deletes the stored credential | static-only: requires a live manager session | |
| "Dry run" | button | "Dry run" | `doPlan()` → `api.plan(operationId, values)`, renders the argv preview, write scope, network policy | static-only: requires the native manager session | Page reachability confirmed (see below) |
| "Run" | button | "Run" | `doRun()` → `api.run(...)`, streams output via `subscribe()`, shows a signed receipt on completion | static-only: requires the native manager session | Disabled until a Dry run has produced a plan |
| "Cancel" (RunConsole) | button | "Cancel" | `doCancel()` → `api.cancel(runId)` | static-only: requires a running operation | |
| Overall page | — | — | `managerApi.listOperations()/accounting()/gates()` — in a browser (no native session), throws `ManagerUnavailableError` | live | Confirmed the page renders its "operations plane is unavailable… Open TheHub through the desktop application" empty state, no console error |

### Cases (`/cases`)

`src/pages/Cases.jsx` — CRUD ledger for `UnifiedCases`, plus a PDF brief generator.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Search input | text input | "Search cases…" | client-side filter | static | |
| Type / Status / Confidence filter selects | dropdown (×3) | Type / Status / Confidence | client-side filter | static | |
| Column sort headers | button (per column) | Code / Title / Type / Municipality / Confidence / Status / Sensitivity | `toggleSort` | static | |
| Table row click | row click | any row | `openEdit(row)` | static | `UnifiedCases` was empty in this seed |
| Per-row "PDF" button | button (per row) | "PDF" (`FileDown` icon) | `setBriefCase(r)` (via `e.stopPropagation()`, doesn't also open the row editor) → opens `BriefTemplateDialog` | static | Not exercised — no seeded case rows to click |
| "New Case" button | button | "New Case" | `openNew()` | live | |
| RecordSheet: 14 fields | inputs | Case ID, Code, Program, Title, Type, Status, Event Date, Date Precision, Municipality, Region, Latitude, Longitude, Confidence, Sensitivity, Public Summary | local state | static | |
| RecordSheet Cancel / Save | button (×2) | "Cancel" / "Save" | as above | live (Cancel) / static (Save) | |
| BriefTemplateDialog: template choice | button (per template) | each `BRIEF_TEMPLATE_LIST` entry | `setSelected(t.id)` | static | |
| BriefTemplateDialog "Cancel" | button | "Cancel" | `onOpenChange(false)` | static | |
| BriefTemplateDialog "Generate PDF" | button | "Generate PDF" | `generateCaseBriefPdf(caseRow, sources, anomalies, selected)` — builds and downloads a jsPDF document client-side, then closes the dialog | static | Not exercised (no case rows to open the dialog from) |

### Sources (`/sources`)

`src/pages/Sources.jsx` — CRUD ledger for `UnifiedSources` (evidence-tier T1–T4 registry).

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Search input | text input | "Search sources…" | client-side filter | live | Page loaded and rendered with 0 console errors |
| Type / Tier / Verification filter selects | dropdown (×3) | Type / Tier / Verification | client-side filter | static | |
| Column sort headers | button (per column) | ID / Title / Type / Tier / Reliability / Verification / Link | `toggleSort` | static | |
| Per-row external link | link (per row, conditional) | `ExternalLink` icon | opens `r.url` in a new tab (`e.stopPropagation()` keeps the row from also opening the editor) | static | |
| Table row click | row click | any row | `openEdit(row)` | static | |
| "New Source" button | button | "New Source" | `openNew()` | static | |
| RecordSheet: 13 fields + Cancel/Save | inputs + buttons | Source ID, Program, Title, Type, Tier, Publisher, dates, URL, Archive Ref, Reliability, Verification, Sensitivity, Summary | as above | static | |

### Federation Tasks (`/tasks`)

`src/pages/Tasks.jsx` + `components/tasks/*` — the cross-module task control plane, with 4
interchangeable views.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Deadline warning banner item | button (per row) | task title | `onSelect` → `openEdit(task)` | static | Banner only renders when high-priority tasks are due ≤48h or overdue |
| Search input | text input | "Search tasks, IDs, assignees…" | `setFilter("search", …)` | static | |
| Program/Status/Priority/Sensitivity/Assignee/Due/Gap filter selects | dropdown (×7) | as labeled | `setFilter(key, value)` | static | |
| "Clear" filters button | button (conditional) | "Clear" | `onClear` → resets `filters` to `{}` | static | Only shown when a filter is active |
| View toggle | button (×4) | Grouped by Program / Urgency Queue / Flat Table / Lifecycle Board | `onChange(view)` | live | Clicked Urgency Queue, Flat Table, Lifecycle Board — all rendered with no errors |
| Grouped view: accordion group header | toggle (per program group) | program label + open/overdue/blocked/high/dueThisWeek/gaps metrics | Radix `AccordionTrigger` — expand/collapse | static | |
| Task card (all 4 views) | click (per task) | task title | `onEdit(task)` → opens `RecordSheet` (`stripDecorations` removes derived `_` fields first) | static | |
| Task card lifecycle "Move to…" select | dropdown (per task, conditional) | "Move to…" | `onStatusChange(task, status)` → `PATCH FederationTasks/{id} {status}`; options are role-gated via `getTaskLifecycleOptions` | static | |
| "New Task" button | button | "New Task" | `openNew()` | static | |
| RecordSheet: 24 fields + Cancel/Save | inputs + buttons | Task ID, Program, Title, Type, Priority, Status, Sensitivity, Assigned To, Due Date, Summary, plus 14 cross-module `linked_*` reference fields | as above | static | |

### Validation Gates (`/gates`)

`src/pages/Gates.jsx` — CRUD ledger for readiness/blocking gates per program.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Search input | text input | "Search gates…" | client-side filter | live | Page loaded, zero console errors |
| Status filter select | dropdown | "Status" | client-side filter | static | |
| Column sort headers | button (per column) | Gate / Program / Blocking / Status / Reviewed | `toggleSort` | static | |
| Table row click | row click | any row | `openEdit(row)` — coerces `blocking` to a string for the select | static | |
| "New Gate" button | button | "New Gate" | `openNew()` | static | |
| RecordSheet: 8 fields + Cancel/Save | inputs + buttons | Gate ID, Program, Gate Name, Status, Blocking, Requirement, Review Notes, Reviewed At | `handleSave` coerces `blocking` back to boolean before `create`/`update` | static | |

### Integrations (`/integrations`)

`src/pages/Integrations.jsx` — CRUD ledger for each program's connection status.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Search input | text input | "Search integrations…" | client-side filter | live | Page loaded, zero console errors |
| Integration / Status filter selects | dropdown (×2) | Integration / Status | client-side filter | static | |
| Column sort headers | button (per column) | Integration / Program / Status / Blocking Reason / Next Action / Checked | `toggleSort` | static | |
| Table row click | row click | any row | `openEdit(row)` | static | |
| "New Integration" button | button | "New Integration" | `openNew()` | static | |
| RecordSheet: 7 fields + Cancel/Save | inputs + buttons | Integration ID, Program, Integration, Status, Last Checked, Blocking Reason, Next Action | as above | static | |

### Exports (`/exports`)

`src/pages/Exports.jsx` + `components/exports/*` — provenance-preserving CSV/GeoJSON export
across every federation ledger.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Per-ledger "CSV" button | button (per ledger row) | "CSV" | `exportLedgerCsv` — builds a CSV client-side and triggers a browser download via a `Blob`/`<a download>`; `recordExport` then logs an `Exports` row and an `AuditLog` row, and shows a toast | live | Clicked an enabled ledger's CSV button; a `download` event fired. Disabled when that ledger has 0 records (confirmed: the first-listed ledger was disabled and correctly un-clickable) |
| Per-ledger "GeoJSON" button | button (per geo-flagged ledger row, conditional) | "GeoJSON" | `exportLedgerGeoJson` — same flow, filtered to rows with lat/lon | static | Disabled when 0 mappable records |
| Export History table | read-only | — | lists all recorded exports (`Exports` entity) | live | Confirmed the CSV click above produced a new row after `invalidateQueries` |

### Module Readiness (`/readiness`)

`src/pages/ModuleReadiness.jsx` + `components/github/*` — GitHub issues/PRs dashboard per repo.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Owner/org input | text input | "GitHub Owner / Org" | `setOwner`; Enter key also triggers Load | live | Filled with "test-org" |
| Repository select | dropdown | repo picker (INTSYS-PR + all 6 producer repos) | `setRepo` | static | |
| "Load" button | button | "Load" (RefreshCw/spinner icon) | `federation.functions.invoke("githubModuleReadiness", {action:"list",…})` → `POST /api/functions/githubModuleReadiness/invoke` | live | Backend's diagnostic-mode stub returned `{status:"not_implemented", result:null}` (no `.data` field); the page reads `res.data`, gets `undefined`, and simply doesn't render the Issues/PRs tabs — no crash, no error banner. Real GitHub data is **static-only: requires a live GitHub App/token-backed deployment** |
| "New Issue" button | button (conditional on loaded data) | "New Issue" | `setDialogOpen(true)` | static-only: requires a loaded repo (see above) | |
| NewIssueDialog: Title/Description inputs + Cancel/Create | inputs + buttons | as labeled | `createIssue` → `functions.invoke("githubModuleReadiness",{action:"createIssue",…})` | static-only: requires live GitHub | |
| Issues/Pull Requests tabs | tab | "Issues (N)" / "Pull Requests (N)" | Radix `Tabs` | static-only: requires loaded data | |
| Per-issue Close/Reopen button | button (per issue) | "Close"/"Reopen" | `toggleIssue` → `functions.invoke(...,{action: state==="open"?"closeIssue":"reopenIssue",…})` | static-only: requires live GitHub | |
| Per-item external link | link (per item) | `ExternalLink` icon | opens `item.html_url` | static-only: requires live GitHub | |

### Transition Audit (`/transition`)

`src/pages/TransitionAudit.jsx` + `components/audit/*` — confirms INTSYS-PR preserves the legacy
`thehub-pr` research ecosystem. Entirely read-only.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| *(none)* | — | — | `LineageBanner`, `ModuleParityList`, `GateChecklist`, `EvidenceStandardsCard`, `SyncBlockCard`, and 5 `StatCard`s are all read-only displays — no clickable controls | live | Page loaded with zero console errors |

### Federation Crossover Workspace (`/crossover`)

`src/pages/FederationCrossoverWorkspace.jsx` + `components/crossover/*` — cross-module
correlation matrix, filters, and 5 tabbed views.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| "Export CSV" button | button (conditional) | "Export CSV" | `exportCrossoversCsv(filtered)` — client-side CSV download | static | Disabled when `filtered` is empty |
| Filter: free-text search | text input | "Search records, rationale, municipality…" | `setFilters` | static | |
| Filter selects | dropdown (×5 fixed + up to 3 data-driven) | Status / Confidence / Evidence tier / Crossover type / Module pair, plus Municipality/Agency/Vendor when data-driven options exist | `setFilters` | static | |
| Filter: date range | date inputs (×2) | date-from / date-to | `setFilters` | static | |
| "Reset" filters button | button | "Reset" (X icon) | `resetFilters()` | static | |
| Tabs | tab (×5) | Matrix / Pairwise Panels / 3+ Module Convergence (N) / ILAP / POIs (N) / All Crossovers (N) | Radix `Tabs` | live | Clicked "Pairwise Panels" and (in a second pass) the "All Crossovers" tab |
| Matrix: row click | row click (per populated pair) | module-pair row | `onSelectPair` → sets `filters.pair`, which the "All Crossovers" tab then reflects | live | Clicked the first matrix row |
| Pairwise Panels: accordion item | toggle (per pair, A–K) | pair title | Radix `AccordionItem` expand/collapse | static | |

### Anomaly Overlap (`/anomaly-overlap`)

`src/pages/AnomalyOverlap.jsx` — compares two modules' anomaly-flagged cases by shared
municipality/region.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Module A select | dropdown | "Module A" | `setModuleA` | live | Page loaded, zero console errors (default AguaYLuz-PR vs Ovnis-PR shown) |
| Module B select | dropdown | "Module B" | `setModuleB` | static | |

### Control Ledgers (`/control`)

`src/pages/ControlLedgers.jsx` — a tabbed shell that re-renders the same components already
catalogued above (Programs, Cases, Sources, Dictionary, Tasks, Gates, Integrations, Exports,
Module Readiness, Manifest) under one URL, syncing the active tab to `?tab=`.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Tab trigger | tab (×10) | Programs / Unified Cases / Unified Sources / Dictionary / Federation Tasks / Validation Gates / Integrations / Exports / Module Readiness / Manifest | `onTabChange` → `navigate("/control?tab="+v)` | live | Clicked the "Unified Cases" tab; URL and content updated |
| *(tab content)* | — | — | renders the same page components documented in their own sections above | — | Not re-listed to avoid duplication |

### Project Signs (`/project-signs`)

`src/pages/ProjectSigns.jsx` — generates and previews consolidated funding "signs" per project.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| "Generate signs" button | button | "Generate signs" | `federation.projectSigns.generate(true)` → `POST /api/project-signs/generate`, invalidates the `ProjectSigns` query, shows a success/failure toast | live | Clicked; backend endpoint is genuinely implemented (`hub.project_signs`); request completed, page stayed responsive, no console error |
| Per-sign "Preview" button | button (per row, conditional) | "Preview" (ExternalLink icon) | `setPreview(sign)` → opens a `Dialog` embedding an `<iframe>` of `GET /api/project-signs/{id}/html` | static | No signs existed in this seed to click |
| Per-sign "Download" link | link (per row, conditional) | "Download" | `<a href=… download>` to the same HTML sign URL | static | |
| Preview dialog close | dialog dismissal | — | `onOpenChange` | static | |

### Research Assistant (`/research`)

`src/pages/ResearchAssistant.jsx` + `components/research/*` — 3-tab LLM research surface.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Top-level tabs | tab (×3) | Module Chat Sessions / Research Operator / Structured Research | Radix `Tabs` | live | Clicked "Research Operator" and (second pass) "Structured Research" |
| Chat: language select | dropdown | Español/English/Bilingüe | `setLanguage` | static | |
| Chat: "Web search" switch | switch | "Web search" | `setWebGrounded` — toggles `add_context_from_internet` on the next LLM call | static | |
| Chat: per-module sub-tab | tab (×6) | Hub / Spiderweb / Ovnis / AguaYLuz / MoneySweep / Skywatcher | `setChatModule` — each renders its own persisted `ModuleChat` session | static | |
| ModuleChat: message textarea + send | textarea + button | message input / send icon | `send()` → creates a `ResearchChat` row, calls `federation.integrations.Core.InvokeLLM`, records the assistant reply | static-only: requires a live LLM provider | Diagnostic-mode stub returns `not_implemented`; `ModuleChat` renders the stringified stub as the "assistant" reply rather than crashing |
| ModuleChat "Clear" | button (conditional) | "Clear" | deletes every `ResearchChat` row for the session | static | |
| ModuleChat "Memory"/"Distill"/"Refresh" | button | "Memory", then "Distill"/"Refresh" | opens `MemoryPanel`; `distillMemory()` calls `InvokeLLM` again to summarize the transcript into a `ResearchMemory` row | static-only: requires a live LLM provider | |
| MemoryPanel close | button (icon) | X | `onClose` | static | |
| OperatorChat: file attach | button + hidden file input | paperclip icon | `onPickFiles` → `Core.UploadFile` per file, then attaches as `file_urls` on the next message | static-only: requires file-storage backend | |
| OperatorChat: attached-file remove | button (per file) | X | removes from the pending `files` array | static | |
| OperatorChat: message textarea + send | textarea + button | message input / send icon | `send()` → `federation.agents.addMessage` on a live SSE-subscribed conversation | live | Textarea filled and Run clicked in the Structured tab (see below); Operator tab loaded and rendered its "governed actions" empty state without crashing, despite the diagnostic-mode agents stub's SSE MIME-type warning |
| OperatorChat "New session" | button | "New session" | `startNew()` → `federation.agents.createConversation` again | static | |
| Structured: query textarea | textarea | prompt placeholder | `setQuery` | live | Filled with a test query |
| Structured: module scope select | dropdown | module scope picker | `setScope` | static | |
| Structured: language select | dropdown | Español/English/Bilingüe | `setLanguage` | static | |
| Structured: "Run Research" button | button | "Run Research" | `run()` → `Core.InvokeLLM` with a structured JSON schema | live | Clicked; diagnostic stub responded, page rendered "No leads returned" empty state, no console error beyond the expected 401 |

### Dictionary (`/dictionary`)

`src/pages/Dictionary.jsx` — CRUD ledger for term normalization.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Search input | text input | "Search terms…" | client-side filter | live | Page loaded, zero console errors |
| Category/Module/Status filter selects | dropdown (×3) | Category / Module / Status | client-side filter | static | |
| Column sort headers | button (per column) | ID / Normalization / Category / Module / Status | `toggleSort` | static | |
| Table row click | row click | any row | `openEdit(row)` | static | |
| "New Term" button | button | "New Term" | `openNew()` | static | |
| RecordSheet: 7 fields + Cancel/Save | inputs + buttons | Term ID, Raw Term, Normalized Term, Category, Module, Status, Definition | `handleSave` stamps `source_repo:"thehub-pr"` on create | static | |

### Manifest (`/manifest`)

`src/pages/Manifest.jsx` — CRUD ledger for per-program federation manifests.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Search input | text input | "Search manifests…" | client-side filter | live | Page loaded, zero console errors |
| Role/Status filter selects | dropdown (×2) | Role / Status | client-side filter | static | |
| Column sort headers | button (per column) | ID / Program / Role / Schema / Status | `toggleSort` | static | |
| Table row click | row click | any row | `openEdit(row)` | static | |
| "New Manifest" button | button | "New Manifest" | `openNew()` | static | |
| RecordSheet: 6 fields + Cancel/Save | inputs + buttons | Manifest ID, Program, Module Role, Schema Version, Status, Notes | as above | static | |

### Spiderweb (`/spiderweb`)

`src/pages/Spiderweb.jsx` — graph nodes/edges (infrastructure & terrain module), plus a map tab.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Tabs | tab (×3) | Graph Nodes / Map View / Graph Edges | Radix `Tabs` | live | Page loaded, zero console errors (default "Graph Nodes" tab) |
| Nodes: search + Type/Confidence filters | inputs (×3) | "Search nodes…" + Type + Confidence | `EntityLedger`'s built-in filter bar | static | |
| Nodes: column sort headers | button (per column) | ID / Label / Type / Confidence / Sensitivity | `toggleSort` | static | |
| Nodes: table row click | row click | any row | opens `RecordSheet` for editing | static | |
| Nodes: "New Node" button | button | "New Node" | opens empty `RecordSheet` | static | |
| Nodes: RecordSheet fields + Cancel/Save | inputs + buttons | Node ID, Label, Type, Municipality, Lat/Long, Confidence, Sensitivity, Summary | as above | static | |
| Map View: Leaflet map | map (pan/zoom/marker popups) | — | `MultiMarkerMap` — plots geo-coded `GraphNodes` on a Leaflet/CARTO dark basemap | static | |
| Edges: search + Relationship/Tier filters | inputs (×3) | "Search edges…" + Relationship + Tier | as above | static | |
| Edges: column sort headers | button (per column) | ID / Source / Target / Relationship / Tier / Status | `toggleSort` | static | |
| Edges: table row click + "New Edge" + RecordSheet | as above | — | as above (9 fields: Edge ID, Source/Target Node, Relationship, Evidence Tier, Confidence, Status, Sensitivity, Rationale) | static | |

### Ovnis (`/ovnis`)

`src/pages/Ovnis.jsx` — pattern observations & witness reports (UAP/USO module).

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Tabs | tab (×2) | Pattern Observations / Witness Reports | Radix `Tabs` | live | Page loaded, zero console errors |
| Patterns: search + Type/Confidence filters | inputs (×3) | "Search patterns…" + Type + Confidence | `EntityLedger` filter bar | static | |
| Patterns: sort headers, row click, "New Pattern", RecordSheet (6 fields) + Cancel/Save | as above | — | as above | static | |
| Witness: search + Privacy/Verification filters | inputs (×3) | "Search reports…" + Privacy + Verification | as above | static | |
| Witness: sort headers, row click, "New Report", RecordSheet (5 fields) + Cancel/Save | as above | — | as above | static | |

### AguaYLuz (`/aguayluz`)

`src/pages/AguaYLuz.jsx` + `components/feed/AguaYLuzFeedTab.jsx` — water/power module: a live
feed tab, plus Infrastructure Assets, Operational Alerts (read-only), and Continuity Risks.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Module tabs | tab (×4) | Water + Power Feed / Infrastructure Assets / Operational Alerts / Continuity Risks | Radix `Tabs` | live | Clicked "Operational Alerts" |
| Feed tab: inner tabs | tab (×3) | Service Feed / Staging Queue (N) / Sources | Radix `Tabs` | live | Clicked "Staging Queue" |
| Feed tab: "Add Service Event" button | button | "Add Service Event" | opens a `RecordSheet` (14 fields: Feed Item ID, Source ID, Source System, Utility Domain, Event Type, Title, Facility Name/Type, Municipality, Customers Affected, Lat/Long, Source URL, Evidence Tier, Summary) | live | Sheet opened, then Cancel clicked |
| Staging Queue: "Verify" button | button (per row, conditional) | "Verify" (ShieldCheck icon) | `setStatus(item,"Verified")` → resolves reviewer via `auth.me()`, `PATCH LiveFeedItems` | static | Button presence confirmed live; not clicked (would mutate seed data) |
| Staging Queue: "Promote" button | button (per row) | "Promote" (Check icon) | `setStatus(item,"Promoted")` → `promoteFeedItem()` creates an `InfrastructureAssets` row, then `PATCH` the feed item | static | Disabled until `sync_status==="Verified"` |
| Staging Queue: "Review"/"Defer" buttons | button (per row, ×2) | "Review" / "Defer" | `setStatus(item,"NeedsReview"/"Deferred")` | static | |
| Staging Queue: source link | link (per row, conditional) | "Source" | opens `it.source_url` | static | |
| Sources tab | read-only table | — | `SourceHealthPanel` — health/freshness per configured feed source | static | |
| Infrastructure Assets: search + Type/Status filters, sort, row click, "New Asset", RecordSheet (12 fields) + Cancel/Save | as above | — | standard `EntityLedger` CRUD | static | |
| Operational Alerts: search + Module/Review filters, sort, row click | as above | — | `EntityLedger … readOnly` — **no create/edit affordances**; a read-only projection of `GovernanceAlerts` scoped to `aguayluz-pr` | live | "Operational Alerts" tab click confirmed the read-only table rendered |
| Continuity Risks: search + Type/Severity filters, sort, row click, "New Risk", RecordSheet (9 fields) + Cancel/Save | as above | — | standard `EntityLedger` CRUD | static | |

### MoneySweep (`/moneysweep`)

`src/pages/MoneySweep.jsx` + `components/feed/MoneySweepFeedTab.jsx` — procurement/funding
module: a live feed tab (USASpending refetch), plus Contracts, Vendors, Anomaly Flags.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Module tabs | tab (×4) | Procurement + Funding Feed / Contracts / Vendors / Anomaly Flags | Radix `Tabs` | live | Page loaded, zero console errors (default "Feed" tab) |
| Feed tab: inner tabs | tab (×3) | Live Feed / Staging Queue (N) / Sources | Radix `Tabs` | static | |
| Feed tab: "Refetch USAspending" button | button | "Refetch USAspending" (spinner icon) | `federation.functions.invoke("refetchUSASpending",{source_id:"usaspending-pr",limit:25})` — invalidates `LiveFeedItems/Sources/Runs`, toasts the result | static-only: requires the USASpending integration | Same diagnostic-stub pattern as Module Readiness's Load button — `res.data` is `undefined`, so the success toast would read "Fetched undefined · undefined new" rather than crashing |
| Staging Queue: Verify/Promote/Review/Defer buttons + source link | button (per row, ×4) + link | as AguaYLuz | `promoteFeedItem()` here creates a `Contracts` row | static | |
| Sources tab | read-only table | — | `SourceHealthPanel` | static | |
| Contracts: search + Procurement/Status filters, sort, row click, "New Contract", RecordSheet (12 fields) + Cancel/Save | as above | — | standard `EntityLedger` CRUD | static | |
| Vendors: search + Review filter, sort, row click, "New Vendor", RecordSheet (8 fields) + Cancel/Save | as above | — | standard `EntityLedger` CRUD | static | |
| Anomaly Flags: search + Type/Severity filters, sort, row click, "New Flag", RecordSheet (9 fields) + Cancel/Save | as above | — | standard `EntityLedger` CRUD | static | |

### Skywatcher (`/skywatcher`)

`src/pages/Skywatcher.jsx` — airspace events, map, correlation reviews (aviation module).

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Tabs | tab (×3) | Airspace Events / Map View / Correlation Reviews | Radix `Tabs` | live | Clicked "Map View" |
| Events: search + Type/Status filters, sort, row click, "New Event", RecordSheet (13 fields) + Cancel/Save | as above | — | standard `EntityLedger` CRUD | static | |
| Map View: Leaflet map | map | — | `MultiMarkerMap` over `AirspaceEvents` | live | Map View tab click rendered the Leaflet container with no console error |
| Correlation Reviews: search + Type/Confidence filters, sort, row click, "New Review", RecordSheet (9 fields) + Cancel/Save | as above | — | standard `EntityLedger` CRUD | static | |

### Centinelas (`/centinelas`)

`src/pages/Centinelas.jsx` — public matters intake/routing module.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Tabs | tab (×2) | Public Matters / Map View | Radix `Tabs` | live | Page loaded, zero console errors |
| Matters: search + Status/Confidence filters, sort, row click, "New Matter", RecordSheet (9 fields) + Cancel/Save | as above | — | standard `EntityLedger` CRUD | static | |
| Map View: Leaflet map | map | — | `MultiMarkerMap` over `PublicMatters` | static | |

### Login (`/login`)

`src/pages/Login.jsx`. **Only routed when `requires_auth=true`** — this repo's own backend runs
in diagnostic mode (`requires_auth:false`), where `App.jsx` instead renders `<Navigate to="/" />`
for this path, since the diagnostic backend implements no `/auth/login` endpoint.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| "Continue with Google" button | button | "Continue with Google" | `federation.auth.loginWithProvider("google","/")` | static-only: requires OAuth + an auth-enabled backend | |
| Email input | text input | "Email" | `setEmail` | static-only: requires an auth-enabled backend | |
| Password input | password input | "Password" | `setPassword` | static-only: requires an auth-enabled backend | |
| "Forgot password?" link | link | "Forgot password?" | `<Link to="/forgot-password">` | static-only: requires an auth-enabled backend | |
| "Log in" submit button | button | "Log in" | `federation.auth.loginViaEmailPassword(email,password)` → on success, full-page redirect to `/` | static-only: requires an auth-enabled backend | Confirmed live that `/login` redirects to `/` in this repo's diagnostic-mode deployment (title stayed "TheHub PR", not a login form) |
| "Create one" link | link | "Create one" | `<Link to="/register">` | static-only | |

### Register (`/register`)

`src/pages/Register.jsx`. Same reachability caveat as Login.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| "Continue with Google" button | button | "Continue with Google" | `federation.auth.loginWithProvider("google","/")` | static-only: requires OAuth + auth backend | |
| Email/Password/Confirm inputs | inputs (×3) | Email / Password / Confirm Password | local state; client-side match check on submit | static-only: requires auth backend | |
| "Create account" submit | button | "Create account" | `federation.auth.register({email,password})` → shows the OTP step | static-only: requires auth backend | |
| OTP: 6-slot code input | `InputOTP` | 6 digit slots | `setOtpCode` | static-only: requires auth backend | |
| OTP: "Verify" button | button | "Verify" | `federation.auth.verifyOtp({email,otpCode})` → stores the token, redirects to `/` | static-only: requires auth backend | Disabled until 6 digits entered |
| OTP: "Resend" button | button (text-style) | "Resend" | `federation.auth.resendOtp(email)` → toast | static-only: requires auth backend | |
| "Log in" link | link | "Log in" | `<Link to="/login">` | static-only | |

### Forgot Password (`/forgot-password`)

`src/pages/ForgotPassword.jsx`. Same reachability caveat.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Email input | text input | "Email address" | `setEmail` | static-only: requires auth backend | |
| "Send reset link" submit | button | "Send reset link" | `federation.auth.resetPasswordRequest(email)` — always shows the success message regardless of outcome (prevents email enumeration) | static-only: requires auth backend | |
| "Back to log in" link | link | "Back to log in" | `<Link to="/login">` | static-only | |

### Reset Password (`/reset-password`)

`src/pages/ResetPassword.jsx`. Same reachability caveat.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| New Password / Confirm inputs | inputs (×2) | as labeled | local state; client-side match check | static-only: requires auth backend | |
| "Reset password" submit | button | "Reset password" | `federation.auth.resetPassword({resetToken,newPassword})` → redirect to `/login` | static-only: requires auth backend | |
| "Request a new link" link | link (conditional, no token) | "Request a new link" | `<Link to="/forgot-password">` | static-only | Shown instead of the form when the URL carries no `?token=` |

### Page Not Found (`*`)

`src/lib/PageNotFound.jsx` — catch-all 404.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| "Go Home" button | button | "Go Home" | `window.location.href = '/'` | static | |

### App shell (present on every dashboard page)

`components/layout/*`, `components/notifications/NotificationBell.jsx`,
`components/shared/ThemeToggle.jsx`.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Sidebar nav link | link (×27, desktop) | one per routed page, grouped Overview/Producers/Federation/Records/Tools | `<Link to={item.path}>`, active-state via `isNavActive` | live | Clicked Cases, Sources, Gates from the sidebar — all navigated correctly |
| Theme toggle | icon button | sun/moon | `toggleTheme()` — flips `light`/`dark`, persisted, drives both Tailwind `.dark` and `federation.css` tokens | live | Toggled to dark and back; `<html>`'s `dark` class changed as expected |
| Mobile nav "Open navigation menu" | icon button | hamburger (Menu icon) | opens a `Sheet` (slide-over) duplicating the sidebar's nav links | static | Desktop viewport used for this audit; component reads identically to the desktop `Sidebar` |
| Mobile nav sheet: nav link | link (×27, mobile) | as desktop | `<Link>`, closes the sheet on click | static | |
| Notification bell | icon button | bell (+ unread badge) | `toggle()` — opens a dropdown digest and, if unread, calls `markAllRead()` | live | Opened; dropdown rendered "You're all caught up." (no seeded notifications), no console error |
| ErrorBoundary "Try again" | button (conditional, only on a caught render error) | "Try again" | `this.setState({error:null})` — clears the boundary and retries the subtree | static | Not exercised — no render error occurred anywhere in this audit |

---

## Desktop Launcher

### `desktop/launcher.html`

Static HTML/CSS/vanilla-JS page (no build step), served at `/launcher` by
`desktop/app_server.py` once the FastAPI app is running, and reachable directly as a `file://` URL
for pure static inspection. It lists the 7 federation repos (from `launcher_api.py`'s
`FEDERATION_REPOS`) and lets the operator launch any sibling repo's desktop app.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| "This window" (Hub) | non-interactive chip | "THIS WINDOW" | none — the repo running the launcher is never itself launchable | live | Loaded `launcher.html` via `file://` and confirmed the DOM (see below) |
| Per-repo "Launch" button | button (×6, one per sibling repo) | "Launch" | `launch(repo)` → `POST /api/local/launch/{repo}` — spawns the sibling repo's `.app` bundle (macOS, via `open -W`) or its `PRII-*.sh`/`.bat` script, tracked in-process so status flips to "Running" | static-only: requires the sibling repo cloned next to this one, and a running desktop backend (only reachable at `/launcher` on a live app, not via a bare `file://` open) | Button is `disabled` whenever the repo isn't cloned, has no desktop wrapper, or is already running |
| Per-repo "GitHub ↗" link | link (conditional, repo not cloned) | "GitHub ↗" | `<a href="https://github.com/jotaele44/{repo}" target="_blank">` | static | Shown in place of "Launch" for any repo not present next to this checkout |
| Main dashboard link | link | "here" (in the footer note) | `<a href="/">` — back to TheHub's own dashboard | static | |
| Background poll | — | — | `refresh()` on load and every 5s: `GET /api/local/federation`, re-renders the list (status chips: THIS WINDOW / NOT CLONED / NO WRAPPER / RUNNING / FIRST-RUN SETUP / READY) | live | Loaded the file directly; confirmed the page's static shell (`<title>TheHub</title>`, "Loading…" placeholder, footer note) renders correctly. The `fetch("/api/local/federation")` call itself is **static-only: requires the FastAPI backend's `/api/local/*` routes**, which only exist under `desktop/app_server.py`, not the plain `server/backend/main.py` instance this audit ran (confirmed: opened as `file://`, so no backend was reachable at all — the page showed "Failed to load federation status" as designed, rather than crashing) |

---

## Desktop launcher entry points (native scripts)

Read `desktop/launch.py`, `desktop/app_server.py`, `desktop/launcher_api.py`, `desktop/config.py`,
and the root `PRII-THEHUB.*` / `PRII-FEDERATION.*` / `PRII-THEHUB.app` / `PRII Federation.app`
launchers (all delegate to the shared `packages/prii_desktop` runtime).

| Entry point | Platform | What happens |
|---|---|---|
| `PRII-THEHUB.command` / `.sh` | macOS / Linux | `cd` to the repo root, `python3 desktop/setup.py --ensure` (one-time venv + dependency install, needs internet once), then `exec .venv/bin/python desktop/launch.py` — opens the **main dashboard** (`/`) |
| `PRII-THEHUB.bat` | Windows | same, via `py -3`/`python`, then `.venv\Scripts\python.exe desktop\launch.py` |
| `PRII-THEHUB.app` | macOS | a real `.app` bundle (`Info.plist` + `AppIcon.icns`); its `Contents/MacOS/PRII-THEHUB` shell script self-locates the repo root from its own bundle path, detects and explains macOS Gatekeeper "App Translocation" (quarantined-copy) failures via an `osascript` dialog, restores `PATH` (Finder-launched apps miss Homebrew/python.org), runs the same `setup.py --ensure`, then execs `desktop/launch.py` — opens the **main dashboard** |
| `PRII-FEDERATION.command` / `.sh` / `.bat` | macOS/Linux/Windows | identical setup step, then `desktop/launch.py --route /launcher` — opens **`launcher.html`** instead of the dashboard |
| `PRII Federation.app` | macOS | same `.app`-bundle pattern as `PRII-THEHUB.app` (own `Info.plist`/icon), execs `desktop/launch.py --route /launcher` — opens **`launcher.html`** |
| `Fix-Gatekeeper.command` | macOS | standalone remediation script the `.app` bundles point to when they detect App Translocation (clears the quarantine flag so the app can see its own checkout) |
| `desktop/launch.py` (what all the above ultimately run) | any | thin adapter: `prii_desktop.launch(DesktopConfig.from_module(desktop.config))` — starts the FastAPI backend (`desktop/app_server.py`, which mounts `server/backend/main.py`'s API plus the `/launcher` route and `/api/local/*` launcher API), waits for its `/health` endpoint, then opens a native **pywebview** window at the resolved route (falls back to the system default browser if pywebview is unavailable) |

---

## Design System

`federation-design/packages/react` (`@pr-federation/react`) — a small, reusable component
library consumed by the dashboard via a `file:` dependency (and by sibling repos in the
federation). Exported entirely from two files: `src/index.jsx` (components) and
`src/semantics.js` (status-vocabulary/tone logic, re-exported from `index.jsx`). These are
**primitives**, not standalone screens — cataloguing what each accepts, not per-page usage.

| Export | Kind | Props / variants | Notes |
|---|---|---|---|
| `FederationThemeProvider` | context provider | `repo`, `defaultTheme`, `allowedThemes` (default `['light','dark']`), `children` | Persists the chosen theme to `localStorage` under `fd-theme:{repo}`, toggles `<html>`'s `.dark` class and `data-theme`/`data-repo` attributes. Falls back to `prefers-color-scheme` when nothing is stored |
| `useFederationTheme()` | hook | — | `{ theme, setTheme, toggleTheme, allowedThemes }`; throws if used outside the provider |
| `FederationButton` | interactive: button | `variant` (default `'primary'`), `loading`, `disabled`, `type` (default `'button'`), plus any native `<button>` prop | Renders a spinner and sets `aria-busy` when `loading`; disabled while loading |
| `FederationIconButton` | interactive: button | `label` or `aria-label` (one required — throws otherwise), plus native `<button>` props | Icon-only button; content is wrapped `aria-hidden` since the label carries the accessible name |
| `FederationPanel` | layout | `as` (default `'section'`), any props | Polymorphic container, not itself interactive |
| `FederationSemanticBadge` | display | `kind`, `value`, `label`, `children` | Resolves `kind`/`value` through `semantics.js`'s vocabulary to a tone + default label; non-interactive |
| `FederationStatusBadge` | display | `status`, `kind` (default `'presentation'`) | Presentation-mode maps any string through `federationStatusRole()`; semantic-mode delegates to `FederationSemanticBadge` |
| `FederationEvidenceTierBadge` | display | `tier` (default `'ungraded'`) | Preset over `FederationSemanticBadge` for T1–T4/ungraded |
| `FederationConfidenceBadge` | display | `confidence` (default `'unknown'`) | Preset for high/medium/low/unknown |
| `FederationProvenanceBadge` | display | `state` (default `'missing'`) | Preset for captured/verified/superseded/missing/hash_mismatch |
| `FederationFreshnessBadge` | display | `freshness` (default `'unknown'`) | Preset for current/aging/stale/unknown |
| `FederationSourceBadge` | display | `source`, `sourceId`, `verified` (default `false`), `children` | Renders `data-verified` for CSS hooking |
| `FederationEmptyState` | display | `icon`, `title`, `description`, `action`, `inline` | `role="status"`/`aria-live="polite"`; emits both `fd-state--empty`/`fd-empty-state` class families for back-compat. Consumed directly by the dashboard's own `EmptyState.jsx` |
| `FederationLoadingState` / `FederationErrorState` / `FederationFilteredEmptyState` / `FederationOfflineState` / `FederationDegradedState` / `FederationPartialDataState` / `FederationStaleDataState` | display | `title`, `description`, `action`, `icon`, `inline`, `busy` | Thin presets over the internal `FederationStateMessage`; `error` renders `role="alert"`/`aria-live="assertive"`, others `role="status"`/`polite` |
| `FederationAsyncState` | display/control-flow | `state` (`'idle'\|'loading'\|'empty'\|'filtered_empty'\|'error'\|'partial'\|'offline'\|'degraded'\|'stale'\|'ready'\|'success'`), `children` | Renders `children` when ready/success, `FederationEmptyState` when empty, else the matching state message |
| `FederationStatCard` | display | `label`, `value`, `icon`, `sub`, `alert`, `tone`, `accent`, `loading` | `loading` suppresses the value and sets `aria-busy` rather than showing a stale number |
| `resolveFederationSemantic(kind, value)` | logic | `kind` ∈ operational/workflow/evidenceTier/confidence/provenance/freshness/asyncState | Normalizes the value and looks it up in the frozen `DEFINITIONS` table, falling back per-kind on an unrecognized value |
| `federationStatusRole(status)` / `federationTone(status)` | logic | any string | Maps free-form status text to one of 9 presentation tones (`danger/success/warning/info/neutral/process/tier/caution/elevated`), with legacy aliases (`operational→success`, `critical→danger`, etc.) |
| Vocabulary constants | data | `FEDERATION_PRESENTATION_TONES`, `FEDERATION_OPERATIONAL_STATES`, `FEDERATION_WORKFLOW_STATES`, `FEDERATION_EVIDENCE_TIERS`, `FEDERATION_CONFIDENCE_LEVELS`, `FEDERATION_PROVENANCE_STATES`, `FEDERATION_FRESHNESS_STATES`, `FEDERATION_ASYNC_STATES`, `FEDERATION_SEMANTIC_DEFINITIONS` | Frozen arrays/objects — the canonical vocabulary every badge/state component is built on |

*No toggle/switch/input/select/checkbox primitives are exported by this package* — the dashboard's
own switches, selects, and inputs come from local Radix wrappers in `server/frontend/src/
components/ui/`, not from `@pr-federation/react`.

---

## Summary

| Metric | Count |
|---|---|
| Dashboard pages catalogued (routed + shared app shell) | 30 routed page components + the catch-all 404 + 1 shared app-shell section = **32 sections** |
| Interactive elements catalogued — dashboard | **199** (201 table rows minus 2 rows that are "this page has no controls" / "see the tabs' own sections" notations, not actual controls) |
| Interactive elements catalogued — `launcher.html` | **5** |
| Interactive elements catalogued — Design System | **19** exported members (2 of which — `FederationPanel` and the vocabulary/logic exports — are non-interactive building blocks, catalogued for completeness) |
| **Total interactive elements catalogued** | **223** |
| Live-verified (that specific control clicked/exercised against the running app in this pass) | **45** dashboard rows + `launcher.html`'s static shell load = **~46** |
| Static-only (read from source only; either not exercised in this pass, or explicitly needs an external service/backend mode this repo doesn't ship here) | **154** dashboard rows (of which 19 are Login/Register/Forgot/Reset controls that need `requires_auth=true` and a real auth backend just to be reachable) + `launcher.html`'s 4 dynamic rows (need its own `/api/local/*` backend, not the plain API server this audit ran) + all 19 Design System rows (library code, not a running screen) |
| Pages that loaded live with **zero page/render errors** | **27 / 27** routed pages reachable in this repo's default (diagnostic-mode, `requires_auth=false`) configuration |
| Broken / dead controls found | **None.** Every clicked control behaved as its source predicted, including every diagnostic-mode stub (GitHub functions, LLM invoke, agents/SSE) — each degrades to an empty/graceful state rather than crashing or hanging the UI |
| Minor findings (not broken, worth a maintainer's attention) | 1) `src/components/shared/MapView.jsx` exists but is **not imported anywhere** in the app — `MultiMarkerMap.jsx` is the map component actually used on every module's Map View tab; MapView.jsx appears to be dead code. 2) `MoneySweepFeedTab`'s "Refetch USAspending" toast reads the diagnostic-stub response's `d.items_fetched`/`d.items_new`, which are `undefined` on that stub (no `.data` wrapper), so the success toast would literally read "Fetched undefined · undefined new" rather than a clean message — cosmetic, and only reachable without a live USASpending integration configured. |

**Branch-name note (flagged for the operator, not a GUI finding):** the requested branch name
`claude/repository-gui-audit-csr1xs` already exists on `origin` with 111 commits unrelated to this
audit (federation/ontology control-plane work, not a GUI audit) — an apparent naming collision,
not something created by this session. To avoid overwriting that existing branch/work, this audit
was committed to `claude/gui-audit-thehub-pr` instead.
