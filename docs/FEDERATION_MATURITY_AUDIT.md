# PRII Federation — Professional Maturity Audit (rollup)

**Date:** 2026-07-26 · **Scope:** all seven repositories · **Method:** static review **plus
execution**. Every figure was produced by running the code in a clean container (Python
3.11.15, Node v22.22.2), using each repo's own documented setup command. Per-repo detail
lives in each repository's `docs/MATURITY_AUDIT.md`.

---

## The one-paragraph answer

The federation's Python engineering is genuinely good and its user interfaces are not
finished. All seven test suites pass — **5,095 tests green across the federation**, from
72 in `ovnis-pr` to 2,394 in `moneysweep-pr` — and all seven frontends build and lint clean.
What separates "professional" from "could be professional" here is not code quality; it is
three things: **UI coverage is wildly out of proportion to backend size**, **quality gates
are enforced on a fraction of the code in three repos**, and **three repos shipped login
screens that cannot authenticate anyone** — one of which grants admin access to any visitor.
That last item was the most severe finding and has been fixed in this audit round.

---

## Federation scorecard

Scored 0–4 per dimension. See each repo's own audit for the evidence behind every cell.

| Repo | D1 Function | D2 Data | D3 UI | D4 Tests | D5 Hygiene | D6 Docs | Total |
|---|---|---|---|---|---|---|---|
| `aguayluz-pr` | 4 | 4 | 3 | 4 | 4 | 4 | **23** |
| `thehub-pr` | 3 | 1 | 4 | 4 | 3 | 3 | **18** |
| `moneysweep-pr` | 4 | 3 | 1 | 4 | 4 | 3 | **19** |
| `spiderweb-pr` | 4 | 3 | 0 | 4 | 2 | 4 | **17** |
| `skywatcher-pr` | 3 | 1 | 4 | 3 | 1 | 4 | **16** |
| `centinelas-pr` | 3 | 2 | 3 | 3 | 3 | 4 | **18** |
| `ovnis-pr` | 3 | 4 | 2 | 2 | 1 | 3 | **15** |

**`aguayluz-pr` is the reference node** — real data, a UI proportionate to its backend, the
widest lint rule set in the federation, and honest caveats. When settling a "how should we do
this?" argument, it is the one to copy.

---

## Verified baseline

| Repo | Python tests | Frontend | UI pages | Py LOC | Lint gate coverage |
|---|---|---|---|---|---|
| `moneysweep-pr` | **2394 passed**, 8 skipped · 51.74% cov | builds clean | 1 | 145,896 | full repo + format + mypy + pre-commit |
| `spiderweb-pr` | **989 passed**, 31 skipped | builds clean, **no lint script** | 0 | 53,758 | **13 of 311 files (4%)** |
| `skywatcher-pr` | **807 passed**, 13 skipped | builds clean | 15 | 51,543 | **none** |
| `thehub-pr` | **388 passed** · +16 frontend | builds clean, **16 tests** | 28 | 15,898 | `packages/` + `src/hub` only |
| `aguayluz-pr` | **306 passed** | builds clean | 11 | 14,024 | full repo (`E,F,I,B,UP,SIM,W`) |
| `centinelas-pr` | **139 passed** | builds clean | 16 | 5,446 | full repo (`E4,E7,E9,F`) |
| `ovnis-pr` | **72 passed** | builds clean | 1 | 3,812 | **none** |

---

## Gaps that only appear in comparison

### 1. Authentication: three repos, three different broken states

Probed live — every backend booted under uvicorn and interrogated.

| Repo | Auth UI | Backend reality | Verdict |
|---|---|---|---|
| `centinelas-pr` | 4 pages + Google button | **No `/auth/*` route exists.** `appClient.js` fakes auth in `localStorage`: `loginViaEmailPassword(email)` takes **no password argument**, `verifyOtp` accepts any code, and `me()` returns `{role: "admin"}` by default — a visitor who never logs in is already an admin. Declares `PRODUCTION`. | **Most severe.** Fixed. |
| `skywatcher-pr` | 4 pages + Google button | All six `/auth/*` endpoints the UI calls returned **404**; `/api/auth/me` returns 401. No `ProtectedRoute` at all. | Dead UI. Fixed. |
| `thehub-pr` | 4 pages + Google button | All six returned **404**; `/api/auth/me` 401; `requires_auth: false` so `ProtectedRoute` never engaged. | Dead UI. Fixed. |
| `aguayluz-pr` | none | exposes an unused `GET /auth/status` | Honest |
| `moneysweep-pr`, `ovnis-pr`, `spiderweb-pr` | none | none | Honest |

Three repos also disagree on the config key for the same concept: `requires_auth`
(`thehub-pr`, `skywatcher-pr`) vs `auth_required` (`centinelas-pr`).

### 2. Unauthenticated writes on the two generic entity stores

Only `thehub-pr` and `skywatcher-pr` implement the generic `/api/entities/{name}` contract.
Both accepted an unauthenticated `POST` and **persisted the row** — verified by follow-up
`GET`. `thehub-pr` writes to `data/hub.db` on disk and ships a `Dockerfile` and
`docker-compose.yml`, so the loopback assumption was never structurally enforced.
`skywatcher-pr`'s writes are in-memory only. Both fixed.

The other five backends implement domain REST APIs and returned 404 for `/api/entities/*`.
Their own mutating routes were **not** write-probed — `aguayluz-pr` has 6
(including `/admin/run-export`), `spiderweb-pr` 4, `centinelas-pr` 2. That is open follow-up
work, flagged in those repos' backlogs.

### 3. The backends do not share an API contract

The federation is described as one system, but its seven backends speak three languages:

- **Generic entity store** (`/api/entities/{name}`, `/api/apps/public-settings`,
  `/api/auth/me`): `thehub-pr`, `skywatcher-pr`
- **Domain REST, no `/api` prefix**: `aguayluz-pr` (`/assets`, `/municipios.geojson`,
  `/events/stream`), `spiderweb-pr` (`/agencies`, `/vendors`, `/sites`), `centinelas-pr`
  (`/items`, `/queue`), `moneysweep-pr` (`/contracts`, `/edges`), `ovnis-pr` (`/cases`,
  `/candidates`)
- **A third auth shape**: `aguayluz-pr`'s `/auth/status`

This is defensible — producers own their domains — but it means the shared
`federationClient.js` only works for two of seven nodes, and the other five each carry their
own `lib/api.js`. Worth an explicit decision rather than drift.

### 4. UI coverage is inverse to backend size

| Repo | Py LOC | UI pages | LOC per page |
|---|---|---|---|
| `moneysweep-pr` | 145,896 | **1** | 145,896 |
| `spiderweb-pr` | 53,758 | **0** | — |
| `skywatcher-pr` | 51,543 | 15 | 3,436 |
| `thehub-pr` | 15,898 | 28 | 568 |

The two largest backends have the least UI; the smallest backend has the most. `thehub-pr`
has 28 well-built pages and 8 KB of data behind them; `moneysweep-pr` has 17 MB of data and
one page. **The federation's UI effort is pointed at the node with the least to show.**

`spiderweb-pr` is the sharpest case: three parallel frontends (`server/frontend` TypeScript
with 0 pages, `dashboard/` vanilla JSX, `workbench/priis-v1/app`), none complete, one with no
ESLint config at all.

### 5. Frontend testing barely exists

`thehub-pr` is the only repo with any frontend test infrastructure — vitest, Playwright,
Testing Library, and `vitest-axe`, 16 tests passing. The other six have **no test runner in
`package.json`**, covering 24.7k LOC of untested UI between them. `thehub-pr`'s setup is a
working in-house template.

### 6. Type checking is configured and unenforced

`npm run typecheck` exists in `thehub-pr` (**831 errors**) and `skywatcher-pr` (**229 errors**)
and is run by **no workflow in either**. A script that always fails and never gates is worse
than no script — it trains people to ignore it.

### 7. The code lives in `scripts/`

| Repo | `scripts/` LOC | package LOC | ratio |
|---|---|---|---|
| `moneysweep-pr` | 81,709 (312 files) | 25,708 | 3.2× |
| `spiderweb-pr` | 11,987 (70 files) | 1,592 | 7.5× |
| `skywatcher-pr` | 10,306 (53 files) | 4,343 | 2.4× |

Loose scripts are hard to import, test, and type-check. This is the structural cause of
`moneysweep-pr`'s own finding that **60 of 231 modules are "structurally identical to
merge-target siblings"** — duplication is the path of least resistance when there is no
package boundary to put shared code behind.

### 8. Declared status vs. observed reality

| Repo | Declares | Observed |
|---|---|---|
| `centinelas-pr` | `PRODUCTION` | 304 KB data, 2/3 files synthetic-flagged, fake-admin auth |
| `ovnis-pr` | `PRODUCTION` | real corpus, but no linter, no `pyproject.toml`, 72 tests |
| `spiderweb-pr` | `PRODUCTION` | real but small package; 4% lint coverage; 0 UI pages |
| `aguayluz-pr` | `PRODUCTION_REAL_DATA_PARTIAL` | **most accurate label in the federation** |
| `moneysweep-pr` | `NON_PRODUCTION_DIAGNOSTIC` | strongest engineering of the seven — arguably understated |
| `skywatcher-pr` | `NON_PRODUCTION_DIAGNOSTIC` | accurate; blockers specific and honest |

The two repos declaring `NON_PRODUCTION_DIAGNOSTIC` are better engineered than three of the
four declaring `PRODUCTION`. The label is not currently tracking maturity.

---

## What was fixed in this audit round

| Fix | Repos | Verification |
|---|---|---|
| Auth routes render only when auth is required | `thehub-pr`, `skywatcher-pr`, `centinelas-pr` | lint + build + tests clean; typecheck error counts identical before and after |
| `PRII_WRITE_TOKEN` bearer-or-loopback guard on mutating routes | `thehub-pr`, `skywatcher-pr` | 14/14 live probes pass across 7 conditions × 2 repos |
| README `COLLECTION_ADAPTERS` drift corrected | `thehub-pr` | all six replacement symbols verified to resolve |
| `STATUS.md` test baseline refreshed | `moneysweep-pr` | re-measured: 2394 passed vs the 481 claimed |

No fixes were needed or applied in `aguayluz-pr`, `ovnis-pr`, or `spiderweb-pr` — those PRs
carry the audit document only.

---

## Consolidated top-20 backlog

Ranked by value per unit of effort across the whole federation.

| # | Item | Repo(s) | Effort |
|---|---|---|---|
| 1 | Add `pyproject.toml` + ruff + a CI lint step | `ovnis-pr` | S |
| 2 | Add ruff + mypy to CI | `skywatcher-pr` | M |
| 3 | Run `hub aggregate/correlate/ingest` in CI; ship a seeded DB | `thehub-pr` | M |
| 4 | Decide the auth story: implement `/auth/*` or delete the pages | `centinelas-pr`, `skywatcher-pr`, `thehub-pr` | L / S |
| 5 | Extend the lint allowlist beyond 13 files | `spiderweb-pr` | M |
| 6 | Pick one frontend; retire the other two | `spiderweb-pr` | L |
| 7 | Build out the dashboard | `moneysweep-pr` | L |
| 8 | Fix `POST /api/entities/{name}` returning 500 on duplicate id (should be 409) | `thehub-pr` | S |
| 9 | Fix `_ocr_regions` crashing when `pytesseract` is present without the binary | `skywatcher-pr` | S |
| 10 | Add a frontend test runner (copy `thehub-pr`'s vitest setup) | 6 repos | M each |
| 11 | Add ESLint config + `lint` script | `spiderweb-pr` | S |
| 12 | Action the 60 module-consolidation candidates | `moneysweep-pr` | L |
| 13 | Add empty-state / `ErrorBoundary` components | `centinelas-pr`, `ovnis-pr`, `spiderweb-pr` | S–M |
| 14 | Review authorization on domain mutating routes | `aguayluz-pr`, `spiderweb-pr`, `centinelas-pr` | M |
| 15 | Run `npm run typecheck` in CI, or drop the script | `thehub-pr`, `skywatcher-pr` | M |
| 16 | Migrate reusable `scripts/` logic into packages | `moneysweep-pr`, `spiderweb-pr`, `skywatcher-pr` | L each |
| 17 | Reconcile `requires_auth` vs `auth_required` naming | 3 repos | S |
| 18 | Reconcile declared `production_status` with observed maturity | `centinelas-pr`, `ovnis-pr` | S |
| 19 | Populate empty `snapshot.json` files | `moneysweep-pr`, `aguayluz-pr` | S |
| 20 | Split the single-page dashboards into routed pages | `ovnis-pr`, `moneysweep-pr` | M |

**Highest value for least effort:** items 1, 8, 9, 11, 17 are all **S** and independently
shippable. Items 3 and 4 are the ones that change what the federation *is* rather than how
tidy it is.

---

## Findings that did not survive verification

Recorded so they are not re-raised. An audit that only reports confirmations is not measuring
its own error rate.

- **"`pip install -e .` is broken in four repos."** Wrong command on the auditor's side. The
  producers declare shared libs via `[tool.uv.sources]`, which pip ignores and `uv` honours;
  CI uses `pip install uv && uv pip install --system`. All installs succeed with `uv`.
- **"`moneysweep-pr` packaging is broken."** Its `pyproject.toml` contains only `[tool.mypy]`
  and `[tool.ruff]` — deliberately tool config, not a package.
- **"`spiderweb-pr` tests fail on missing `sse_starlette`."** Under-provisioned install; CI
  installs `.[airspace,earthgpt,server,dev]` and the suite is fully green.
- **"`spiderweb-pr/server/backend/requirements.txt` is empty."** True but inert; dependencies
  live in pyproject extras and nothing reads that file.
- **"`thehub-pr` does not dogfood its own design system."** True but deliberate: it vendors
  `lib/theme.jsx` so the app builds standalone, and `src/styles/federation.sync.test.js`
  fails if the two drift. A tested trade-off, not an oversight.
- **"6 `skywatcher-pr` tests fail."** An artifact of the auditor's shared virtualenv — a
  sibling repo's extras installed `pytesseract` without the `tesseract` binary. Identical
  failures with and without this round's changes; CI does not install `pytesseract` and stays
  green. It did, however, expose a real robustness bug — backlog item 9.
