# PRII Federation — Gap-Closure Status

_Authoritative status of the Puerto Rico Integrated Intelligence (PRII) federation._
_Last updated: 2026-10-20 (`docs-sync` is now a required check on `main` in
`centinelas-pr` too, six repos in all — see Part 12 below). Prior update: 2026-10-15
(`docs-sync` required on `main` in five repos — see Part 11 below)._

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
| `centinelas-pr` | pre-officialization signal monitor | ✅ | ✅ | n/a | LIVE: 2026-08-25 refresh produced 100 real signals; production export and Hub package validation passed. Classifier used keyword fallback because `ANTHROPIC_API_KEY` was unavailable |

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

**Part 7 — UI surface consolidation (ADR 0001, Phase 2):**
- The single supported product surface is the Hub app
  (`thehub-pr/server/frontend`): one page per producer plus the cross-domain
  Crossover/Anomaly views only the Hub can host. The Hub UI consolidation —
  grouped navigation, mounted auth routes, Hub-vs-route de-duplication, and
  dead-code/dependency prune — landed here.
- The six producer frontends are **demoted to diagnostic-only** (retained, not
  deleted): each producer frontend carries a "Diagnostic-only surface (ADR 0001,
  Phase 2)" note pointing operators to the Hub as the product surface. This does
  not change any producer runtime, schema, or readiness gate.

**Part 8 — ANOMALOUS intake lane (Centinelas → OVNIS → Hub):**
- Closed the last producer→producer hop so a sentinel Internet find in the
  `ANOMALOUS` domain reaches the OVNIS case corpus. Centinelas already classified
  anomalous items and mapped them to `ovnis-pr`; it now has the egress workflow
  (`dispatch-signals-ovnis.yml`) that emits a `centinelas-signal`
  `repository_dispatch`, and its ovnis payload now carries resolved
  `municipalities` so OVNIS can set a case `location_name`.
- OVNIS gained the matching consumer: `scripts/ingest_centinelas_dispatch.py`
  adapts the dispatched signal into a candidate feed, and `centinelas-intake.yml`
  runs the existing reviewed `import_candidates.py --apply` pipeline (normalize →
  score → dedupe → route into candidate/aux ledgers, master read-only, human-gated
  PR). Non-PR / location-less signals are quarantined by OVNIS's schema gate.
- **The Hub side required no change.** The federation stays artifact-based
  (ADR 0001): once OVNIS promotes and exports these cases, the Hub's existing
  `aggregate → correlate → ingest` path pulls them (`uap_case` →
  `UnifiedCases`/`PatternObservations`) and correlates them with the rest of the
  Federation exactly as before — this entry records that the upstream lane feeding
  those cases is now wired end to end.

**Part 9 — Federation-wide gap-closure audit (2026-09-06):**
- **Branch-protection verification.** Checked `main`'s `protected` flag via the GitHub
  API across all seven repos (this only confirms branch protection is *on*, not which
  specific status checks are required — that needs an admin-scoped ruleset read this
  audit's tooling didn't have). Result, recorded in `governance/merge_blocking_status.json`:
  `moneysweep-pr` and `spiderweb-pr` have `main` protected; `thehub-pr`, `aguayluz-pr`,
  `ovnis-pr`, `skywatcher-pr`, and `centinelas-pr` do **not**. `merge_blocking_status`
  stays `BLOCKED`, now with hard evidence instead of an unverified claim.
- **thehub-pr upgrade-audit Phase 1+2 closure.** `handoff-audit/upgrade-audit/UPGRADE_AUDIT.md`
  was a pre-existing, pre-vetted, HOLD-pending audit of thehub-pr only. Its own
  config/doc phase (DEP-3 documented, DEP-10, SEC-1's loopback-bind half) and small
  correctness-fix phase (BUG-1 connection-safety, BUG-3 body validation, BUG-6 limit
  bounds, BUG-7 manifest error handling, DEP-7 test-client swap) landed, each re-verified
  against current HEAD rather than the audit's now-stale line numbers, with new
  regression tests and a clean `pytest`/`ruff`/`mypy` run. See that document's own
  2026-09-06 status update for exactly what changed, what was found already fixed
  (BUG-2), and what was investigated and deliberately left on HOLD (DEP-2, DEP-4,
  DEP-6/FEAT-2, DEP-1) with reasoning.
- **The other six producer repos were not touched.** Their blockers in the table below
  were re-checked against this document and remain externally gated — skywatcher (real
  FR24 capture), moneysweep-pr (Tranche-B manual exports + API keys), aguayluz
  (per-asset outage granularity) — no code in this pass could close them.

**Part 10 — Branch-protection re-audit and the `docs-sync` required check (2026-10-12):**
- **Re-audit, now with the required-check lists.** Read every active ruleset and the
  classic branch protection on `main` across all seven repos, which the Part 9 audit
  could not do. Nothing protects `main` in `thehub-pr`, `aguayluz-pr`, `ovnis-pr`,
  `skywatcher-pr` or `centinelas-pr`. `moneysweep-pr` and `spiderweb-pr` require only
  their own CI jobs; neither requires `federation-compatibility`, so no federation
  check blocks a merge anywhere. Recorded in `governance/merge_blocking_status.json`;
  `merge_blocking_status` stays `BLOCKED`.
- **`docs-sync` ready to require (ADR 0010, rollout step 3).**
  `tools/require_docs_sync.py --apply` marks it required on `main` per repo: appended to
  `moneysweep-pr`'s ruleset and `spiderweb-pr`'s branch protection, and a new
  `main-required-checks` ruleset in `thehub-pr`, `ovnis-pr` and `skywatcher-pr`. It is a
  repository setting, so a repository administrator runs it; until then the gate stays
  `PROVISIONAL`. `aguayluz-pr` is held because `refresh.yml` pushes its scheduled data
  commits straight to `main`, which a required check would reject. `skywatcher-pr`'s
  `centinelas-handoff.yml` also pushes to `main` but has never been dispatched; it needs
  the same change before it is first used. `centinelas-pr` has not adopted the gate yet.

**Part 11 — `docs-sync` required on `main` in five repos (2026-10-15):**
- **Applied.** A repository administrator ran `tools/require_docs_sync.py --apply`. `main`
  now requires `docs-sync` in `thehub-pr`, `ovnis-pr` and `skywatcher-pr` (a new
  `main-required-checks` ruleset with the repository-admin bypass), in `moneysweep-pr`
  (added to its `main-protection` ruleset) and in `spiderweb-pr` (added to its branch
  protection), so the gate is no longer `PROVISIONAL` there. Re-audit recorded in
  `governance/merge_blocking_status.json`; `merge_blocking_status` stays `BLOCKED`, since
  no federation check is required anywhere and two repos have nothing protecting `main`.
- **Still open.** `aguayluz-pr` stays held because `refresh.yml` pushes to `main`.
  `centinelas-pr` adopted the gate on 2026-10-12 (its PR #166) and is not held: the change
  that held it (#362) was reverted. Its `signal-ledger-refresh.yml`,
  `just-security-monitor.yml` and `el-yunque-access-monitor.yml` push scheduled data
  commits straight to `main`, so the next `--apply` creates a ruleset there and those
  pushes will then be rejected.

**Part 12 — `docs-sync` required on `main` in `centinelas-pr` (2026-10-20):**
- **Applied.** A repository administrator re-ran `tools/require_docs_sync.py --apply`,
  which created a `main-required-checks` ruleset in `centinelas-pr` (repository-admin
  bypass). Six repos now require `docs-sync` on `main`; only `aguayluz-pr` is held.
  Re-audit recorded in `governance/merge_blocking_status.json`; `merge_blocking_status`
  stays `BLOCKED`, since no federation check is required anywhere and `aguayluz-pr` has
  nothing protecting `main`.
- **Consequence.** `centinelas-pr`'s `signal-ledger-refresh.yml`,
  `just-security-monitor.yml` and `el-yunque-access-monitor.yml` push scheduled data
  commits straight to `main` with the Actions token; those pushes are now rejected. The
  first two fail visibly. `el-yunque-access-monitor.yml` ends its push with
  `|| echo "nothing to push"`, so its runs stay green while the refresh is lost. All three
  need to open a pull request instead.

## Blocked gaps — fully specified, waiting on a named external input

Each item below is **code-ready** unless noted; the missing item is named.

| Gap | Node | Unblock requirement |
|---|---|---|
| Live observations | skywatcher | Real FlightRadar24 capture only — the DB→producer-package builder now automates the rest (see skywatcher docs/FR24_PRODUCTION_PROMOTION_RUNBOOK.md). |
| Live exec | moneysweep-pr | Tranche-B manual source exports (hud_drgr, prasa, oficina_contralor, pr_cabilderos) + cor3 portal export (JS-rendered; manual CSV fallback) + `PROPUBLICA_API_KEY`. Runtime keys (FEC/SAM/HigherGov/LDA/Data.gov-family via `X_API_KEY`) are now supplied and 8/14 required sources are live-materialized. |
| Per-asset outage attribution | aguayluz | A finer outage feed; PREPS is island-wide aggregate and third-party outage snapshots remain review-grade until promoted. |
| ECW photomosaic extents | PRIIS | A GDAL ECW driver/plugin or external ECW→GeoTIFF conversion before remaining mosaics can be ingested. |
| `docs-sync` required on `main` | aguayluz | Held until `refresh.yml` opens a pull request instead of pushing to `main`; then an administrator runs `tools/require_docs_sync.py --apply`, since repository settings are outside what a template or CI can change. |
| Scheduled refreshes rejected by `main`'s required check | centinelas | `signal-ledger-refresh.yml`, `just-security-monitor.yml` and `el-yunque-access-monitor.yml` push straight to `main`, which now requires `docs-sync`; they need to open a pull request instead. |
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
