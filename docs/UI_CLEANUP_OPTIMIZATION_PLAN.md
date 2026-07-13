# thehub-pr UI Cleanup & Optimization Plan

Scope: the single hub app frontend at `server/frontend` (React 18 + Vite + Tailwind +
Radix/shadcn), which the FastAPI backend serves alongside the JSON API. This plan targets
**app design and interactive workflow** — navigation/IA, dead code, bundle weight,
design-system consistency, accessibility, and interaction correctness. It refines and
localizes the federation-wide contracts in
[`FEDERATION_DESIGN_SYSTEM_V1.md`](FEDERATION_DESIGN_SYSTEM_V1.md) and
[`FEDERATION_FRONTEND_STACK_AUDIT_V1.md`](FEDERATION_FRONTEND_STACK_AUDIT_V1.md); `thehub-pr`
is the reference implementation, so cleanup here sets the pattern the other repos migrate to.

It does **not** change API contracts, data shapes, or the producer/hub boundary.

---

## 1. Findings (current state)

Evidence gathered from the working tree. File references are clickable.

### A. Navigation & information architecture — highest-impact

| # | Finding | Evidence |
|---|---|---|
| A1 | **~9 routed pages are orphaned** — no sidebar entry, no mobile-nav entry, and no in-app link. Reachable only by typing the URL. | `Programs`, `Cases`, `Sources`, `Integrations`, `Exports`, `ModuleReadiness`, `Dictionary`, `Manifest` are defined only in [`App.jsx`](../server/frontend/src/App.jsx); `Gates`/`Tasks` each have exactly one stray link. The sidebar exposes only Recent Activity, Hub, and the 6 modules ([`Sidebar.jsx`](../server/frontend/src/components/layout/Sidebar.jsx)). |
| A2 | **Duplicate reachability.** Dashboard, Crossover, Anomaly Overlap, Transition Audit, Research, Control Ledgers each exist as a **standalone route** (`/crossover`, `/anomaly-overlap`, …) **and** as an embedded tab inside `/hub`. Two URLs render the same content. | Routes in [`App.jsx`](../server/frontend/src/App.jsx); tab set in [`Hub.jsx`](../server/frontend/src/pages/Hub.jsx). |
| A3 | **`embedded` prop is honored by only one of six Hub tabs.** `Hub` renders `<Active embedded />`, but only `ControlLedgers` reads it. The other five render their full standalone header + page padding inside the Hub shell → doubled headers and inconsistent nesting. | `grep embedded` → only [`ControlLedgers.jsx`](../server/frontend/src/pages/ControlLedgers.jsx) + [`Hub.jsx`](../server/frontend/src/pages/Hub.jsx). |
| A4 | **Auth pages are unrouted.** `Login`, `Register`, `ResetPassword`, `ForgotPassword`, `ProtectedRoute` exist but are not mounted in the `<Routes>` tree. `auth.redirectToLogin()` sends the browser to `/login`, which the SPA catch-all resolves to `PageNotFound`. | Auth pages under `src/pages/`; router in [`App.jsx`](../server/frontend/src/App.jsx) has no `/login` etc.; redirect in [`federationClient.js`](../server/frontend/src/api/federationClient.js). |
| A5 | **Dead import.** `Dashboard` is imported into `App.jsx` but never routed (it renders only via Hub). | [`App.jsx:10`](../server/frontend/src/App.jsx). |

### B. Dead code & dependency bloat

| # | Finding | Evidence |
|---|---|---|
| B1 | **~35 of ~48 shadcn UI primitives have zero imports** outside `components/ui/` itself. | e.g. `accordion`, `alert*`, `avatar`, `badge`, `breadcrumb`, `calendar`, `carousel`, `chart`, `checkbox`, `collapsible`, `command`, `context-menu`, `drawer`, `dropdown-menu`, `form`, `hover-card`, `menubar`, `navigation-menu`, `pagination`, `popover`, `progress`, `radio-group`, `resizable`, `scroll-area`, `slider`, `toggle*`. |
| B2 | **A second, unused 626-line sidebar system** ships in the bundle. The app uses the custom `layout/Sidebar.jsx`; the shadcn `ui/sidebar.jsx` (626 lines) is never imported. | [`ui/sidebar.jsx`](../server/frontend/src/components/ui/sidebar.jsx). |
| B3 | **7 npm dependencies with zero source imports:** `moment`, `@stripe/react-stripe-js`, `@stripe/stripe-js`, `canvas-confetti`, `react-quill`, `lodash`, `framer-motion`, `html2canvas`. (Stripe/confetti are template leftovers unrelated to an intelligence control plane.) | `grep` across `src`. |
| B4 | **Three overlapping toast systems** coexist: `sonner` (5 files), `react-hot-toast` (1 file), and the Radix `toast`/`use-toast`/`toaster` stack. Only one should remain. | `grep` across `src`. |
| B5 | **Single-consumer feature libs** pulled in for one dead UI primitive each: `embla-carousel-react` (only `carousel.jsx`), `react-day-picker` (only `calendar.jsx`), `input-otp` (1 real use). | `grep` across `src`. |
| B6 | **`next-themes` is loaded only to power `ui/sonner.jsx`**, itself unused, in an app with a single hard-coded dark theme. | [`ui/sonner.jsx:2`](../server/frontend/src/components/ui/sonner.jsx). |

### C. Design-system consistency

| # | Finding | Evidence |
|---|---|---|
| C1 | **Hard-coded semantic status colors** (`text-red-300`, `bg-emerald-400`, `bg-red-500/20`, …) are used directly in views, which `FEDERATION_DESIGN_SYSTEM_V1.md` explicitly prohibits ("semantic tokens only"). | [`RecentActivity.jsx`](../server/frontend/src/pages/RecentActivity.jsx), accent palette in [`federation.js`](../server/frontend/src/lib/federation.js), status maps in [`chips.js`](../server/frontend/src/lib/chips.js). |
| C2 | **Two near-identical page headers** (`PageHeader`, `ModulePageHeader`) with divergent markup. | [`shared/PageHeader.jsx`](../server/frontend/src/components/shared/PageHeader.jsx), [`shared/ModulePageHeader.jsx`](../server/frontend/src/components/shared/ModulePageHeader.jsx). |
| C3 | **Render-blocking Google Fonts `@import`** in CSS contradicts the repo's offline-safe / sanitized posture and adds a third-party request to first paint. | [`index.css:1`](../server/frontend/src/index.css). |
| C4 | **Duplicated `:root` and `.dark` token blocks** are byte-identical; the theme plumbing implies a toggle that does not exist. | [`index.css`](../server/frontend/src/index.css). |

### D. Accessibility (design-system AA gates, currently unmet)

| # | Finding | Evidence |
|---|---|---|
| D1 | Icon-only / dot-only controls lack accessible names (mobile menu button, accent-dot nav items). | [`MobileNav.jsx`](../server/frontend/src/components/layout/MobileNav.jsx), [`Sidebar.jsx`](../server/frontend/src/components/layout/Sidebar.jsx). |
| D2 | Loading spinner has no `role="status"` / `aria-live`; multiple `animate-spin` / `animate-pulse` with no `prefers-reduced-motion` fallback. | [`App.jsx`](../server/frontend/src/App.jsx), [`RecentActivity.jsx`](../server/frontend/src/pages/RecentActivity.jsx). |
| D3 | No semantic landmarks beyond a single `<main>`; nav is not wrapped/labeled consistently. | layout components. |

### E. Performance

| # | Finding | Evidence |
|---|---|---|
| E1 | **No route-level code splitting.** Every page is statically imported in `App.jsx`, so heavy libs (`leaflet` ×3, `recharts` ×3, `three`, `jspdf`) all land in the initial bundle even for users who only view Recent Activity. | [`App.jsx`](../server/frontend/src/App.jsx). |
| E2 | Recent Activity polls three entities every 30s and merges client-side; correct but a candidate for one server-side activity endpoint later. | [`RecentActivity.jsx`](../server/frontend/src/pages/RecentActivity.jsx). |

### F. Testing / verification

| # | Finding | Evidence |
|---|---|---|
| F1 | **Zero frontend tests.** The design-system verification matrix requires unit/integration, axe, keyboard smoke, and visual-regression baselines; none exist. | no `*.test.*` under `server/frontend/src`. |

---

## 2. Goals & non-goals

**Goals**
- Every routed page is reachable through visible, grouped navigation.
- One canonical URL per surface; no accidental duplicate-content routes.
- Remove dead components and dependencies; shrink the initial bundle.
- Status/domain color flows through semantic tokens only.
- Meet the WCAG 2.2 AA gates the design system already mandates.
- Establish a minimal but real frontend test/CI floor.

**Non-goals**
- No changes to the API, entity schemas, ingest adapters, or hub/producer boundary.
- No visual redesign or rebrand — the dark control-plane identity stays.
- No new product features; this is cleanup + optimization only.

---

## 3. Workstreams (prioritized)

### P0 — Navigation & workflow correctness

1. **Restructure the sidebar into labeled groups** so every page has a home. Proposed groups (from existing routes):
   - **Overview** — Recent Activity, Hub
   - **Producers** — the 6 module pages (unchanged)
   - **Federation** — Crossover, Anomaly Overlap, Transition Audit, Module Readiness, Control Ledgers
   - **Records** — Programs, Cases, Sources, Tasks, Gates, Exports, Dictionary, Manifest
   - **Tools** — Research Assistant, Integrations

   Encode this as one `NAV` config consumed by **both** `Sidebar.jsx` and `MobileNav.jsx` (they currently duplicate the module list). Add a collapsed/scrollable treatment for the longer list.

2. **Resolve the Hub-vs-route duplication (A2/A3).** Decide one model and apply it consistently:
   - *Recommended:* keep the standalone routes as canonical; make `/hub` a lightweight launcher/overview that links to them, and delete the embedded-tab rendering. This removes the half-implemented `embedded` prop entirely.
   - *Alternative:* keep Hub as the tabbed container and make the standalone routes redirect into `/hub?tab=…`; then every embedded page must actually honor `embedded` (suppress its own `PageHeader`/padding). This is more work and keeps two code paths.
   Pick one; do not leave both.

3. **Mount or externalize the auth routes (A4).** Either add `/login`, `/register`, `/forgot-password`, `/reset-password` (+ `ProtectedRoute`) to the router, or, if auth is handled entirely server-side, delete the orphaned pages and point `redirectToLogin` at the real endpoint. Today `/login` 404s inside the SPA.

4. **Drop the dead `Dashboard` import from `App.jsx` (A5)** and collapse the `/` + `/activity` duplication to a single canonical path with a redirect.

### P1 — Dead code & dependency removal

5. **Prune unused shadcn primitives (B1/B2).** Remove `ui/*.jsx` files with zero imports, including the 626-line `ui/sidebar.jsx`. Keep the ~13 in use (`button`, `tabs`, `select`, `input`, `label`, `table`, `card`, `textarea`, `dialog`, `sheet`, `separator`, `skeleton`, `tooltip`, plus toast — see #7). Verify with a codemod/grep gate so nothing transitively required is dropped.

6. **Remove zero-import dependencies (B3)** from `package.json`: `moment`, `@stripe/*`, `canvas-confetti`, `react-quill`, `lodash`, `framer-motion`, `html2canvas`; plus `embla-carousel-react`, `react-day-picker`, and `next-themes` once their sole consumers (`carousel`, `calendar`, `sonner`) are removed (B5/B6). Re-run `npm ci && build` to confirm.

7. **Consolidate to one toast system (B4).** Standardize on the Radix `use-toast`/`toaster` already wired in `App.jsx`, migrate the 5 `sonner` call-sites and 1 `react-hot-toast` call-site, then drop `sonner` and `react-hot-toast`.

### P2 — Design-system consistency

8. **Tokenize status & domain accents (C1).** Move raw palette classes into semantic tokens (extend `styles/federation.css` + `federation.tokens.json`) and have `chips.js` / `federation.js` reference token classes, satisfying the "no hard-coded semantic colors" gate.

9. **Unify the two headers (C2)** into one `PageHeader` with an optional accent/badge slot; `ModulePageHeader` becomes a thin preset.

10. **Self-host fonts and de-duplicate theme tokens (C3/C4).** Vendor Inter + JetBrains Mono locally (removes the render-blocking third-party `@import`); collapse the identical `:root`/`.dark` blocks.

### P3 — Accessibility

11. Add `aria-label`s to icon/dot-only controls; wrap nav in labeled `<nav>` landmarks; give the spinner `role="status"`; add a global `prefers-reduced-motion` rule that disables `animate-*` (D1–D3). Gate with `axe` in CI.

### P4 — Performance

12. **Route-level code splitting (E1).** Convert `App.jsx` page imports to `React.lazy` + `<Suspense>` so Leaflet/Recharts/three/jspdf load only on the pages that use them. Measure initial bundle before/after.

### P5 — Test & CI floor

13. Add Vitest + React Testing Library with a smoke test per top-level route (renders without crash, key controls reachable), an `axe` pass on 3 primary pages, and wire `lint → typecheck → test → build` into CI, matching the design-system verification matrix (F1).

---

## 4. Sequencing

```
P0 (nav/workflow correctness)  →  P1 (dead code/deps)  →  P2 (tokens/consistency)
        │                                                        │
        └───────────────►  P5 (tests/CI floor) runs alongside ◄──┘
                           P3 (a11y) + P4 (perf) land after P1 shrinks the surface
```

P0 first (it fixes broken/undiscoverable workflows and is low-risk). P1 next (smaller surface
makes every later step cheaper). P5 should be stood up early enough to guard P1–P4 regressions.

## 5. Verification (per PR)

Mirror the design-system matrix, scoped to `server/frontend`:

| Gate | Required |
|---|---|
| API/entity contracts unchanged | Yes |
| Every route reachable from nav | Yes (P0) |
| No duplicate-content routes | Yes (P0) |
| Zero-import UI files / deps removed | Yes (P1) |
| Hard-coded semantic status colors | 0 outside tokens (P2) |
| `axe` critical/serious violations | 0 (P3) |
| Initial JS bundle | Reduced vs. baseline (P1+P4) |
| Lint / typecheck / test / build | Pass (P5) |
| Widths 768 / 1280 / 1440 / 1920 | Pass |

## 6. Risks & mitigations

- **Pruning something transitively used** → drive removals by a grep/knip gate + a green `build`, one category per commit, not a bulk delete.
- **Auth-route decision needs product input** (A4) → treat #3 as a decision point; the rest of P0 is independent and can land first.
- **Token migration touching many files** (P2) → codemod the palette-class → token-class mapping; land behind the P5 smoke tests.
- **Bundle-split regressions** (P4) → add `Suspense` fallbacks and verify each lazy route renders before merge.

## 7. Suggested first PR (smallest safe slice)

Bundle the zero-risk items: remove the dead `Dashboard` import (A5), delete zero-import
`ui/*` files incl. `ui/sidebar.jsx` (B1/B2), drop the 7 zero-import deps (B3), and add the
grouped `NAV` config wired into both `Sidebar` and `MobileNav` (A1). No behavior change for
existing links; large dead-weight reduction; unblocks the rest.
