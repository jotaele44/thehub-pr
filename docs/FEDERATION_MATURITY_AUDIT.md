# PRII Federation — Professional Maturity Audit (rollup)

**Date:** 2026-07-26 · **Scope:** all seven repositories · **Method:** static review **plus
execution**. Every figure was produced by running the code in a clean container (Python
3.11.15, Node v22.22.2), using each repo's own documented setup command. Per-repo detail
lives in each repository's `docs/MATURITY_AUDIT.md`.

---

## The one-paragraph answer

The federation's Python engineering is genuinely good and its user interfaces are not
finished. All seven test suites pass — **5,095 tests green across the federation**, from
72 in `ovnis-pr` to 2,394 in `moneysweep-pr` — and every frontend that can be built and
linted was, cleanly, **by hand in this audit** (see the correction below for what CI
actually runs).
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
| `aguayluz-pr` | 4 | 4 | 4 | 4 | 4 | 4 | **24** |
| `thehub-pr` | 3 | 1 | 4 | 4 | 3 | 3 | **18** |
| `moneysweep-pr` | 4 | 3 | 2 | 4 | 4 | 3 | **20** |
| `spiderweb-pr` | 4 | 3 | 1 | 4 | 2 | 4 | **18** |
| `skywatcher-pr` | 3 | 1 | 4 | 3 | 1 | 4 | **16** |
| `centinelas-pr` | 3 | 3 | 4 | 3 | 3 | 4 | **20** |
| `ovnis-pr` | 3 | 4 | 2 | 2 | 1 | 3 | **15** |

**`aguayluz-pr` is the reference node** — real data, a UI proportionate to its backend, the
widest lint rule set in the federation, honest caveats, and the only producer that already
ships optional write auth (`API_SECRET_KEY` via `_require_key`). When settling a "how should
we do this?" argument, it is the one to copy.

---

## Maturity percentages and the road to 100%

Added 2026-07-27. Scores allow **partial credit** where a criterion splits into independent
halves (e.g. "linters gated in CI" = 2.5 Python + 2.5 JavaScript), so dimension totals are
not always multiples of five. Exact component sums, before rounding to the nearest whole
percent: thehub 64, skywatcher 60.5, centinelas 69, moneysweep 72.5, spiderweb 55.5,
aguayluz 69.5, ovnis 68.

The 0–4 scorecard above saturates — `aguayluz-pr` scored 24/24 while
having no frontend tests — so it cannot express "how far from done". This finer model
scores 20 explicit criteria at 5 points each; every lost point is a work item.

| Repo | Maturity | Function /20 | Data /20 | UI /20 | Tests /15 | Hygiene /15 | Docs /10 | Own `ROAD_TO_100` |
|---|---|---|---|---|---|---|---|---|
| `moneysweep-pr` | **73%** | 17 | 15 | 8 | 10 | 12.5 | 10 | ~75% |
| `aguayluz-pr` | **70%** | 20 | 15 | 15 | 5 | 4.5 | 10 | ~90% |
| `centinelas-pr` | **69%** | 20 | 16 | 17 | 5 | 3 | 8 | ~90% |
| `ovnis-pr` | **68%** | 18 | 20 | 12 | 5 | 5 | 8 | ~82% |
| `thehub-pr` | **64%** | 17 | 2 | 18 | 10 | 9 | 8 | ~90% |
| `skywatcher-pr` | **61%** | 17 | 6 | 17 | 5 | 5.5 | 10 | ~73% |
| `spiderweb-pr` | **56%** | 18 | 16 | 2 | 10 | 2.5 | 7 | ~85% |

**Federation mean: 66%.** Note this reorders the 0–4 table: `moneysweep-pr` leads because
the finer model rewards CI enforcement, where it is untouchable, while `aguayluz-pr`'s
ceiling-hit concealed four real gaps.

### Reconciling with the per-repo `ROAD_TO_100.md` ledgers

**All seven** repos carry their own completion ledger, claiming 73–90%. Those measure **code
completeness against intended scope**, explicitly excluding data/live-feed blockers. This
audit measures **professional maturity** — it only counts a thing done when a CI gate keeps
it working. The spread is largely enforcement, not implementation. Both are correct; each
repo's `ROAD_TO_100.md` now carries a block naming that repo's specific missing gates.

The two ledgers agree most closely where enforcement is already strong (`moneysweep-pr`,
~75% vs 73%) and diverge most where it is weakest (`spiderweb-pr`, ~85% vs 56%). That
spread is itself the clearest single signal in this audit.

### The road to 100% — 241 points, phased

**Phase 1 — CI sweeps (S each, ~99 pts).** The cheapest points in the federation are all
wiring, not features, and each has a working in-house template:

| Sweep | Repos | Points | Template |
|---|---|---|---|
| Frontend test harness | 6 | 30 | `thehub-pr/server/frontend` (vitest + Testing Library + `vitest-axe`) |
| Coverage gate | 5 | 25 | `moneysweep-pr/pytest.ini` `--cov-fail-under`, ratcheted from actuals |
| Type checking gated | 5 | 27 | includes running the `typecheck` scripts that already exist and fail silently |
| Linters gated | 5 | 17 | `ovnis-pr` is the cheapest anywhere — 3 findings today |

**Phase 2 — UI states and polish (M, ~50 pts).** a11y gates; `ErrorBoundary` for
centinelas/ovnis/spiderweb; ovnis's error-vs-empty conflation; aguayluz's empty
`snapshot.json`; one federation-wide answer for how a frontend supplies a write credential.

**Phase 3 — structural (L, ~72 pts).** spiderweb consolidating three frontends into one
with routed pages (+18); moneysweep's dashboard (+12); thehub running
`aggregate/correlate/ingest` into a committed fixture so 23 pages stop rendering empty
(+18); module consolidation in moneysweep/spiderweb/skywatcher (+7).

**Phase 4 — externally blocked (~20 pts) — the honest ceiling.** Four repos can reach 100%
on internal effort: `aguayluz-pr`, `centinelas-pr`, `ovnis-pr`, `thehub-pr`. Three cannot:

| Repo | Blocker | Internal ceiling |
|---|---|---|
| `skywatcher-pr` | FlightRadar24 captures must be supplied locally | ~86% |
| `moneysweep-pr` | `PROPUBLICA_API_KEY`, JS-gated cor3 portal, Tranche-B operator drops | ~95% |
| `spiderweb-pr` | corpus growth beyond the single site observation | ~98% |

Phase 1 alone moves the federation from 66% to roughly 80%, because it is the same four
changes seven times.

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
`GET`. `thehub-pr` writes to `data/hub.db` on disk; `skywatcher-pr`'s writes are in-memory
only. Both now refuse unauthenticated writes from public addresses, and require a bearer
token when `PRII_WRITE_TOKEN` is set.

The other five backends implement domain REST APIs and returned 404 for `/api/entities/*`.
`aguayluz-pr` is ahead of the hub here: `_require_key` already gates all five of its mutating
routes behind an optional `API_SECRET_KEY`. `spiderweb-pr` (4 mutating routes) and
`centinelas-pr` (2) were not write-probed — open follow-up in those repos' backlogs.

**The shared gap is the client, not the server.** Wherever write auth exists — the hub's
new `PRII_WRITE_TOKEN`, skywatcher's, and aguayluz's older `API_SECRET_KEY` — no frontend
sends the credential. `federationClient` carries only the federation access token, and
`AuthContext` drops that when `/api/auth/me` 401s. So enabling write auth anywhere currently
breaks that repo's own UI. This needs one federation-wide answer, not three local patches;
it is item 4 in the backlog below.

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
| 4 | One federation-wide answer for how a frontend supplies a write credential | all repos with write auth | M |
| 4b | Decide the auth story: implement `/auth/*` or delete the pages | `centinelas-pr`, `skywatcher-pr`, `thehub-pr` | L / S |
| 5 | Extend the lint allowlist beyond 13 files | `spiderweb-pr` | M |
| 6 | Pick one frontend; retire the other two | `spiderweb-pr` | L |
| 7 | Build out the dashboard | `moneysweep-pr` | L |
| 8 | Fix `POST /api/entities/{name}` returning 500 on duplicate id (should be 409) | `thehub-pr` | S |
| 9 | Fix `_ocr_regions` crashing when `pytesseract` is present without the binary | `skywatcher-pr` | S |
| 10 | Add a frontend test runner (copy `thehub-pr`'s vitest setup) | 6 repos | M each |
| 11 | Add ESLint config + `lint` script | `spiderweb-pr` | S |
| 12 | Action the 60 module-consolidation candidates | `moneysweep-pr` | L |
| 13 | Add a global `ErrorBoundary`; stop errors rendering as empty results | `centinelas-pr`, `ovnis-pr`, `spiderweb-pr` | S |
| 14 | Review authorization on domain mutating routes | `spiderweb-pr`, `centinelas-pr` | M |
| 15 | Run `npm run typecheck` in CI, or drop the script | `thehub-pr`, `skywatcher-pr` | M |
| 16 | Migrate reusable `scripts/` logic into packages | `moneysweep-pr`, `spiderweb-pr`, `skywatcher-pr` | L each |
| 17 | Reconcile `requires_auth` vs `auth_required` naming | 3 repos | S |
| 18 | Reconcile declared `production_status` with observed maturity | `centinelas-pr`, `ovnis-pr` | S |
| 19 | Populate the empty `snapshot.json` / chain a snapshot step into `build:export` | `aguayluz-pr` | S |
| 20 | Split the single-page dashboards into routed pages | `ovnis-pr`, `moneysweep-pr` | M |

**Highest value for least effort:** items 1, 8, 9, 11, 17 are all **S** and independently
shippable. Items 3 and 4 are the ones that change what the federation *is* rather than how
tidy it is.

---

## Corrections applied after review

Automated review on the seven PRs caught real errors in the first draft. They are listed
here rather than quietly edited, because an audit that hides its own corrections has no
standing to grade anyone else's doc accuracy.

**One methodology error, five repos affected.** The first draft counted UI states by
grepping for *component names* (`EmptyState`, `emptyTitle`, `LoadingState`) rather than
*semantic branches*. That systematically undercounted repos that handle states inline or
through a differently-named shared component, and it understated four D3 scores:

| Repo | What was actually there | D3 |
|---|---|---|
| `aguayluz-pr` | `components/common/PanelState.jsx` + branches in 7 views | 3 → **4** |
| `centinelas-pr` | `components/ListState.jsx` — three-way loading/error/empty with `aria-live` and `role="alert"`, used by 8 files | 3 → **4** |
| `moneysweep-pr` | `components/QueryBoundary.jsx` — shared loading/error-with-retry/empty across 4 tables | 1 → **2** |
| `spiderweb-pr` | inline states in `FinancePane.tsx:53-54`, `LayerCatalogPane.tsx:35-36` | 0 → **1** |
| `ovnis-pr` | inline "Queue empty" in `CandidateReview.jsx:46` | held at 2 — the real gap is that `getJSON` turns failures into `[]`, so errors are indistinguishable from empty |

**Other corrections.**

- **A regression this audit introduced.** The first cut of the write guard was loopback-only.
  Under `docker compose up`, uvicorn sees the Docker bridge address, so it would have 403'd
  every write in `thehub-pr`'s documented container deployment. Now allows loopback + private
  + link-local, refusing public addresses. Caught in review, not by me.
- `aguayluz-pr` **already had write auth** (`_require_key` / `API_SECRET_KEY` on five of its
  six mutating routes — see the 2026-07-27 corrections below). The draft said its routes were
  unguarded. It is ahead of the hub here, and the finding became the client-credential gap
  instead.
- `aguayluz-pr` has no `GET /assets/{id}` endpoint and no `/assets/:id` route — AssetDetail
  is a panel over the `/assets` collection.
- `centinelas-pr`'s data is **254 live records** (`is_synthetic: false`) against 6 synthetic
  rows in a clearly-named example file. The draft's "2 of 3 files synthetic" reading, and the
  "manifest overstates the node" conclusion that followed, were both wrong. D2 2 → 3.
- `centinelas-pr`'s Handoff page is **backend-backed** (`createHandoff()` → `POST
  /handoffs/{itemId}`), not localStorage-only.
- `moneysweep-pr`'s baseline was measured on **Python 3.11.15** while CI pins **3.13** — now
  labelled as such in both the audit and `STATUS.md`, rather than claimed as CI-equivalent.
- `moneysweep-pr`'s `build:export` chains `npm run snapshot` first, so the committed `{}` is
  intentional and offline exports do carry data. Backlog item removed.
- `spiderweb-pr`'s `pipeline/`, `federation/` and `integration/` directories are **not**
  ruff-clean — only the 13 allowlisted files are. The draft's advice to add those directories
  wholesale would have broken the gate.
- `ovnis-pr` has 7 application routes, not 11 (the draft counted FastAPI's auto-generated
  docs routes), **5 of its 9 test modules import `scripts/` directly**, and it does have a
  JS linter — the gap is Python-side plus a CI gate.

### Second round of corrections — 2026-07-27

Two more claims failed re-verification. Both were mine, and both were the same failure mode:
a summary sentence generalised past the evidence under it.

- **"`_require_key` … is attached to every mutating route" (`aguayluz-pr`) — false.** The
  sentence named five routes; six exist. `POST /ai/query` (`server/backend/main.py:413`)
  carries no `Depends(_require_key)`. That is the one route where the omission has a cost
  beyond data integrity: it forwards the caller's prompt to `api.anthropic.com` on the
  operator's `ANTHROPIC_API_KEY`, so an exposed port is a spendable credential. It is now
  `aguayluz-pr`'s backlog item 1, coupled to the client-header item — guarding it alone
  would break the dashboard's AI panel, which works today *because* the route is open.
  Method: parse every `@app.post`/`@app.patch` decorator against its handler signature,
  rather than trusting the prose list.
- **"All seven frontends build and lint clean" — false on both halves.** Six of seven have a
  `lint` script; `spiderweb-pr/server/frontend` has none (`['build','build:export','dev',
  'preview','snapshot','typecheck']`). And "clean" described *my* manual runs, not CI. What
  CI actually does:

  | Repo | `npm ci` + build in CI | `npm run lint` in CI |
  |---|---|---|
  | `thehub-pr` | yes | **yes** (plus `test`, `test:visual`) |
  | `skywatcher-pr` | yes | **yes** |
  | `centinelas-pr`, `aguayluz-pr`, `moneysweep-pr`, `ovnis-pr` | yes | no — script exists, no workflow runs it |
  | `spiderweb-pr` | **no npm step in any workflow** | no script to run |

  So the enforced position is two repos, not seven. The four middle repos are the cheap fix:
  the script already exists and passes, it simply is not wired to a gate.

**Why both survived the first pass.** Neither claim was invented — each summarised real
observations (five guarded routes; seven clean manual runs). The defect is that a
quantifier got attached to a sample. The harness described below exists so that class of
error fails a build instead of waiting for a re-read.

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

---

## The audit is now gated against itself

`scripts/verify_audit.py` re-derives the countable claims in these documents from the code
and fails when the two disagree. It is stdlib-only, runs in about a second, and is wired
into `.github/workflows/ci.yml` as the `audit-claims` job. `tests/test_verify_audit.py`
covers it — mostly with negative cases, because a gate only ever observed to pass is
indistinguishable from a gate that always passes.

**What it checks today.** Which mutating routes carry an auth dependency and which do not,
in `aguayluz-pr`; the hub CLI's subcommand count; the size of `spiderweb-pr`'s CI lint
allowlist; and the whole frontend lint table — which repos have a `lint` script and which
actually gate it. Those are precisely the claims that went wrong.

**Four properties that make it worth having.**

- It reads the *asserted* number out of the document and compares it to the derived one, so
  a stale doc fails with both values printed — not a bare assertion error.
- Deleting the sentence does not make it green. A claim that no longer matches its pattern
  fails as "the document was reworded, or the claim was dropped", with the derived value
  attached.
- It is bidirectional. Guarding `POST /ai/query` without updating these documents turns the
  gate red exactly as leaving the documents stale does. The code is the source of truth, but
  drift is an error in whichever direction it appears.
- It parses handler *signatures*, not decorator lines. The auth dependency is a default
  argument and signatures wrap across lines; a decorator-only reading reports every route in
  `aguayluz-pr` as unguarded, and a first-line-only reading misses `patch_asset`. Both wrong
  answers were produced during this audit before the parser was written correctly.

**Its stated boundary.** The federation is seven repositories, and a CI job has one checked
out, so most checks report SKIP there — counted in the summary, never silently passed. The
full set runs from a working copy holding all seven:

```
python3 scripts/verify_audit.py --root <dir> --require-all
```

It also does not check test counts or coverage percentages. Those require the suites to be
run, which is each repo's own test workflow's job. A claim this gate cannot derive is left
to the reader rather than approximated — a verifier that guesses is worse than one with a
boundary written down.

**What it does not touch.** Every judgement in this audit — the 140 criterion scores, the
effort estimates, the phased roadmap — remains judgement. The harness constrains the
arithmetic and the counts, which is where both of the confirmed errors lived. It does not
make the grades objective and is not offered as doing so.
