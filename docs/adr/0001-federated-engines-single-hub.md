# ADR 0001 — Federated engines, one hub app

- **Status:** Accepted
- **Date:** 2026-07-06
- **Deciders:** PRII federation maintainers
- **Scope:** `thehub-pr` and the six PRII producer repositories

## Context

PRII is delivered today as seven repositories:

- Six **producers** (domain "engines"): `moneysweep-pr`, `spiderweb-pr`,
  `aguayluz-pr`, `ovnis-pr`, `skywatcher-pr`, `centinelas-pr`.
- One **hub**: `thehub-pr`, which discovers producers, validates their export
  packages, aggregates canonical streams, and correlates entities across
  producers.

A recurring question is whether to keep the repos independent or to fold them
into a single program that uses all engines so the final product does not force
the operator to switch between them. In practice the question is about the
**product surface**, not the repository layout. The concrete pain is that each
of the six producers currently ships its own FastAPI backend plus its own
React/Vite dashboard, so seeing the whole picture means running and flipping
between roughly six apps. Cross-producer correlation — the entire reason the hub
exists — has no home in any single producer dashboard.

Two facts about the current codebase shape this decision:

1. The federation is **artifact-based by design**. `ARCHITECTURE.md` states there
   is "no shared database or RPC": producers publish export packages in their own
   repos, and the hub fetches and merges them. Every producer already conforms to
   `schemas/repo_federation_manifest.schema.json` via a root `federation.json`.
2. The hub already has **two halves that are not wired together**:
   - A data plane — the `hub` CLI (`src/hub/`: `fetch → validate → aggregate →
     correlate`) that writes `data/aggregate/*.jsonl`, `graph_summary.json`, and
     `correlations.jsonl`. This is real and tested.
   - A control-plane UI — `server/backend/main.py` (a generic SQLite entity store
     seeded only from `registry/producers.yaml`) and `server/frontend/` (a React
     app that can fall back to a static `snapshot.json` via `VITE_OFFLINE=1`).

   Nothing loads the aggregate outputs from the data plane into the store the
   frontend reads. That missing seam is what keeps PRII feeling like "seven
   engines you switch between" instead of "one product backed by all seven."

## Decision

**Keep the six producers as independent engines. Consolidate the final product
into the single `thehub-pr` app. Do not merge the repositories into a monorepo.**

The producer contract — `repo_federation_manifest.schema.json` and
`federation_export_manifest.schema.json` — is the stable boundary between engines
and product. The `thehub-pr` server (backend + `server/frontend/`) is the single
product surface; the per-producer dashboards are demoted to development and
diagnostic tools.

### Target architecture

```
6 producer repos (unchanged: own federation.json + export packages)
      |  hub fetch  (git clone/pull; optional sandboxed export_canonical)
      v
src/hub: validate -> aggregate (id-dedup + _producers provenance) -> correlate
      v
data/aggregate/{sources,entities,relationships,alerts,...}.jsonl + correlations.jsonl
      |  <-- new seam: ingest bridge loads aggregate -> hub server store
      v
thehub-pr/server/backend   (single API over the federation graph)
      v
thehub-pr/server/frontend  (the product: per-producer pages + cross-domain correlation)
```

No producer runtime, schema, or readiness-gate changes are required by this
decision.

## Rationale

**Why keep the producers independent:**

- Distinct domains, provenance, and cadence, and — critically — distinct
  **readiness gates**. Some producers are `ready_for_live` (`spiderweb-pr`,
  `aguayluz-pr`, `ovnis-pr`, `centinelas-pr`); others are only
  `ready_for_discovery` (`moneysweep-pr`, `skywatcher-pr`). A monorepo would
  couple release cycles and collapse the per-domain provenance boundary the
  architecture deliberately enforces: producers export; the hub correlates.
- The artifact-based contract makes independent repos the natural unit. Each
  producer already emits a conformant `federation.json` and export package.

**Why unify the product in the hub:**

- The "switching" cost lives in the UI tier, not the data tier. The six producer
  dashboards are near-identical boilerplate over a single domain each (a
  byte-identical shadcn UI kit is copied across five of them; the FastAPI
  `server/backend/main.py` is re-implemented per repo).
- `thehub-pr` already scaffolds the single pane of glass: one backend and one
  React app with a dedicated page per producer (`MoneySweep.jsx`, `AguaYLuz.jsx`,
  `Ovnis.jsx`, `Skywatcher.jsx`, `Spiderweb.jsx`) plus the cross-domain views that
  only make sense at the hub (`FederationCrossoverWorkspace.jsx`,
  `AnomalyOverlap.jsx`, `Dashboard.jsx`).

## Alternatives considered

- **True monorepo (merge all seven repos).** Rejected: couples release cycles,
  collapses per-domain readiness gates and provenance, and contradicts the
  artifact-based contract that already works.
- **Keep every repo fully standalone with its own dashboard.** Rejected: this is
  the status quo that produces the six-app switching cost and leaves
  cross-producer correlation with no product home.

## Consequences

- The hub app becomes the single, supported product surface; per-producer
  dashboards are documented as diagnostic-only (not deleted).
- A new integration seam must be built and maintained in `thehub-pr` to load
  aggregate outputs into the server store (see roadmap Phase 1). Until then, the
  frontend continues to rely on `snapshot.json`.
- The producer contract schemas are frozen as the engine/product boundary;
  changes to them become deliberate, versioned events.

## Roadmap

- **Phase 0 — Ratify (this ADR).** Adopt the decision, declare the hub app the
  single product surface, and freeze the producer contract schemas as the stable
  boundary.
- **Phase 1 — Close the seam (highest value).** Add an ingest bridge in
  `thehub-pr` that loads `data/aggregate/*.jsonl` and `correlations.jsonl` into
  the server store the frontend reads, and retire the `snapshot.json` fallback in
  favor of live aggregate data.
- **Phase 2 — Consolidate the surface.** Make `thehub-pr/server/frontend` the
  canonical UI; demote the six producer `dashboard/` / `frontend/` apps to
  diagnostic-only. Fill any per-producer page gaps against live data.
- **Phase 3 — Reduce duplication (incremental).** Extract the shared skeleton the
  producers already clone: a shared UI kit, a shared federation-export/envelope
  schema library, and a shared maintenance/FastAPI core. Standardize run and
  packaging conventions. Do this repo-by-repo behind the frozen contract — never a
  big-bang merge.
- **Phase 4 — Consumer.** Point downstream analytics (PRIIS) at the hub aggregate
  outputs.

## Verification

The decision is a document, but its central claim is testable end to end once
Phase 1 is built:

1. Run the data plane: `make setup && hub fetch --root ws && hub aggregate --root
   .. --out data/aggregate && hub correlate --in data/aggregate`, and confirm
   `data/aggregate/*.jsonl` and `correlations.jsonl` are produced.
2. After Phase 1, start `uvicorn server.backend.main:app` and the frontend with
   `VITE_OFFLINE` off, and confirm the per-producer pages and the
   Crossover/Anomaly views render the live aggregate rather than `snapshot.json` —
   all six engines visible in one app, with no switching.
3. Regression guard: `thehub-pr`'s `tests/` stay green, and each producer's
   `test_suite` remains independently runnable, proving the engines stayed
   decoupled.
