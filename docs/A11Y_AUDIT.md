# Accessibility (A11y) Audit — thehub-pr

## Overview

This is a follow-up to `docs/GUI_AUDIT.md` (the prior GUI-controls audit), focused specifically on
automated accessibility conformance of the live `server/frontend` web dashboard. It uses the
project's own dev build (Vite + FastAPI backend, diagnostic-mode seed data) driven by the
environment's shared Playwright/axe-core runner at `/home/user/.a11y-runner`.

This audit is one of three combined pieces of work in this PR — the other two,
`docs/design-system-usage.json` and `docs/TEST_HARNESS_AUDIT.md`, cover design-system consumption
and an audit of `federation-design/test-harness/` itself. This document covers the live a11y pass
only.

## Method

- **Tooling:** the shared, pre-provisioned runner at `/home/user/.a11y-runner` — pinned
  `@playwright/test@1.62.1` + `@axe-core/playwright@4.12.1`, Chromium via `executablePath` pointing
  at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`. Not modified; invoked per-route via
  `FEDERATION_BASE_URL` / `FEDERATION_ROUTE` env vars against
  `cd /home/user/.a11y-runner && npx playwright test`.
- **App under test:** `server/backend/main.py` on `127.0.0.1:8102` (`PYTHONPATH=src`, diagnostic
  mode, no auth) + Vite dev server on `127.0.0.1:5302`, with a **temporary** `server.proxy` entry
  added to `server/frontend/vite.config.js` (`/api` → `127.0.0.1:8102`) so the browser's
  same-origin fetches reach the backend without hitting the backend's CORS allow-list (which only
  lists `localhost:5173`/`127.0.0.1:5173`). Reverted before finishing (see Cleanup). Confirmed the
  correct app was under test via page `<title>` = "TheHub PR" before scanning.
- **Routes scanned (5):** `/` (Recent Activity), `/hub`, `/cases`, `/crossover`
  (Federation Crossover Workspace), `/research` (Research Assistant) — chosen from
  `server/frontend/src/App.jsx`'s route table as a representative cross-section: the landing page,
  the aggregation hub, a CRUD-heavy record page with dialogs/sheets, the most control-dense
  federation view (filters, tabs, a data table), and a chat-style page. All five resolved with
  seeded diagnostic-mode data and required no auth (this repo runs in public/diagnostic mode:
  `requires_auth` is unset in `appPublicSettings`).
- **Checks per route** (run automatically across 2 Playwright projects — `mobile-compact` 390×844
  and `desktop-1280` 1280×800 — so 4 checks × 2 viewports = 8 assertions per route): axe-core
  critical/serious violations = 0, first-`Tab`-press focus outline visible, no horizontal overflow,
  every visible `<button>` ≥44px tall.
- **Scope vs. the full contract, explicitly:** `federation-design/test-harness/test-harness.contract.json`
  defines a full matrix of **6 viewports × 11 states × 2 themes = 132 cells** per route
  (`mobile-compact`, `mobile-wide`, `tablet`, `desktop`, `desktop-wide`, `wide` ×
  `populated`/`loading`/`empty`/`filtered_empty`/`error`/`stale`/`offline`/`degraded`/`partial`/`long_labels`/`keyboard_only`
  × `light`/`dark`). **This pass runs a deliberate subset: 2 viewports (`mobile-compact`,
  `desktop-1280`) × effectively 2 states (`populated` — the diagnostic-mode seed data every route
  loads into by default; and `keyboard_only`, exercised implicitly by the focus-visible check) × 1
  theme (`light`, the app's rendered default in this pass).** Running the full 132-cell matrix by
  hand for 5 routes in one pass is not feasible — it would require scripting each of the 9 remaining
  states per route (mocking loading/error/offline/stale/degraded/etc. responses), 4 more viewports,
  and a dark-theme pass, none of which this pass attempted. This is stated explicitly rather than
  silently; see Scope limitations below for what that leaves unverified.
- **Design-system cross-reference:** `docs/design-system-usage.json` independently found this
  repo's buttons are shadcn/ui primitives (`server/frontend/src/components/ui/button.jsx`), not
  `FederationButton` — its default/sm/lg/icon size variants are 36px/32px/40px/36px tall, all under
  the 44px contract minimum. That finding and this audit's touch-target results (below) corroborate
  each other independently.

### Harness-consumption note for this repo

thehub-pr's own `federation-design/test-harness/` ships the exact same class of check this audit
runs (see `docs/TEST_HARNESS_AUDIT.md` for the full write-up). As of this audit, this repo's
`desktop-build.yml` wires the harness's `desktop-setup.spec.js` against the **native** Setup &
Diagnostics screen (Linux leg only, gated to desktop-path-touching PRs/tags/dispatch — not normal
CI), and that run is clean (4/4 projects pass). But no repo, including this one, wires the harness's
`federation-smoke.spec.js` against the **web dashboard** this audit exercises — this document is, as
far as this audit could determine, the first automated a11y pass of any kind against thehub-pr's
live `server/frontend` app in this container.

## Per-route results

| Route | mobile-compact axe | desktop-1280 axe | keyboard-focus-visible | horizontal-overflow | touch-targets ≥44px |
|---|---|---|---|---|---|
| `/` | 1 critical | 1 critical, 1 serious | fails (see note) | pass | pass\* |
| `/hub` | 1 critical, 1 serious | 1 critical, 1 serious | fails (see note) | pass | pass\* |
| `/cases` | 1 critical | 1 critical, 1 serious | fails (see note) | pass | pass\* |
| `/crossover` | 3 critical, 1 serious (+1 more serious) | 2 critical, 1 serious | fails (see note) | pass (see note) | pass\* |
| `/research` | 1 critical | 1 critical, 1 serious | fails (see note) | pass | pass\* |

\* **The runner's touch-target and (partially) overflow results are false negatives, verified
independently — see the note below the table.** "pass" here reports exactly what the runner's
JSON/list output said; the note explains why that result understates real violations.

**Note — pre-hydration timing race in the shared runner's own test methodology (affects both
`keyboard-focus-visible` and, silently, `touch-targets`/`overflow`):** `federation-smoke.spec.js`'s
`page.goto(route)` uses Playwright's default wait condition (`'load'`), which fires before this
React SPA finishes hydrating and mounting its route content. Independently reproduced and confirmed
for every route above:

- **keyboard-focus-visible "fails"** because, at `'load'` time, nothing in the DOM is focusable yet
  — the first `Tab` press leaves `document.activeElement` on `<body>`, which `locator(':focus')`
  never finds within the 5s timeout. Re-checked after `waitForLoadState('networkidle')`: the first
  real Tab stop is a visible sidebar nav link with a clear `2px solid rgb(5, 41, 168)` outline. This
  is a **test-timing artifact, not a real missing-focus-style bug** — flagged in
  `docs/TEST_HARNESS_AUDIT.md` as a harness-spec gap.
- **touch-targets "passes" vacuously.** At `'load'` time `button:visible` count is **0** on every
  route tested (confirmed directly: `page.goto()` with no extra wait → `page.locator('button:visible').count()` → `0`), so the loop that checks each button's height never runs, and the assertion
  trivially passes. Re-checked after full hydration (`networkidle` + settle): **every single visible
  button on every route and both viewports is under 44px** — `/` 4-5 buttons all under, `/hub` 6-7,
  `/cases` 6-7, `/crossover` 14-15, `/research` 14-15, **100% of visible buttons across all 5 routes
  and 2 viewports fail the 44px minimum.** This matches `docs/design-system-usage.json`'s finding
  that this app's buttons come from `src/components/ui/button.jsx` (shadcn/ui default), whose size
  variants top out at 40px (`lg`) with the default at 36px (`h-9`) — none reach 44px by design.
  **This is a real, verified violation the runner's own timing masked; reported here as a Finding,
  not a pass.**
- **horizontal-overflow** is genuinely `false` (pass) for `/`, `/hub`, `/cases`, `/research` at
  desktop width and for `/`, `/hub`, `/cases` at mobile width, re-confirmed post-hydration. But at
  **mobile-compact (390px) width, `/crossover` and `/research` do overflow** (document scrollWidth
  523–714px vs. 390px clientWidth) — this was **not caught by the runner's own run** for the same
  pre-hydration-timing reason (checked at `'load'` time, before the overflowing content renders).
  Root cause identified: both pages render a shadcn `TabsList`
  (`inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1`, from
  `src/components/ui/tabs.jsx`) with several tab triggers that don't wrap or become scrollable at
  narrow widths — on `/research` it alone accounts for ~507px of un-wrapped width; on `/crossover`,
  a data `<table>` also extends past the viewport.

## Findings

Ordered by severity/impact.

1. **[Critical, sitewide] Unnamed Select filter controls — axe `button-name`.** Every route tested
   has at least one Radix Select combobox trigger (`src/components/ui/select.jsx`,
   `role="combobox"` on a `<button>`) that axe flags as having no discernible accessible name, even
   where the trigger visibly displays placeholder text like "All severities" / "All time" in a
   `<span>`. This reproduces on 5/5 routes (2 instances on `/`, `/hub`, `/cases`, `/research`; 5
   instances on `/crossover`, from its multiple filter dropdowns). Independently reproduced via the
   test-harness's own copy of `federation-smoke.spec.js` (see `docs/TEST_HARNESS_AUDIT.md` §3a) —
   same violation, same axe rule, same DOM shape. This is a known Radix-Select/axe interaction:
   `role="combobox"` buttons are evaluated by combobox naming rules rather than plain visible-text
   rules, so the inner `<span>` text isn't picked up as the accessible name. Fix is straightforward:
   add an explicit `aria-label` (e.g. "Filter by severity") to each `SelectTrigger` usage, or thread
   a `aria-labelledby` pointing at each filter's visible label.

2. **[Critical, sitewide, verified independently] Every visible button is under the 44px touch-target
   minimum.** See the table note above — this was masked by the shared runner's own pre-hydration
   timing on this pass's live run, but independently re-verified post-hydration: 100% of visible
   `<button>` elements across all 5 routes and both viewports (mobile and desktop) are 32–40px tall,
   against the contract's 44px CSS-px minimum. Root cause: `src/components/ui/button.jsx`'s cva size
   variants (`default: h-9`=36px, `sm: h-8`=32px, `lg: h-10`=40px, `icon: h-9 w-9`=36px) never reach
   44px — this is a systemic sizing choice in the shared local button primitive, not a per-page bug.
   Fixing it means either raising the default/sm/lg heights (impacts the whole app's density) or
   adding touch-target padding via `min-height`/hit-area tricks that don't change visual size.

3. **[Serious, desktop only] Insufficient color contrast — axe `color-contrast`.** Present on all 5
   routes at `desktop-1280` (not flagged at `mobile-compact`, because the mobile sidebar collapses
   and the offending elements aren't rendered/visible there). Two element families: sidebar section
   labels (`text-sidebar-foreground/60`, e.g. "OVERVIEW", "PRODUCERS", "FEDERATION", "RECORDS") and a
   secondary caption (`text-sidebar-foreground/50`). Both use a Tailwind opacity-modified foreground
   color that falls under WCAG's minimum contrast ratio against the sidebar background. On
   `/crossover`, an additional, larger instance affects the crossover table/card row labels
   (`.cursor-pointer > .whitespace-nowrap.font-medium`, 21 nodes) — same root cause, an
   opacity-reduced text color used for de-emphasis that also happens to fail contrast.

4. **[Critical, `/crossover` only] Two date inputs with no accessible label — axe `label`.**
   `<input type="date">` elements at `.w-[130px]` (2 nodes, both viewports) have no associated
   `<label>`, `aria-label`, or `aria-labelledby`. Likely a from/to date-range filter pair rendered
   without the same label wiring the rest of the filter row uses.

5. **[Serious, `/crossover`, mobile only] Scrollable region not keyboard-focusable — axe
   `scrollable-region-focusable`.** One `.overflow-auto` container on `/crossover` at 390px width is
   scrollable by mouse/touch but has no `tabindex` and isn't reachable by keyboard, so keyboard-only
   users can't scroll its content into view.

6. **[Serious, `/crossover` and `/research`, mobile only, not caught by the runner's own live run]
   Horizontal overflow from a non-wrapping tab bar.** See table note — `TabsList`
   (`src/components/ui/tabs.jsx`) doesn't wrap or scroll at 390px width, pushing the document
   133–324px wider than the viewport. On `/crossover` a data table compounds it. Real users on
   narrow viewports get horizontal scroll/clipped content on these two routes; the contract requires
   `horizontalOverflow: false` unconditionally.

7. **[Informational — test-methodology, not an app bug] `federation-smoke.spec.js`'s default
   `page.goto()` wait races this SPA's hydration**, producing both a false failure
   (keyboard-focus-visible) and false passes (touch-targets, and overflow on the two routes that do
   overflow). Documented in full, with root-cause verification, in `docs/TEST_HARNESS_AUDIT.md` §3a
   and flagged there as a harness-spec gap (recommend the spec wait for `networkidle` or a
   render-complete signal before running its Tab/button/overflow checks).

## Scope limitations

- **Only 1 of the contract's 11 states was actually exercised** (`populated`, since every route's
  diagnostic-mode seed data loads real rows by default) plus `keyboard_only` implicitly via the
  focus check. `loading`, `empty`, `filtered_empty`, `error`, `stale`, `offline`, `degraded`,
  `partial`, and `long_labels` were **not** scripted or checked on any route in this pass — each
  would require mocking specific API responses or UI states per page, which this pass did not
  attempt.
- **Only 2 of the contract's 6 viewports** were run (`mobile-compact` 390×844, `desktop` 1280×800).
  `mobile-wide` (430×932), `tablet` (768×1024), `desktop-wide` (1440×900), and `wide` (1920×1080)
  were not checked. Given finding 6 (mobile-only horizontal overflow), it's plausible `mobile-wide`
  would show similar or different overflow behavior at 430px — not verified.
- **Only the light theme was checked.** This repo defaults to dark theme
  (`docs/design-system-usage.json`: `themeSupport.defaultTheme: "dark"`) and ships a reachable
  toggle, but this pass's axe/keyboard/overflow/touch-target runs were all against whatever the
  runner's default page state rendered, which resolved to light in this environment (no explicit
  `prefers-color-scheme` set for the headless browser, and no stored `localStorage` preference on a
  fresh profile — `resolveInitialTheme()` in `src/lib/theme.jsx` falls back through OS preference
  before its own dark default). The design-system-usage.json screenshots separately captured both
  themes for visual reference, but no axe/keyboard/overflow pass was run against dark.
- **Only 5 of the app's ~27 routed pages** were scanned (see `src/App.jsx` for the full route
  table — `/programs`, `/apps`, `/operations`, `/sources`, `/tasks`, `/gates`, `/integrations`,
  `/exports`, `/readiness`, `/transition`, `/anomaly-overlap`, `/control`, `/project-signs`,
  `/dictionary`, `/manifest`, `/spiderweb`, `/ovnis`, `/aguayluz`, `/moneysweep`, `/skywatcher`,
  `/centinelas` were not scanned in this pass). The 5 chosen routes were picked to be representative
  (landing/list/CRUD/dense-filter/chat-style), not exhaustive — findings 1–3 recur across every route
  checked, so it is likely (not confirmed) that the unscanned routes share at least the sitewide
  Select-naming, button-height, and sidebar-contrast findings, since all three trace to shared layout
  chrome or shared UI primitives rather than per-page code.
- **No authenticated/role-gated states were checked** — this repo runs in diagnostic/public mode
  with `requires_auth` unset, so `/login`, `/register`, and the auth-guarded variant of the app shell
  were out of scope for this pass.
- Nothing was blocked by missing data or auth for the 5 routes actually scanned — all resolved with
  diagnostic-mode seed content.
