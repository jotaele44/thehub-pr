# Four-Repo Pipeline Logic — Centinelas → MoneySweep → SpiderWeb → TheHub

This document traces, end to end, the logic of the four-repo *located finance*
flow: Centinelas finds a public-interest story (e.g., a construction project),
MoneySweep turns it into a located finance candidate, SpiderWeb attaches and
scores the geography, and the Hub aggregates and correlates the result.

It complements `docs/FEDERATION_TOPOLOGY.md` (which *declares* the grouping and
seam contracts) by walking the actual code paths, the artifact produced at each
hop, and the implementation status of every seam — including where the flow as
commonly described diverges from what is implemented today.

## The mental model

The four repos do **not** form a live linear message bus. They participate in
an artifact-based, hub-and-spoke federation (`ARCHITECTURE.md`): each producer
repo ships a `federation.json` manifest plus a canonical export package, and
the Hub discovers → validates → aggregates → correlates those packages. There
is no shared database, no RPC, and no webhooks. Every inter-repo hop below is a
filesystem/CLI handoff that assumes the repos are checked out as sibling
directories.

Within that federation, the specific chain

```
centinelas-pr ──intake drop──► moneysweep-pr ──bundle──► spiderweb-pr
      │                              │                        │
      └──────────── canonical federation packages ────────────┘
                                     ▼
                                thehub-pr
                     fetch → aggregate → correlate → ingest
```

is the *located finance* sub-flow declared in `docs/FEDERATION_TOPOLOGY.md`.

## Stage 1 — Centinelas: find and classify the story

Repo: `centinelas-pr` (production gate: `PRODUCTION`,
`ready_for_hub_live_execution: true`).

1. **Ingest.** `src/centinelas/ingest/rss.py` (`poll_all`) polls the RSS/Atom
   feeds in `src/centinelas/ingest/sources.yaml`, deduplicates by
   `item_id = sha256(url|published_at)[:16]`, and yields `RawItem`s
   (`src/centinelas/models.py`). The current feed list is global-topical
   (defense, environment, geology, finance, politics wires) — the PR-specific
   pre-officialization sources (legislative calendars, municipal agendas,
   procurement notices) are described as future intake and are not yet wired.
2. **Classify.** `src/centinelas/classify/classifier.py` labels each item with
   one or more of six domains (keyword fast-path in `classify/rules.py`, Claude
   Haiku fallback). The result is a `ClassifiedItem`, which *also* declares
   optional finance/location enrichment fields (`municipalities`, `agencies`,
   `estimated_value`, `signal_stage`, `beat`) — today the classifier never
   populates them; they default empty.
3. **Route.** `src/centinelas/classify/labels.py` `LABEL_TO_REPO` maps domains
   to destination repos: `FINANCIAL` and `POLITICAL` → `moneysweep-pr` (the
   money anchor), `GEO_GEOLOGY` → `spiderweb-pr`, and so on. The Hub always
   receives a copy of every item (`route/router.py` `route()`). Only the
   MoneySweep-bound payload carries the finance/location enrichment block
   (`_FINANCE_ENRICHED_REPOS`, `route/router.py`); the per-target contracts
   live in `src/centinelas/route/contracts/*.schema.json`.
4. **Dispatch.** `src/centinelas/route/dispatch.py` writes each payload to
   `<CENTINELAS_REPOS_DIR (default ~/Developer)>/<repo>/intake/<item_id>.json`
   and records a local `DispatchRecord`. This file drop **is** the
   Centinelas → MoneySweep transport; there is no network hop.

CLI: `centinelas run` (ingest → classify → route → dispatch), per-stage
commands in `src/centinelas/cli.py`. The FastAPI app in `server/backend/` is a
read-only local visibility surface, not a cross-repo endpoint.

## Stage 2 — MoneySweep: turn the signal into a located finance candidate

Repo: `moneysweep-pr` (production gate: `NON_PRODUCTION_DIAGNOSTIC`,
`ready_for_hub_live_execution: false`).

1. **Consume the drop.** `moneysweep/runtime/centinelas_intake.py` reads
   `intake/*.json`, keeps only drops labeled `FINANCIAL`/`POLITICAL`
   (`is_finance_relevant`), and resolves each to a PR municipality with the
   same deterministic engine the rest of MoneySweep uses
   (`moneysweep.runtime.geo_attribution.attribute_geo`). When the drop carries
   no explicit municipality (the normal case today, since the Centinelas
   classifier does not fill the enrichment), it falls back to matching
   municipality aliases in the story's `title`/`body_text`.
2. **Emit candidates.** Each kept drop becomes a *pre-official located finance
   candidate* shaped like a `funding_award` export row:
   `award_id = "CS-CENT-<item_id>"`, `source_id = "centinelas-pr"`,
   `signal_stage = "pre_official"`, `synthetic = false`, a full `location`
   block (`municipality_code/name`, `attribution_source`,
   `attribution_confidence`), and lineage back to the source URL. Amount
   degrades to `0.0` when `estimated_value` is absent.
3. **Run it.** `scripts/ingest_centinelas_signals.py` writes
   `exports/centinelas_intake/{funding_awards,transactions}.jsonl`;
   `run_all.py --ingest-centinelas` runs the ingest **and** the Stage 3 bundle
   build as a standalone lane (exposed to the Hub as the
   `ingest_centinelas` / `build_contract_finance_bundle` hub-callable
   commands in `federation.json`).

**What this stage does *not* do:** it never determines "who got the contract."
The candidate is placed on the map as a pre-official signal; no code matches it
against MoneySweep's officialized awards master (entity resolution,
signal-to-award joining, or `matched_to_moneysweep` lifecycle transitions do
not exist — see Gaps).

## Stage 3 — MoneySweep → SpiderWeb: attach and score the geography

1. **Build the bundle (MoneySweep side).**
   `moneysweep-pr/scripts/build_contract_finance_bundle.py` (reusing
   `scripts/run_contract_finance_geo_reasoning.py` for row-level municipality
   placement) emits the four-file handoff to
   `outputs/contract_finance_bundle/`:
   `contract_awards.geojson`, `financial_flows.geojson`,
   `municipality_funding_density.csv`, and
   `contract_finance_ingest_report.json` (which carries a
   `centinelas_pre_official` provenance block). Export contract `v1.2.0`.
2. **Deliver it.** Transport is a manual operator step — the automated
   delivery hop (`deliver_derivatives.py` + the intake GitHub Actions in both
   repos) was removed in the 2026-06 producer-only pivot.
3. **Score it (SpiderWeb side).**
   `spiderweb-pr/readiness/contract_finance_layer.py`
   (`build_contract_finance_layer`, CLI
   `scripts/build_contract_finance_layer.py --input <bundle>`) scores every
   feature with a weighted model — 0.25·amount + 0.30·entity convergence +
   0.25·municipal density + 0.20·temporal funding pulse — assigns evidence
   tiers T1–T4 (T1/T2 auto-accepted, T3/T4 → manual review), and writes
   `contract_finance_scored_overlay.geojson` plus
   `contract_finance_layer_report.json`, which surfaces the Centinelas
   pre-official feature counts. It consumes artifacts only; it never imports
   MoneySweep code.
4. **SpiderWeb's location primitives** (used across its lanes):
   `scripts/geocode_pr.py` — Census → Nominatim → Google backends behind a
   content-addressed cache, a PR bounding-box gate, and
   `municipio_from_point()` point-in-polygon against `data/municipios.geojson`
   (a runtime data file, not committed; the helper degrades to `""` when it is
   absent).
   Canonical entities gain a representative `{lat, lon}` in
   `scripts/federation_export.py` so the Hub can join them spatially.

Repo: `spiderweb-pr` (production gate: `PRODUCTION`,
`ready_for_hub_live_execution: true`; first real package operator-approved
2026-07-03).

## Stage 4 — TheHub: aggregate, correlate, analyze

All producers — including the three above — reach the Hub the same way: their
`scripts/federation_export.py` writes a canonical package
(`{sources,entities,relationships[,observations]}.jsonl` + sha256 `manifest.json`)
validated against the schemas in `schemas/`. The Hub pipeline (`src/hub/`,
CLI `hub …`) then runs:

1. **fetch** (`fetch.py`) — clones each producer from `registry/producers.yaml`
   and runs its `export_canonical` command behind an allowlist security gate.
2. **aggregate** (`aggregate.py`) — validates packages, unions rows, dedups by
   deterministic id, and stamps every row with `_producers` provenance.
3. **correlate** (`correlate.py` `derive_relationships`) — six strategies, each
   linking only rows from *disjoint* producer sets: shared normalized name,
   shared external id, spatial proximity (haversine ≤ 1 km, grid-indexed),
   temporal proximity (award/transaction dates within 7 days), alert
   footprints, and observation footprints.
4. **ingest** (`ingest.py`) — loads the aggregate into `data/hub.db` (SQLite)
   and projects the UI collections (CrossoverLinks, GraphNodes/Edges,
   GovernanceAlerts, …) served by `server/backend/main.py`.

The located pre-official finance correlates with officialized money and
spatial records **through its anchoring entity's `location`** (spatial) and by
temporal proximity — not by a direct `funding_award.location` join
(`docs/FEDERATION_TOPOLOGY.md`, seam 5). No Hub code change is required for
the sub-flow.

## Worked example — one construction story, every artifact

A wire story "Municipio adjudica contrato de construcción del acueducto" would
move through the flow as:

| # | Where | What happens | Artifact |
|---|-------|--------------|----------|
| 1 | centinelas `ingest/rss.py` | Feed item captured, deduped | `RawItem` (`item_id=abc123…`) |
| 2 | centinelas `classify/` | Labeled `FINANCIAL` (keyword or Haiku) | `ClassifiedItem` in `.centinelas/classified/` |
| 3 | centinelas `route/dispatch.py` | Payload written to MoneySweep + Hub | `moneysweep-pr/intake/abc123….json`, `thehub-pr/intake/abc123….json` |
| 4 | moneysweep `run_all.py --ingest-centinelas` | Drop kept, municipality resolved from title text | `CS-CENT-abc123…` row in `exports/centinelas_intake/funding_awards.jsonl` |
| 5 | moneysweep `build_contract_finance_bundle.py` | Candidate placed into the GeoJSON bundle | `outputs/contract_finance_bundle/` (4 files) |
| 6 | operator | Bundle copied to a SpiderWeb checkout | manual |
| 7 | spiderweb `build_contract_finance_layer.py` | Feature scored, tiered, provenance surfaced | `contract_finance_scored_overlay.geojson` + layer report |
| 8 | both producers `federation_export.py` | Canonical packages refreshed | `{sources,entities,relationships}.jsonl` + `manifest.json` |
| 9 | hub `hub fetch/aggregate/correlate/ingest` | Cross-producer edges derived, DB loaded | `data/aggregate/correlations.jsonl`, `data/hub.db`, UI |

## Implementation status per seam

| Seam | Code | Tests | Live today? |
|------|------|-------|-------------|
| Centinelas ingest + classify | implemented | yes | yes — 274 real signals in `data/signals/live_signals.jsonl` |
| Centinelas → `intake/` drops | implemented | yes | dormant — no `intake/` dirs materialized anywhere; requires sibling checkouts + manual run |
| Classifier finance enrichment (`estimated_value`, `municipalities`, …) | **not implemented** | — | fields always empty; MoneySweep compensates from title/body text |
| MoneySweep intake → pre-official candidates | implemented | yes | dormant — repo is `NON_PRODUCTION_DIAGNOSTIC`; no export artifacts on disk |
| Signal-to-award matching ("who got the contract") | **not implemented** | — | aspirational (schema-level intent only: `matched_to_moneysweep`, `handoff_status`) |
| MoneySweep → SpiderWeb bundle | implemented | yes | manual transport; automated delivery removed 2026-06 |
| SpiderWeb contract-finance scoring | implemented | yes | runs on delivered bundles |
| Producers → Hub canonical packages | implemented | yes | centinelas + spiderweb gates `true`; moneysweep consumed from committed artifacts (`ready_for_hub_live_execution: false`) |
| Hub aggregate → correlate → ingest | implemented | extensive | yes — production-grade |

## Gaps

1. **No semantic signal-to-award matching.** Nothing joins a Centinelas story
   to an actual awarded contract; "who got the contract, for what, when, where,
   why" exists only as contract/schema intent. Pre-official candidates and
   official awards meet only probabilistically, in the Hub's spatial/temporal
   correlators.
2. **The classifier doesn't emit the enrichment its own contract advertises.**
   `moneysweep.schema.json` declares `municipalities`/`agencies`/
   `estimated_value`/`signal_stage`/`beat`; the classifier leaves them empty,
   so downstream amounts degrade to `0.0` and locations depend on text
   fallback.
3. **Manual transport between repos.** Both inter-repo hops (intake drop and
   bundle delivery) assume sibling checkouts and operator-run commands; the
   one automated delivery mechanism was deleted in the 2026-06 pivot.
4. **Two unaligned news routers.** Centinelas's `DomainLabel` routing and the
   deterministic PR-intake router (`moneysweep-pr/shared/pr_intake_router.py`,
   mirrored in spiderweb-pr) use different taxonomies and never reference each
   other.
5. **Duplicated, hand-versioned schemas.** Each seam contract is copied per
   repo (no shared package); version bumps like the v1.2.0 export contract are
   coordinated manually.

## Provenance guardrails (unchanged from the topology doc)

Centinelas-derived rows are pre-official, never officialized money:
`signal_stage="pre_official"`, `synthetic=false`, `source_id="centinelas-pr"`,
full lineage — downstream consumers filter or weight them accordingly, and
location attribution is enrichment, never a filter.
