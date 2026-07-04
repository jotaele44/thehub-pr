# PRII Federation — Gap-Closure Status

_Authoritative status of the Puerto Rico Integrated Intelligence (PRII) federation._
_Last updated: 2026-07-04 (follow-up sweep: spiderweb + centinelas promoted to live execution)._ 

The federation is **artifact-based**: producers emit a discovery manifest
(`federation.json`) plus a canonical export package (`sources/entities/
relationships.jsonl` + `manifest.json`); the Hub (`thehub-pr`) discovers,
validates, and aggregates them. `hub fetch` can populate a workspace straight
from GitHub, so aggregation no longer assumes local checkouts.

## Node status

| Node (program_id) | Role | Discovery | Live exec | Canonical `location` | Notes |
|---|---|:--:|:--:|:--:|---|
| `thehub-pr` | Hub (registry+validator+aggregator) | — | — | — | not a producer |
| `moneysweep-pr` (moneysweep-pr) | public-money | ✅ | ⛔ | n/a (no point coords) | 9/14 required sources live-materialized; blocked on Tranche-B manual exports + cor3 portal (probes confirmed JS/operator-gated) |
| `spiderweb-pr` | spatial/operational producer | ✅ | ✅ | ✅ records project geometry | LIVE: real production package hub-validated; blocker_class=ready; corpus grows with the revived intake lane |
| `aguayluz-pr` | water/grid | ✅ | ✅ | ✅ 273/273 assets | power + PREPS + water/wastewater live; outage granularity remains caveated |
| `ovnis-pr` (OVNIS) | historical case corpus | ✅ | ✅ | n/a | 470 real master cases (0 synthetic); production canonical export live |
| `skywatcher-pr` | airspace | ✅ | ⛔ | ✅ observations | synthetic package only — needs real FR24 capture/export |
| `centinelas-pr` | pre-officialization signal monitor | ✅ | ✅ | n/a | LIVE: 274 real RSS signals bridged into the ledger; production export hub-validated; PR-matter source families remain future intake |

## What is closed

**Parts 1–3** built every producer + the Hub, closed the producer↔Hub↔consumer
communication paths, and wired real data where available (aguayluz power+PREPS,
moneysweep-pr federal publications, skywatcher airport reference, and retained
spatial layers).

**Part 4 — Full Gap Closure:**
- **Z1 — state reconciliation.** Hub registry statuses + spiderweb readiness gate
  reflect the producer-only boundary. Cross-producer correlation is owned by the
  Hub's `hub correlate` path, not by Spiderweb.
- **Z2 — geometry on canonical entities.** `federation_entity.schema.json` carries
  an optional WGS84 `location {lat, lon, municipality?}`. Producers that carry
  coordinates populate it: aguayluz assets, spiderweb retained spatial records,
  and skywatcher observations.
- **Z5 — aguayluz water/wastewater assets.** `scripts/ingest_water.py` loads the
  public PR_Geodata OSM layers (water treatment / wastewater / pumping / reservoir)
  into review-grade utility assets. These rows enrich the spatial layer but retain
  source-tier and review caveats.
- **Z3 — `hub fetch`.** Clone/refresh producers into a workspace and optionally
  run their `export_canonical`. The clone path has been exercised; the `--run`
  path remains dependent on each producer's local dependencies and external inputs.

**Part 5 — README/link/schema gate sweep:**
- Top-level README boundaries were realigned across the connected repos.
- The Hub README producer map now matches `registry/producers.yaml`.
- `skywatcher-pr` owns the airspace / FR24 role; `spiderweb-pr` remains the
  spatial / operational producer.
- Schema-gate drift is being closed so producer identity, sample package manifests,
  and validators use the active federation ids.

**Part 6 — operational `alerts` stream:**
- New canonical `alerts` stream (`federation_alert.schema.json`, id `alrt_…`) wired
  into `STREAM_SCHEMA`/`STREAM_ID_FIELD`, the export-manifest enum, and the bridge.
- `aguayluz-pr` emits it from its operational alert system (10 sector modules;
  hydro/power/weather/contamination/dam-safety active). The Hub validates,
  aggregates, and — via `hub correlate` — links an alert's anchor entity to
  co-located cross-producer entities (`alert_affects_entity`, match_basis `location`).

## Blocked gaps — fully specified, waiting on a named external input

Each item below is **code-ready** unless noted; the missing item is named.

| Gap | Node | Unblock requirement |
|---|---|---|
| Live observations | skywatcher | Real FlightRadar24 capture only — the DB→producer-package builder now automates the rest (see skywatcher docs/FR24_PRODUCTION_PROMOTION_RUNBOOK.md). |
| Live exec | moneysweep-pr | Tranche-B manual source exports (hud_drgr, prasa, oficina_contralor, pr_cabilderos) + cor3 portal export (JS-rendered; manual CSV fallback) + `PROPUBLICA_API_KEY`. Runtime keys (FEC/SAM/HigherGov/LDA/Data.gov-family via `X_API_KEY`) are now supplied and 8/14 required sources are live-materialized. |
| Per-asset outage attribution | aguayluz | A finer outage feed; PREPS is island-wide aggregate and third-party outage snapshots remain review-grade until promoted. |
| ECW photomosaic extents | PRIIS | A GDAL ECW driver/plugin or external ECW→GeoTIFF conversion before remaining mosaics can be ingested. |
| Repo deletion | `jotaele44/Aerospace-Intelligence-Tool` | `gh auth refresh -s delete_repo` then `gh repo delete … --yes`. Content preserved in `skywatcher-pr` archive/provenance notes. |
| Repo deletion | `jorgegonzalez44/Puerto-Rico-Airspace-Intelligence-Tool` | Delete from the **jorgegonzalez44** account after confirming no unsalvaged material remains. |

## Remaining code-closable

- **Cross-repo intake-lane delivery.** moneysweep-pr has the router + raw-intake
  subsystem; the missing piece is delivery into Spiderweb's normalized intake lane
  and PR automation.
- **Federal publications → canonical_v1.** Fold `data/sources/federal_publications.jsonl`
  into moneysweep-pr's canonical_v1 evidence layer when a downstream consumer
  needs the expanded source count.
- **Skywatcher engine port.** Optional terrain / mission / satellite components are
  not the live-execution blocker; real FR24 input is.
- **Carve-out branches.** Keep archive/salvage branches until a per-branch salvage
  review confirms they are safe to delete.

## Reproduce

```bash
# Aggregate from local checkouts. Each producer's exports/federation must exist —
# materialise it first by running that producer's export_canonical command.
PYTHONPATH=src python3 -m hub aggregate --root <parent> --out /tmp/prii_agg

# Clone-only fetch.
PYTHONPATH=src python3 -m hub fetch --root ws

# Clone + run each producer's export, then aggregate.
# Requires each producer's dependencies and external inputs where applicable.
PYTHONPATH=src python3 -m hub fetch --run --root ws && \
PYTHONPATH=src python3 -m hub aggregate --root ws --out /tmp/prii_agg
```
