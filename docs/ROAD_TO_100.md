# Road to 100% — thehub-pr (PRII Federation HUB)

> **Framing:** The hub is **code-complete**. Its remaining distance to a
> 100% end-to-end federation is **not** local hub code — it is **producer
> readiness** (live feeds, operator-approved live-execution gates, and the
> domain fields producers must emit). This ledger enumerates what is done,
> the small hardening closed here, and exactly what each producer must ship
> for the hub to light up end-to-end.

**Current completion: ~90%.** The remaining ~10% tracks producer maturity /
live-feed readiness, not hub implementation.

---

## 1. Done — implemented hub subsystems (the ~90%)

### 1.1 Hub CLI — 13 commands (`src/hub/cli.py`)
A complete producer-federation control plane:

| Command | Purpose | Module |
|---|---|---|
| `list` | list registered producers | `registry.py` |
| `validate-manifest <path>` | validate a producer `federation.json` | `manifest.py` |
| `validate-package <dir>` | validate an export package directory | `validate.py` |
| `validate-federation` | roll up producer readiness from a workspace | `federation_status.py` |
| `fetch [--run]` | clone/refresh producers (optionally run their export) | `fetch.py` |
| `aggregate` | discover + aggregate producer export packages | `aggregate.py` |
| `wrap-bridge` | wrap canonical bridge streams into a validated package | `bridge.py` |
| `correlate` | derive cross-producer correlation relationships | `correlate.py` |
| `ingest` | load an aggregate into the server entity store (`data/hub.db`) | `ingest.py` |
| `graph-report` | quality report for an aggregate directory | `graph_report.py` |
| `analytics-v2` | build Federation Analytics v2 from an aggregate | `federation_analytics_v2.py` |
| `consume-sensor-fusion <p>` | validate skywatcher sensor-fusion export → dashboard surface | `sensor_fusion_consumer.py` |
| `maintenance` | roll up producer maintenance reports + compute the promotion gate | `maintenance/` |

### 1.2 Correlation / aggregation pipeline
`registry → manifest → validate → fetch → aggregate → correlate → ingest →
graph_report`. Deterministic, schema-frozen, strict-mode aggregation with a
municipality/proximity + time-window correlation join
(`correlate.py`, tunable via `--window-days` / `--threshold-km`).

### 1.3 MCP runtime subsystem (`src/hub/mcp_runtime/`)
Router, runtime registry, auth, telemetry, caching, policy, SDK shim, and a
full adapter set (`geospatial`, `documents`, `domain`, `http`,
`github_bridge`, `provenance`, `mock`) plus registry-drift detection. Mounted
as HTTP routes behind a defensive guard so an MCP-layer failure can never take
down the entity API (`server/backend/mcp_api.py`).

### 1.4 Single FastAPI + React product (`server/`)
One deployable product: a generic SQLite-backed entity store implementing the
INTSYS-PR federation contract (`/api/entities/{name}` CRUD,
`/api/apps/public-settings`, `/api/auth/me`) with the built React SPA served
from the same origin. MCP federation API mounts alongside it.

### 1.5 Two shared packages (`packages/`)
- `prii_maintenance` — deterministic, audit-first maintenance layer shared
  across producer repos (models, state, detect, corrections, quarantine,
  report, runner).
- `prii_export_utils` — canonical id / normalization / hashing helpers
  (`fid`, `norm`, `sha256`).

### 1.6 Populated producer registry (`registry/producers.yaml`)
Six producer nodes registered with roles, manifests, export paths, and the
hub's integration-tier view: `moneysweep-pr`, `spiderweb-pr`, `aguayluz-pr`,
`ovnis-pr`, `skywatcher-pr`, `centinelas-pr`.

### 1.7 Strong CI (`.github/workflows/`)
4-version test matrix (3.9 / 3.10 / 3.11 / 3.12), `ruff` + `mypy` gate,
`uv lock --check` lockfile enforcement, plus federation-ingest, maintenance,
MCP-registry-validation, and desktop-build workflows.

---

## 2. Remaining — code (closed in this change)

Small, zero-risk hardening handled locally — no behavioural fabrication:

- **Diagnostic-mode stub contract hardened** (`server/backend/main.py`).
  The three intentionally-unimplemented subsystems — function execution
  (`/api/functions/{name}/invoke`), conversational agents (`/api/agents/*`),
  and binary file storage (`/api/files/upload`) — now return an **explicit,
  typed, self-documenting** payload with a stable contract:
  `status="not_implemented"`, `mode="diagnostic"`, `implemented=False`,
  a `feature` name, and a **documented `reason`**. HTTP status is deliberately
  kept at `200` (not `501`) because the single-product frontend treats any
  non-2xx as a hard error; the stubs must let the diagnostic UI degrade
  gracefully instead of throwing, and compatibility keys the frontend reads
  (e.g. `id` for a created agent conversation) are preserved.
- **Contract test added** (`tests/test_diagnostic_stubs.py`) pinning the
  diagnostic-mode contract for all three endpoints so they cannot silently
  drift into fabricating "implemented" behaviour.

These stubs **stay stubbed by design** — see §3.

---

## 3. Remaining — bounded by producers / out of local scope (the ~10%)

None of the below is hub code work. Each item is gated on an upstream producer
shipping live data or flipping its own live-execution gate.

### 3.1 The 3 diagnostic-mode stub endpoints stay stubbed by design
`functions.invoke`, `agents.*`, and `files/upload` are bound to live producer
feeds / external backends that are out of local scope. They are a deliberate
diagnostic contract, not a gap to "implement." Reaching 100% here means wiring
real backends (function execution feeds, an agent backend, a storage backend)
— a product decision beyond this hub build.

### 3.2 Domain UI pages render empty until producers emit their fields
The React pages (contracts / feeds / cases and related module views) are built
and wired to the federation client; they render **empty states** until the
corresponding producers emit those domain fields into their export packages
and the hub aggregates + ingests them. No frontend change unblocks this — it
tracks producer output.

### 3.3 `hub fetch --run` full live-export path is clone-exercised only
`fetch.py` clones/refreshes producer checkouts and can invoke their export
(`--run`). Offline, only the clone path is exercised; the full live-export
round-trip runs when producers are reachable and their exports execute.

### 3.4 Per-producer readiness checklist (what each must ship for 100%)

`hub validate-federation` reports **0/6 ready** offline (checkouts absent);
readiness is authoritative from each producer's own
`ready_for_hub_live_execution` gate. To reach 100% end-to-end:

| Producer | Hub tier | What it must ship to flip to live |
|---|---|---|
| **moneysweep-pr** | `ready_for_discovery` | Materialize remaining required sources (Tranche-B manual exports + cor3 portal JS-gated export) and supply `PROPUBLICA_API_KEY`; flip `ready_for_hub_live_execution`. |
| **spiderweb-pr** | `ready_for_live` | Live-execution gate already operator-approved; grow the real production corpus beyond the first validated package via the revived intake lane. |
| **aguayluz-pr** | `ready_for_live` | Live power/PREPS/water data wired and gate approved; resolve MiLUMA data-sharing to lift the outage-granularity (snapshot-grade) caveat. |
| **ovnis-pr** | `ready_for_live` | 470 real master cases, `PRODUCTION`, gate approved; keep canonical production export current on `main`. |
| **skywatcher-pr** | `ready_for_discovery` | Land a real FlightRadar24 capture through the FR24 ingest/OCR/RLSM pipeline to flip `ready_for_hub_live_execution`. |
| **centinelas-pr** | `ready_for_live` | `PRODUCTION`, gate approved, 274 real RSS signals bridged; keep production export passing `hub validate-package`. |

**Definition of 100% (end-to-end):** all 6 producers reachable with
`ready_for_hub_live_execution=true`, their export packages passing
`hub validate-package`, and a full `fetch --run → aggregate → correlate →
ingest → graph-report` cycle populating the entity store so the domain UI
pages render live data.

---

## 4. Verification (offline)

- `python -m pytest tests/ -q` → **318 passed** (includes the 5 new
  diagnostic-contract tests).
- `python -m hub.cli validate-federation` → runs cleanly; reports **0/6
  ready** with `missing_checkout` blockers (expected offline — producer
  checkouts and live feeds are absent, per §3).
- `ruff check` → clean on changed files.

**Bottom line: the hub is code-complete; the remaining ~10% tracks producer
readiness, not hub implementation.**
