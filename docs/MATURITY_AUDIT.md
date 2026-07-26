# thehub-pr — Professional Maturity Audit

**Date:** 2026-07-26 · **Method:** static review **plus execution** — every number below
came from running the code in a clean container (Python 3.11.15, Node v22.22.2), not from
reading it. Commands and raw output are named inline so any claim can be re-checked.

Scope: this repository only. Cross-repo comparisons live in
[`FEDERATION_MATURITY_AUDIT.md`](FEDERATION_MATURITY_AUDIT.md).

---

## Scorecard

Scored 0–4. 4 = would pass review at a team that ships this for a living.

| Dim | Area | Score | Evidence |
|---|---|---|---|
| D1 | Functional completeness | **3** | `hub` CLI has 10 real subcommands; 24 API routes serve; auth surface was dead (fixed below) |
| D2 | Data reality | **1** | `data/` is 8 KB — the aggregate has never been run in-tree, so most UI pages render empty |
| D3 | UI craft | **4** | 28 pages on shared primitives; 30 files handle empty states, 22 handle loading; only repo in the federation with an automated a11y test |
| D4 | Test & CI coverage | **4** | `388 passed` (pytest, 6.3s) + `16 passed / 7 files` (vitest); Playwright visual harness present |
| D5 | Engineering hygiene | **3** | ruff+mypy clean on enforced scope (`mypy`: 50 files, no issues) — but `server/` is outside that scope and `npm run typecheck` reports 831 errors that no workflow runs |
| D6 | Doc accuracy | **3** | README pointed at a symbol that does not exist (fixed below); otherwise accurate and unusually thorough |

**Overall: the strongest engineering surface in the federation, starved of data.**
The hub is the only node with frontend tests, the only one with an a11y gate, and its UI
architecture is genuinely good. Its problem is not craft — it is that `hub aggregate` has
never been run into `data/hub.db`, so most of that craft renders blank.

---

## What is fully developed vs. what is not

**PRODUCTION** — real behaviour, tested, CI-gated, docs match.

| Module | Evidence |
|---|---|
| `src/hub/cli.py` | 10 subcommands (`list`, `validate-manifest`, `validate-package`, `validate-federation`, `fetch`, `aggregate`, `correlate`, `ingest`, `graph-report`, `maintenance`) |
| `src/hub/aggregate.py`, `correlate.py`, `validate.py`, `registry.py`, `manifest.py` | covered by the 388-test suite; mypy-clean |
| `src/hub/ingest.py` | `ingest_aggregate` + `_project_ui` + four `project_*` helpers (`:111`, `:254`, `:305`, `:396`, `:567`, `:629`) |
| `server/backend/notifications.py` | pure decision logic, unit-tested, thin HTTP surface over it |
| `packages/prii_export_utils`, `packages/prii_maintenance` | shared libs; ruff+mypy gated in CI; consumed by five producers |
| `server/frontend` shared primitives | `PageHeader`, `FilterBar`, `SearchableTable`, `RecordSheet`, `StatusChip`, `EmptyState` — one consistent CRUD pattern across 28 pages |

**FUNCTIONAL** — works, but thinly tested or undocumented.

| Module | Gap |
|---|---|
| `server/backend/main.py` | 24 routes, serves correctly — but sits outside the ruff/mypy scope CI enforces |
| `server/backend/mcp_api.py` (153 loc) | no direct test module |
| `federation-design/packages/react` | 120 LOC published as a versioned tarball; six producers depend on it, this repo does not (see below) |

**SCAFFOLD** — structure present, behaviour incomplete.

| Item | Why |
|---|---|
| 18 of 23 UI collections | The UI reads `UnifiedCases`, `AnomalyFlags`, `Contracts`, `Vendors`, `AirspaceEvents`, `FederationTasks`, `ValidationGates`, `ContinuityRisks`, `LiveFeedItems`, `IntegrationStatus`, `InfrastructureAssets`, `GovernanceAlerts`, `FederationManifest`, `LiveFeedSources`, `LiveFeedRuns`, `EvidenceStandards`, `DictionaryTerms`, `CorrelationReviews`. `ingest.py` projects only a subset; the rest have no producer path and render empty. |
| `/api/files/upload` | returns `_diagnostic_stub(...)` — a placeholder, correctly labelled |
| `/api/connectors/{name}/connection` | hardcoded `{"status": "not_connected"}` |

**DEAD** — reachable UI with no working implementation. *Fixed in this PR.*

| Item | Proof |
|---|---|
| Login / Register / ForgotPassword / ResetPassword | `federationClient.js` posts to `/auth/login`, `/auth/register`, `/auth/verify-otp`, `/auth/password/reset-request`, `/auth/password/reset`, `/auth/resend-otp`. **All six returned HTTP 404** when probed against a live server. `/api/auth/me` returns 401 `"No auth in diagnostic mode"`; `/api/apps/public-settings` reports `requires_auth: false`, so `ProtectedRoute` never engaged and the forms were reachable but inert. |

---

## UI feature matrix

28 pages. All are built on the same shared primitives and handle loading and empty states —
the craft is uniform. What varies is whether anything is behind them.

| Page group | Backing collections | Renders data today? |
|---|---|---|
| Programs, Hub | `Programs` (seeded from `registry/producers.yaml` at startup) | **Yes** — the seed path works |
| Sources, Spiderweb graph, crossover | `UnifiedSources`, `GraphNodes`, `GraphEdges`, `CrossoverLinks` | **Only after** `hub aggregate && hub correlate && hub ingest`; empty in-tree |
| Cases, Tasks, Gates, Integrations, Dictionary, Manifest, ControlLedgers, ModuleReadiness, TransitionAudit, AnomalyOverlap, RecentActivity, Exports, ResearchAssistant | `UnifiedCases`, `FederationTasks`, `ValidationGates`, `AnomalyFlags`, … | **No** — no ingest path populates these |
| Per-producer pages (MoneySweep, Skywatcher, AguaYLuz, Ovnis, Centinelas, Spiderweb) | domain collections | **No** — README is candid that these "stay empty until producers emit that data" |
| Login, Register, ForgotPassword, ResetPassword | none | **No** — dead, now gated |

The README's own framing is accurate and worth keeping: domain-heavy pages stay empty until
producers emit the fields. The audit's only quarrel is the ratio — 28 pages, ~5 with a live
data path.

---

## Fixes applied in this PR

**1. Auth routes no longer render when there is nothing to authenticate against.**
`server/frontend/src/App.jsx` already computed `authRequired` from
`appPublicSettings?.public_settings?.requires_auth || appParams.requireAuth` to decide
whether to wrap the shell in `ProtectedRoute`. The four auth routes ignored it. They now
use the same flag: rendered when auth is required, redirected to `/` when it is not. One
existing variable, no new state, no backend change — the shell can no longer contradict
itself. Verified: `npm run lint` clean, `npm run build` clean, `npm run test` 16/16.

**2. Mutating API routes refuse unauthenticated non-loopback callers.**
`server/backend/main.py` gains `require_write_access` on `POST`/`PATCH`/`DELETE`
`/api/entities/*` and the notification write routes:

- `PRII_WRITE_TOKEN` set → `Authorization: Bearer <token>` required (`secrets.compare_digest`)
- `PRII_WRITE_TOKEN` unset → writes served to loopback only; a startup warning is logged

Reads are untouched, and the documented single-operator loopback workflow is unchanged.
This matters because the repo ships a `Dockerfile` and `docker-compose.yml`, so
"it only listens on localhost" was never structurally guaranteed. Verified by booting the
server on `0.0.0.0` and probing from a non-loopback address:

| Condition | Expected | Observed |
|---|---|---|
| no token, loopback write | 200 | **200** |
| no token, remote write | 403 | **403** |
| no token, remote **read** | 200 | **200** |
| token set, correct bearer | 200 | **200** |
| token set, wrong bearer | 401 | **401** |
| token set, no bearer | 401 | **401** |

**3. README drift corrected.** `README.md:92` told readers the collection mapping lives in
`COLLECTION_ADAPTERS` in `src/hub/ingest.py`. That symbol does not exist — `grep -rn
COLLECTION_ADAPTERS` matched only the README line itself. It now names the functions that
do exist, each verified to resolve: `ingest_aggregate` (`ingest.py:629`), `_project_ui`
(`:567`), `project_producer_collections` (`:254`), `project_crossover_links` (`:111`),
`project_continuity_risks` (`:305`), `project_livefeed` (`:396`).

Regression check after all three: `388 passed` (unchanged), vitest `16 passed` (unchanged),
`npm run build` clean, `npm run typecheck` 831 errors **before and after** — identical, my
changes add none.

---

## Backlog, ranked

| # | Item | Effort | Why it matters |
|---|---|---|---|
| 1 | Run `hub aggregate && hub correlate && hub ingest` in CI and commit a fixture DB, or ship a seeded demo DB | **M** | The single highest-leverage change here. 23 pages of good UI currently prove nothing because there is no data behind them. |
| 2 | Decide the auth story: implement `/auth/*` for real, or delete the four auth pages | **L** / **S** | This PR stops the forms from lying. It does not decide which way you go. |
| 3 | `POST /api/entities/{name}` returns **HTTP 500 on a duplicate id** | **S** | Verified: two POSTs with `id: "DUP-TEST-001"` → first 200, second 500. `create_entity` uses a bare `INSERT`; a `UNIQUE` violation escapes as an unhandled `sqlite3.IntegrityError`. Should be 409. |
| 4 | Bring `server/` into the ruff+mypy scope CI enforces | **S** | CI lints `packages/` and `src/hub` only. `server/` — 937 LOC including all the HTTP surface — is unchecked. |
| 5 | Either run `npm run typecheck` in CI or stop shipping the script | **M** | 831 errors, zero of them enforced. A green-looking script that no gate runs is worse than no script. |
| 6 | Prune UI collections with no ingest path, or mark them "awaiting producer" in the UI | **M** | Distinguishes "no data yet" from "broken" for an operator. |
| 7 | Reconcile `requires_auth` vs `auth_required` naming across the federation | **S** | `thehub-pr`/`skywatcher-pr` use `requires_auth`; `centinelas-pr` uses `auth_required`. Same concept, two keys. |

**Not a defect, recorded so it stops being re-litigated:** this repo publishes
`@pr-federation/react` but does not consume it — `server/frontend/src/lib/theme.jsx` vendors
the tokens locally so the app builds standalone, and `src/styles/federation.sync.test.js`
fails if the two drift. That is a deliberate, tested trade-off, not an oversight.
