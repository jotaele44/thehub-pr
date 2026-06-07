# PRII Federation — Gap-Closure Status

_Authoritative status of the Puerto Rico Integrated Intelligence (PRII) federation._
_Last updated: 2026-06-07 (Part 4 — Full Gap Closure, phases Z1–Z3 landed)._

The federation is **artifact-based**: producers emit a discovery manifest
(`federation.json`) plus a canonical export package (`sources/entities/
relationships.jsonl` + `manifest.json`); the Hub (`thehub-pr`) discovers,
validates, and aggregates them. `hub fetch` can now populate a workspace
straight from GitHub, so aggregation no longer assumes local checkouts.

## Node status

| Node (program_id) | Role | Discovery | Live exec | Canonical `location` | Notes |
|---|---|:--:|:--:|:--:|---|
| `thehub-pr` | Hub (registry+validator+aggregator) | — | — | — | not a producer |
| `moneysweep-pr` (Contract-Sweeper) | public-money | ✅ | ⛔ | n/a (no point coords) | needs API keys + Tranche-B (below) |
| `spiderweb-pr` | spatial/operational query-hub | ✅ | ⛔ | ✅ records project geometry | needs real (non-synthetic) envelope rows |
| `aguayluz-pr` | water/grid | ✅ | ✅ | ✅ 273/273 assets | power + PREPS + water/wastewater live |
| `prufon-pr` (PRUFON) | anomaly/UAP | ✅ | ⛔ | n/a | placeholder ledger — needs real cases |
| `skywatcher-pr` | airspace | ✅ | ⛔ | ✅ observations | synthetic — needs FR24 capture |

## What is closed

**Parts 1–3** built every producer + the Hub, closed the producer↔Hub↔consumer
communication paths, and wired real data (aguayluz power+PREPS, PRIIS spiderweb
layers + satellite manifest, Contract-Sweeper federal publications, skywatcher
airport reference).

**Part 4 — Full Gap Closure (this round):**
- **Z1 — state reconciliation.** Hub registry statuses + spiderweb readiness gate
  now reflect reality (removed the stale "spatial correlation is a follow-up"
  condition; G3-C2 shipped `correlate_spatial`/`correlate_by_external_id`).
- **Z2 — geometry on canonical entities.** `federation_entity.schema.json` carries
  an optional WGS84 `location {lat, lon, municipality?}`. Producers that carry
  coordinates populate it: aguayluz (39/39 assets), spiderweb (observations/
  events/tracks project their GeoJSON point), skywatcher (observations).
- **Z3 — `hub fetch`.** Clone/refresh producers into a workspace and optionally
  run their `export_canonical`, so `hub fetch --run && hub aggregate` rebuilds the
  aggregate from clean GitHub clones.
- **Z5 — aguayluz water/wastewater assets.** `scripts/ingest_water.py` loads the
  public PR_Geodata OSM layers (water treatment / wastewater / pumping / reservoir)
  → 234 `utility_assets` merged with the 39 power assets = **273 total**; centroids
  carried as entity `location` (review_status=needs_review, T3).

**Cross-producer spatial intelligence now works** (the Z2 payoff). Aggregating the
four live producers yields **411 entities / 283 with `location`**; feeding them
through spiderweb's `correlate_spatial` produces **25 cross-producer spatial links
at 5 km** — e.g. a spiderweb airspace event ↔ aguayluz "San Juan Combined Cycle
(PREPA)" substation. Before Z2 the entities were location-less and this join was
impossible.

## Blocked gaps — fully specified, waiting on a named external input

Each item below is **code-ready**; only the named input is missing.

| Gap | Node | Unblock requirement |
|---|---|---|
| Live observations | skywatcher | Real FlightRadar24 capture → ILAP intake; the adapter + ILAP bridge then run in production (no FR24 data exists in `/Documents/Data`). |
| Real cases | PRUFON | Real UAP case records → `data/master/master_cases.jsonl` (replace the placeholder); the export adapter is ready. |
| Live exec | Contract-Sweeper | Tranche-B manual source exports + PR-gov scraper queue + runtime API keys (`FEC_API_KEY`, `SAM_API_KEY`, `HIGHERGOV_API_KEY`, `LDA_API_KEY`, `OPENCORPORATES_API_TOKEN`) supplied locally. (Issue #87 depends on these.) |
| Production export | spiderweb | Real (non-synthetic) envelope rows from its FR24/ILAP pipeline. |
| Per-asset outage attribution | aguayluz | A finer outage feed; PREPS is island-wide aggregate. |
| ECW photomosaic extents | PRIIS | A GDAL ECW driver/plugin (or external ECW→GeoTIFF), then `ingest_satellite_mosaics.py` extracts the remaining ~22 mosaics (3/75 done via KMZ). |
| Repo deletion | `jotaele44/Aerospace-Intelligence-Tool` | `gh auth refresh -s delete_repo` then `gh repo delete … --yes`. Content preserved as `archive/aerospace-intelligence-tool/*` tags in skywatcher-pr. |
| Repo deletion | `jorgegonzalez44/Puerto-Rico-Airspace-Intelligence-Tool` | Delete from the **jorgegonzalez44** account (its contract is already in skywatcher-pr). |

## Remaining code-closable (deferred this round)

- **Z4 — cross-repo intake-lane delivery (#114/#41).** Contract-Sweeper already has
  the router + raw-intake subsystem; the missing piece is the cross-repo *delivery*
  (write spiderweb's `data/normalized/spatial_intake_items.csv` + open the PR).
  Medium-large; not an empty pipe.
- **Z6 — federal publications → canonical_v1.** Fold `data/sources/
  federal_publications.jsonl` (4,248 sources) into Contract-Sweeper's canonical_v1
  evidence layer. Deferred: large CI surface, 18×-es the aggregate source count,
  no identified downstream consumer (PRIIS scores award/transaction streams).
- **Skywatcher engine port** (GEBCO/mission/satellite from the archive tag) — does
  not unblock the node (FR24-blocked regardless); left in the archive tag.
- **Carve-out branches** (CS ×3, spiderweb ×6) — kept as deliberate salvage-first;
  each is archive-tagged. Delete only after a per-branch salvage review.

## Reproduce

```bash
# from a parent dir holding the producer checkouts (by repo name):
PYTHONPATH=src python3 -m hub aggregate --root <parent> --out /tmp/prii_agg
# or pull fresh from GitHub first:
PYTHONPATH=src python3 -m hub fetch --run --root ws && \
PYTHONPATH=src python3 -m hub aggregate --root ws --out /tmp/prii_agg
```
