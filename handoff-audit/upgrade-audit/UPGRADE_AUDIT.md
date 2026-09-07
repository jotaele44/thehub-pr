# THEHUB — Upgrade Audit (features, bug fixes, dependency & CI upgrades)

**Scope:** recommendable improvements found by a read-only audit of `thehub-pr` at pinned commit
`70765a2c4bd67470ee6b9892023f3ff4c80913b8` (plus the Spatial-RAG donor where noted).
**Status: Phase 1 + Phase 2 applied 2026-09-06 (see below). Phase 3 + Phase 4 remain
RECOMMENDATIONS ONLY — HOLD is retained for those.**

## Status update (2026-09-06) — Phase 1 + Phase 2 closure

Applied on `claude/federation-gap-closure-audit-o7wao8` as part of a federation-wide
gap-closure audit, verified against current `main` (the backend has since split
`server/backend/main.py` into a thin compat shim over `server/backend/main_core.py` —
line numbers below are stale; re-verify against current HEAD rather than trusting them).
Full test suite green (1176 passed, 3 skipped), `ruff check src/hub server tests` and
`mypy src/hub server/backend` both clean. A branch-protection audit across all seven
federation repos also landed in `governance/merge_blocking_status.json`. Everything
below this section is left verbatim as the historical record of the original,
pre-closure audit.

**Applied — Phase 1 (config/doc):**
- **DEP-3** — documented the sub-package Python-floor inconsistency in place (no
  3.10-only syntax was found, so the floors were left as-is rather than risk an
  unverified install-floor change on desktop packaging).
- **DEP-10** — added `"engines": {"node": ">=22"}` to `server/frontend/package.json`.
- **SEC-1 (config half)** — `docker-compose.yml` now publishes `127.0.0.1:8000:8000`,
  not `8000:8000`; the no-auth-past-loopback invariant is now spelled out in
  `docs/federation/MCP_DEPLOYMENT.md`.

**Investigated, not applied — recorded so this isn't re-litigated:**
- **DEP-2** — attempted (set mypy's `python_version` to `3.9` to match
  `requires-python`), then reverted: the resolved mypy (`>=1.10`, currently 2.3.1) has
  dropped support for `python_version = "3.9"` outright — it prints a warning and does
  not check 3.9 semantics at all. See the comment left on `[tool.mypy]` in
  `pyproject.toml`. A real fix means either pinning an older mypy that still supports a
  3.9 target, or raising the floor to 3.10 (which also means dropping 3.9 from the CI
  test matrix) — both bigger, deliberate decisions than a config-only pass.
- **DEP-4** — already substantially done on this HEAD: `.github/workflows/pip-audit.yml`
  (weekly + on lockfile-touching PRs) and `.github/dependabot.yml` (pip/npm/actions) both
  already exist, and `pyproject.toml`'s `[tool.coverage.report] fail_under = 88` is
  already an enforced gate. The one remaining piece — `ci.yml` still runs
  `npm ci --no-audit --no-fund` — lives in federation-templated infrastructure
  (`federation-templates/baseline/`, synced by `federation-template-sync.yml`), out of
  scope for a thehub-pr-only change.
- **DEP-6 / FEAT-2** — `server/backend/requirements.txt`'s apparent duplication of the
  `server` extra is deliberate and already documented in-file (`desktop-build.yml`
  installs it directly, without `-e .[server]`). Pinning the Docker image install
  against `handoff-audit/phase0/RUNTIME_LOCK.json` needs a real Docker build to confirm
  it doesn't regress, which this pass couldn't do safely without a Docker daemon. Left
  on HOLD.
- **DEP-1** — out of scope as originally noted: it's about the unmerged Spatial-RAG
  donor, not shipped Hub code ("not a merge unit").

**Applied — Phase 2 (small correctness fixes):**
- **BUG-1** — `contextlib.closing(_conn())` now wraps every remaining route that opens a
  connection in `server/backend/main_core.py` (`health`, `_load_alerts`,
  `notifications`/`notifications_ack`/`*_preferences`, `list_entities`, `get_entity`,
  `update_entity`, `delete_entity`, `filter_entities`, `bulk_create`).
- **BUG-3** — every mutating route's `await request.json()` now goes through a new
  `_read_json_body()` helper (400 on invalid JSON or a non-object body);
  `filter_entities`/`bulk_create` also validate `filters`/`items` shape (400 on a
  non-dict/non-list).
- **BUG-6** — `list_entities`'s `limit` query param now has `ge=1, le=2000`;
  `filter_entities`'s body `limit` goes through a new `_clamp_limit()` helper with the
  same bounds — which also fixes the negative-limit case silently returning exactly one
  row.
- **BUG-7** — `src/hub/manifest.py`'s `load_and_validate_manifest` now catches
  `FileNotFoundError`/`json.JSONDecodeError` and returns `({}, [error])`, mirroring
  `validate.py`'s existing pattern, instead of raising a raw traceback.
- **DEP-7** — swapped `starlette.testclient.TestClient` for
  `fastapi.testclient.TestClient` in the three named test files.
- New regression tests: `tests/test_entity_api.py` (BUG-2/3/6) and two new cases in
  `tests/test_manifest.py` (BUG-7).

**Found already fixed on this HEAD (no action needed):**
- **BUG-2** — `create_entity` already caught `sqlite3.IntegrityError` and returned 409,
  inside a `try/finally` that closes the connection — ahead of the rest of BUG-1's
  pattern, which this pass now extends to every other route. A regression test now
  guards it (`test_duplicate_create_returns_409_not_500`).

**Not attempted this pass:** Phase 3 (BUG-4 WAL/busy_timeout, BUG-5/FEAT-1 single-source
DDL) and Phase 4 (FEAT-3 observability, BUG-8/9/10/11, SEC-2/3, DEP-5/8/9) remain on HOLD
exactly as documented below.

---

Each item is tagged:
- **HOLD-safe?** — `config/doc` (a new/isolated config or documentation change) vs `CODE` (edits existing
  Hub production logic — recommend only, do not apply under HOLD).
- **Effort** — S / M / L. **P1-enabler** — directly de-risks the dual-engine migration.

Machine-readable index: [`UPGRADE_FINDINGS.csv`](UPGRADE_FINDINGS.csv).

---

## A. Bugs / correctness (Hub) — all CODE, recommend only

### BUG-1 · P1 · DB connection leak — no `try/finally` in FastAPI routes
`server/backend/main.py` — every route opens `c = _conn()` and calls `c.close()` manually with no
context manager (list/create/update/delete/filter/bulk entities, health, notifications, preferences).
Any exception between open and close leaks the SQLite connection and skips rollback. `src/hub/ingest.py`
(~652–687) does it correctly with `try/…/finally`.
**Failure:** a stream of malformed or duplicate-id requests each leaks a handle → fd/handle exhaustion →
every request eventually fails.
**Fix:** wrap each body in `with contextlib.closing(_conn()) as c:` or a FastAPI dependency that
yields+closes. **Effort S.**

### BUG-2 · P1 · `create_entity` uses `INSERT` → 500 on duplicate id
`server/backend/main.py:280`. Plain `INSERT INTO entities …`; a re-POST with an existing id raises
`sqlite3.IntegrityError` (PK `(entity_type, entity_id)`), uncaught → 500 (and, with BUG-1, an orphaned
connection). Inconsistent with `bulk_create` which uses `INSERT OR REPLACE`.
**Fix:** decide the contract — idempotent `INSERT OR REPLACE`, or catch `IntegrityError` → `409 Conflict`.
**Effort S.**

### BUG-3 · P1 · Unvalidated request bodies → 500 instead of 400
`server/backend/main.py` — `await request.json()` is unguarded in create/update/filter/bulk/ack/
preferences. Malformed/empty JSON raises inside the handler → 500. No shape checks either: `filter_entities`
does `body.get("filters", {})` / `body.get("limit", 500)` — a list `filters` or string `limit` raises
500 downstream; `bulk_create` assumes `items` is a list of dicts.
**Fix:** guard the parse and validate shape (ideally Pydantic request models); return 400 on bad input.
**Effort M.**

### BUG-4 · P1 · SQLite concurrency race on `data/hub.db` (no WAL / busy_timeout)
The API (`server/backend/main.py`) and `hub ingest` (`src/hub/ingest.py`) both write the same
`data/hub.db` in default rollback-journal mode, no `PRAGMA journal_mode=WAL`, no `busy_timeout`.
`ingest_aggregate` holds one write transaction for the whole load.
**Failure:** ingest during live serving → API writes (and reads, in rollback-journal mode) block, then
after the ~5s default raise `OperationalError: database is locked` → uncaught 500.
**Fix:** enable WAL + a `busy_timeout` on both connections; consider chunked commits in ingest. **Effort M.**

### BUG-5 · P1 · DDL drift risk — duplicated inline schema, unguarded *(P1-enabler)*
The `entities` DDL is hand-duplicated: `src/hub/ingest.py:46` (`_SCHEMA`, comment *"kept byte-identical
to server/backend/main.py::_init_db"*) and `server/backend/main.py:62`. **They agree today (byte-identical)**,
but: two hand-synced copies, **no** `PRAGMA user_version`/migration, and `tests/test_schema_freeze.py`
covers only `schemas/*.json` — **not** these inline strings. An edit to one and not the other passes CI
silently; whichever process runs first wins (both `CREATE TABLE IF NOT EXISTS`), so the other silently
operates on a stale shape → `OperationalError` or dropped data.
**Fix:** single source of truth (`src/hub/_store_schema.py` with `SCHEMA` + `ensure_schema(conn)`), import
in both; add `PRAGMA user_version` + a tiny forward-only migration guard; extend the freeze test to hash
the shared DDL. **Effort M.** Also listed as FEAT-1.

### BUG-6 · P2 · Unbounded / negative `limit`
`server/backend/main.py:247` `limit: int = Query(500)` has no `ge/le` — `limit=-1` → SQLite `LIMIT -1`
= no limit (dumps the whole collection); huge values are a memory lever. `filter_entities` (~343–364):
a negative body `limit` makes the `if len(results) >= limit` guard true after the first match → returns
exactly 1 row (silently wrong).
**Fix:** `Query(500, ge=1, le=N)` and validate the body limit. **Effort S.**

### BUG-7 · P2 · `manifest.py` has no error handling
`src/hub/manifest.py:26` does `json.loads(Path(path).read_text())` unguarded; `hub validate-manifest
<path>` on a missing/malformed file dumps a raw traceback instead of a clean "INVALID". `src/hub/validate.py`
(~35–38) handles both cases.
**Fix:** mirror `validate.py` — catch `FileNotFoundError`/`JSONDecodeError`, return an error string. **Effort S.**

### BUG-8 · P2 · `fetch_all` — no per-producer error isolation
`src/hub/fetch.py` (~161–197): `clone_or_pull` / export runner use `check=True`, so one unreachable repo
or failed export raises `CalledProcessError` out of the loop and aborts the whole fetch, losing results
already collected. `aggregate()` isolates per-producer via `summary["errors"]`.
**Fix:** wrap each producer iteration in try/except, record a per-producer error, continue. **Effort S.**
Minor adjacent: `export_command` assumes `cmd` is a `str`; a list/dict in `federation.json` raises
`TypeError` in `shlex.split` — add an `isinstance(cmd, str)` guard.

### BUG-9 · P2 · Startup / registry-shape crashes
`server/backend/main.py::_seed_programs` (~107–142): `p["program_id"]` → `KeyError` if any producer
entry lacks it, inside the FastAPI `lifespan` → **server fails to start**; `registry.get("producers", [])`
assumes a dict, but an empty `producers.yaml` yields `None` → `AttributeError`. `src/hub/registry.py`
(~39–46): `data["hub"]` / `data["schema_version"]` `KeyError` on a registry missing those keys →
every CLI command tracebacks.
**Fix:** validate registry shape (or catch and surface a clear message). **Effort S–M.**

### BUG-10 · P2 · Non-atomic file writes (reader races)
`src/hub/aggregate.py` (~58–64) writes each `<stream>.jsonl` / `graph_summary.json` directly (truncate-
write); `src/hub/correlate.py` (~517–520) writes `correlations.jsonl` the same way. A concurrent
`correlate`/`ingest` read mid-write hits a truncated line, and the parse loops have no per-line guard →
hard crash.
**Fix:** write to a temp file in the same dir + `os.replace()` (atomic); optionally tolerate a bad line.
**Effort S.**

### BUG-11 · P2 · `rstrip('s')` plural gotcha
`server/backend/main.py:271` `body.get(f"{entity_name.rstrip('s').lower()}_id")`. `str.rstrip('s')`
strips a *set* of trailing chars, not a plural suffix → `"Status"→"Statu"`, `"Address"→"Addre"`. For a
collection ending in `ss`/multiple `s`, the derived id key is wrong and it silently falls through to
`uuid4`. Cosmetic for current collections; latent surprise.
**Fix:** `name[:-1] if name.endswith('s') else name`, or an explicit singular map. **Effort S.**

### Verified NON-issues (checked, deprioritize)
- **No SQL injection:** the only f-string into SQL is `direction` (`main.py:257,353`), a validated
  `ASC`/`DESC` literal; all ids/values are parameterized. `ingest.py`/`notifications.py` fully parameterized.
- **No mutable default args** in `correlate.py` (tuple defaults) or runners.
- **`fetch.py` command execution is well-hardened** (shell-metachar block, bare-executable allowlist, no
  path separators, `-c/-m/-e/stdin` rejection, `--depth 1`). Preserve as-is.
- **No archive/zip decompression** in fetch/ingest (JSONL line-by-line) → no zip-bomb surface.
- No `TODO/FIXME/HACK` left in `src/hub` or `server/backend` (only a deliberate test fixture).

---

## B. Security

### SEC-1 · P0 · Unauthenticated mutation API reachable via `0.0.0.0` Docker bind
The entity CRUD surface is default-open (`public_settings` advertises `requires_auth: False`,
`auth_me` always 401 → "diagnostic mode"). Defensible on loopback, but `Dockerfile:40` binds
`--host 0.0.0.0 --port 8000` and `docker-compose.yml:11` publishes `8000:8000`. Any non-loopback deploy
exposes anonymous create/update/**delete**/bulk-overwrite of every collection backing the UI.
**Fix (HOLD-safe part = `config/doc`):** bind compose to `127.0.0.1:8000:8000`; document a hard invariant
that diagnostic (no-auth) mode must never bind past loopback (e.g. in `docs/federation/MCP_DEPLOYMENT.md`).
**Fix (CODE, recommend):** gate mutations behind an auth dependency or a `HUB_READONLY`/`HUB_DIAGNOSTIC`
flag before any non-loopback bind. **Effort: config S / code M.**

### SEC-2 · P1 · No request-body size limits / unbounded prefetch (DoS)
Every write route does `await request.json()` with no cap; `bulk_create` iterates an arbitrary-length
`items`; `filter_entities` prefetches `max(limit*10, 5000)` rows with `limit` straight from the body →
`limit=10_000_000` forces a ~100M-row load. Compounds SEC-1 (no auth needed).
**Fix (config):** enforce a max body at the proxy/uvicorn layer. **Fix (CODE):** clamp `limit`
(`Query(500, le=2000)`), clamp body `limit`/`max_hits`, cap `bulk_create` count. **Effort S.**

### SEC-3 · P2 · Error details reflect caller-supplied ids
`server/backend/main.py:298,312` (and the integrations stub echoing the path) return
`"{entity_name}/{entity_id} not found"`. Low severity (no internals/stack), but reflects input.
**Fix (CODE):** generic 404 detail; keep specifics in server logs. **Effort S.**

### Positive controls to PRESERVE (no action)
Scoped CORS (explicit `localhost:5173`/`127.0.0.1:5173`, not wildcard, even with credentials) ·
parameterized SQL · SPA catch-all path-traversal guard (`DIST.resolve() in candidate.parents`, blocks
`api/`) · hardened `fetch.py` subprocess allowlist · no decompression surface · secrets clean
(`.env.example` names-only, env-sourced provider secrets with offline no-op, `auth.py` fail-closed +
`REDACTED` reprs) · non-root Docker uid 10001.

---

## C. Dependencies / tooling / CI

### DEP-1 · P0 · Spatial-RAG donor: undeclared runtime deps *(config — donor, not Hub)*
Imported but absent from the donor `backend/requirements.txt`: `tenacity` (`app/spatial/enricher.py:17`),
`geoalchemy2` (`app/models/orm.py:7`), `pgvector` (`app/models/orm.py:8`), `numpy`
(`app/ingestion/embedder.py:12`, only transitively present via torch today). Also `sse-starlette==2.1.3`
is declared but unused (dead pin). Any env installing only the declared reqs crashes at import.
**Fix:** add pinned `tenacity`, `geoalchemy2`, `pgvector`, `numpy`; drop the dead pin. Relevant only if
the donor is ever adopted — it is **not** a merge unit. **Effort S.** (First surfaced in Phase-0
`SPATIAL_RAG_REPRODUCTION_LEDGER.md`; numpy is the newly-added 4th.)

### DEP-2 · P1 · mypy/Python-floor mismatch *(config)*
`pyproject.toml`: `requires-python = ">=3.9"` but `[tool.mypy] python_version = "3.10"`. CI runs a 3.9
leg, yet mypy type-checks against 3.10 semantics → 3.9-only breakages (builtin-generic subscripting,
`X | Y` unions) aren't caught. **Fix:** set mypy `python_version = "3.9"`, or raise the floor to 3.10.
**Effort S.**

### DEP-3 · P1 · Sub-package floor inconsistency *(config/doc)*
`packages/prii_desktop|prii_export_utils|prii_maintenance/pyproject.toml` declare `>=3.10` vs root `>=3.9`.
The support matrix is inconsistent. **Fix:** unify to 3.10 or document explicitly. **Effort S.**

### DEP-4 · P1 · CI has no dependency audit / security scan / coverage gate *(config — new workflow)*
`.github/workflows/ci.yml`: no `pip-audit`/`safety`, no CodeQL/bandit, `npm ci --no-audit` explicitly
disables npm audit; no coverage measurement/threshold; no `dependabot.yml`/renovate. **Fix:** add a
`pip-audit` + `npm audit` job, a coverage gate, and Dependabot. **Effort M.**

### DEP-5 · P1 · Lint/type coverage is narrow *(config)*
`ruff check src/hub tests` + `mypy src/hub` only. Unchecked: `tools/`, `server/backend/`, `desktop/`,
and packages beyond their own jobs. **Fix:** widen ruff/mypy targets (may surface new findings). **Effort M.**

### DEP-6 · P1 · Mixed / duplicated dependency pinning *(config)*
Root runtime deps are lower-bound-only (`pyproject.toml`), reproducibility resting entirely on `uv.lock`;
`server/backend/requirements.txt` re-declares `fastapi`/`uvicorn`/`PyYAML` loosely, overlapping the
pyproject `server` extra (drift risk); the donor uses exact `==` (opposite strategy). **Fix:** pick one
strategy; de-duplicate server deps against the `server` extra; consume the lockfile in the image
(`Dockerfile` `pip install -e ".[server]"` is unpinned). **Effort S–M.** (See also FEAT-2.)

### DEP-7 · P1 · Deprecated test client *(CODE — tests only)*
`starlette.testclient.TestClient` in `tests/test_desktop_app_server.py:21`,
`tests/test_desktop_launcher_api.py:17`, `packages/prii_desktop/tests/test_appserver.py:17`, while
`fastapi.testclient` is used elsewhere. Inconsistent and httpx-deprecation-sensitive (this is the
warning seen in Phase-0). **Fix:** standardize on `fastapi.testclient`. **Effort S.**

### DEP-8 · P2 · Ruff ruleset minimal *(config)*
`select = ["E4","E7","E9","F"]`. Low-risk high-value adds: `"I"` (import sort), `"B"` (bugbear). Hold
`"UP"` (pyupgrade) until the floor moves to 3.10+ (it would rewrite `typing.List/Optional` used in ~30
files). Enabling `I`/`B` may turn CI red until existing violations are fixed. **Effort S–M.**

### DEP-9 · P2 · mypy leniency *(config)*
Global `ignore_missing_imports = true` + `disable_error_code = ["import-untyped"]` suppress a whole error
class. **Fix:** scope via `[[tool.mypy.overrides]]` per untyped module; add `types-jsonschema`. **Effort S.**

### DEP-10 · P2 · Node version not enforced *(config)*
`server/frontend/package.json` has no `engines`, yet CI hard-pins Node 22. **Fix:** add
`"engines": { "node": ">=22" }`. **Effort S.**

### DEP-11 · P2 · Frontend major upgrades *(CODE — separate initiative)*
React 18 (→19 available), Vite 6, vitest 2, jsdom 29. Genuine effort; call out as its own initiative,
not part of this HOLD-safe pass. **Effort L.**

### Verified ABSENT deprecations (no action)
No `datetime.utcnow()`, no FastAPI `@app.on_event`, no `asyncio.get_event_loop`, no `pkg_resources`
across Hub `src/`, `server/`, `desktop/`, or the donor. The donor already uses the `lifespan` context
manager and pydantic v2. The real work is dependency/CI/config, not code rewrites.

---

## D. Features / enhancements

### FEAT-1 · P1 · SQLite migration + versioning; single-source DDL *(P1-enabler; = BUG-5)*
Doc/ADR is HOLD-safe now; the code consolidation is a recommendation. Directly de-risks the dual-engine
store evolution. **Effort M.**

### FEAT-2 · P1 · Pin server runtime deps / use lockfile in image *(config — HOLD-safe)*
`Dockerfile` `pip install -e ".[server]"` is unpinned. Ship pinned server deps (constraints file or
`uv export`/`uv sync --frozen`), aligning with the Phase-0 freeze artifacts (`RUNTIME_LOCK.json`,
`pip_freeze.txt`). **Effort S–M.**

### FEAT-3 · P1 · Structured logging + request-ID middleware + error tracking *(CODE)*
Health/readiness are well covered (`/health`, `/api/health`, MCP `/healthz`+`/readyz`, `/mcp/metrics`),
but there is **no** app-wide structured request logging, **no request/correlation-ID middleware**, and no
error-tracking hook — so anonymous mutations (SEC-1/2) can't be reconstructed. **Fix:** ASGI middleware
that assigns/propagates `X-Request-ID`, emits one JSON access log per request, binds the id into MCP
provenance; env-gated error sink (no-op when unset). **Effort M.**
> Note: there is no existing request-correlation middleware; `src/hub/correlate.py` is *data* correlation,
> unrelated to request tracing.

### FEAT-4 · P2 · CLI `--version` *(CODE, small)*
`src/hub/cli.py` has no `--version` (package is `0.1.0`); useful for the CI/handoff tooling ledgers.
`argparse action="version"` sourced from package metadata. **Effort S.**

### FEAT-5 · P2 · Extend schema-freeze + startup config validation *(config/test HOLD-safe; command = CODE)*
`tests/test_schema_freeze.py` pins only `schemas/*.json`. Not frozen: `registry/producers.yaml`,
`activation-matrix.yaml`/`dependency-graph.yaml`, and the SQLite DDL — all boundary contracts. Add
freeze/validation for those; optionally a `hub doctor` subcommand validating env + registry consistency.
**Effort S (freeze) / M (doctor).**

### FEAT-6 · P2 · Ingest snapshot-metadata scaffold *(P1-enabler; CODE)*
`ingest_aggregate` stamps only per-row dates; no ingest-run/snapshot manifest (source dir, git SHAs, row
counts, timestamp) is persisted. A small snapshot-metadata record is a low-risk scaffold Phase 1 builds on.
**Effort S–M.**

---

## Suggested sequencing (when the user authorizes work)

1. **HOLD-safe config/doc first** (no logic change): DEP-2, DEP-3, DEP-6/FEAT-2, DEP-4, DEP-10, the
   compose loopback bind + deploy doc under SEC-1, the donor requirements fix DEP-1.
2. **Small correctness fixes:** BUG-1, BUG-2, BUG-3, BUG-6, BUG-7, DEP-7.
3. **Concurrency & schema hardening (P1-enablers):** BUG-4 (WAL), BUG-5/FEAT-1 (single-source DDL +
   versioning), FEAT-5, FEAT-6.
4. **Observability & remaining:** FEAT-3, BUG-8/9/10/11, SEC-2/3, DEP-5/8/9.

Nothing above is applied in this PR — these are recommendations for a future authorized change.
