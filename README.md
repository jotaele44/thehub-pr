# thehub-pr — PRII Federation Hub

`thehub-pr` is the central control-plane and aggregation node for the Puerto Rico Integrated Intelligence (PRII) federation.

The Hub does not own domain data collection. It discovers producer repositories, validates their manifests and export packages, aggregates canonical streams, and derives cross-producer relationships from normalized names, external identifiers, locations, dates, source lineage, and confidence metadata.

```text
            ┌──────────────────────────── thehub-pr ────────────────────────────┐
            │ registry → fetch federation.json → validate exports → aggregate    │
            │ aggregate → correlate → publish federation graph                   │
            └───────────────▲───────────────▲───────────────▲───────────────▲────┘
                            │               │               │               │
   moneysweep-pr │ spiderweb-pr │ aguayluz-pr │ ovnis-pr │ skywatcher-pr │ centinelas-pr
   (public money)  (spatial/ops)  (water/grid) (case corpus) (airspace)   (pre-signal)
                   PRODUCERS emit federation.json + canonical export packages
```

A separate analytical consumer may read Hub aggregate outputs to rank leads. It is not the Hub.

## Active producer map

| Federation id | Repository | Domain | Hub stance |
|---|---|---|---|
| `moneysweep-pr` | [`moneysweep-pr`](https://github.com/jotaele44/moneysweep-pr) | Public money, procurement, grants, recovery, influence, fiscal-control records | Producer; not production-certified master dataset until gates pass |
| `spiderweb-pr` | [`spiderweb-pr`](https://github.com/jotaele44/spiderweb-pr) | Spatial / operational evidence and GIS bridge exports | Producer; no longer active FR24 owner |
| `aguayluz-pr` | [`aguayluz-pr`](https://github.com/jotaele44/aguayluz-pr) | Water, wastewater, power, outage, and recovery-project monitoring | Real-data partial producer |
| `ovnis-pr` | [`OVNIS`](https://github.com/jotaele44/ovnis-pr) | Puerto Rico historical case corpus | Case-corpus producer |
| `skywatcher-pr` | [`skywatcher-pr`](https://github.com/jotaele44/skywatcher-pr) | Airspace / aircraft intelligence and FR24 ingestion | Airspace producer; live execution blocked until non-synthetic observation export exists |
| `centinelas-pr` | [`centinelas-pr`](https://github.com/jotaele44/centinelas-pr) | Pre-officialization public-interest signal monitoring (upstream of moneysweep-pr) | Pre-signal producer; live execution blocked until real (non-synthetic) signal intake exists |

## The producer contract

1. Root `federation.json` conforming to [`schemas/repo_federation_manifest.schema.json`](schemas/repo_federation_manifest.schema.json).
2. Offline-safe `hub_callable_commands` such as `setup`, `test_suite`, and export commands.
3. `canonical_outputs` describing where export packages and reports are emitted.
4. A `federation_readiness_gate` stating discovery/live-execution status and blockers.
5. Export package with `manifest.json` plus JSONL streams such as:

```text
sources.jsonl
entities.jsonl
relationships.jsonl
funding_awards.jsonl
transactions.jsonl
observations.jsonl
alerts.jsonl
```

Every row should carry deterministic ids, lineage, confidence, synthetic/test flags where applicable, and ISO timestamps. The package manifest records each file's SHA-256 and record count.

## Usage

```bash
make setup                                   # pip install -e ".[dev]"
hub list                                     # show registered producers
hub validate-federation --root ..            # roll up all producer manifests/packages
hub validate-federation --root .. --json     # machine-readable readiness report
hub validate-manifest ../moneysweep-pr/federation.json
hub validate-package <export-dir>            # validate producer export package
hub fetch --run --root ws                    # clone/refresh producers and run exports when allowed
hub aggregate --root .. --out data/aggregate # merge discoverable packages
hub correlate --in data/aggregate            # derive cross-producer relationship edges
hub ingest --in data/aggregate --db data/hub.db  # load the aggregate into the app store
make test
```

## The hub app (single product)

The hub ships as one product — a FastAPI backend that serves both the JSON API and the
React UI, so operators use a single app instead of switching between per-producer dashboards.

```bash
# 1. Load real federation data into the app store (data/hub.db)
hub aggregate --root .. --out data/aggregate && hub correlate --in data/aggregate
hub ingest --in data/aggregate --db data/hub.db

# 2. Build the UI once (outputs server/frontend/dist/, git-ignored)
npm --prefix server/frontend ci
npm --prefix server/frontend run build

# 3. Serve UI + API on one origin
python -m uvicorn server.backend.main:app --port 8000   # open http://localhost:8000/
```

`hub ingest` maps the canonical aggregate streams onto the collections the UI reads
(`sources → UnifiedSources`, `entities → GraphNodes`, `relationships → GraphEdges`,
`alerts → GovernanceAlerts`, `correlations → CrossoverLinks`); the mapping lives in one place,
`COLLECTION_ADAPTERS` in [`src/hub/ingest.py`](src/hub/ingest.py). Pages backed by these
collections (Sources, the Spiderweb graph, cross-producer links) render live aggregate data;
domain-heavy pages that need per-domain fields the aggregate does not yet carry (contracts,
feeds, cases) stay empty until producers emit that data. If `dist/` is not built, the backend
runs API-only and the UI can be served separately with `npm --prefix server/frontend run dev`
(Vite on :5173). The per-producer `dashboard/`/`frontend/` apps are diagnostic-only; the hub
app is the product.

## Boundary rules

| Rule | Meaning |
|---|---|
| Producers collect and normalize | Domain repos own data acquisition and local validation |
| Hub validates and aggregates | Hub owns federation schemas, registry, package validation, readiness rollup, and aggregate graph generation |
| Hub correlates across producers | Cross-domain joins belong here, not inside individual producer repos |
| Consumers rank and analyze | Analytical systems consume Hub outputs; they do not replace the Hub |

## Status docs

See [docs/FEDERATION_STATUS.md](docs/FEDERATION_STATUS.md) for gap-closure status and [ARCHITECTURE.md](ARCHITECTURE.md) for topology, node roles, and producer registration protocol.
