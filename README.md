# thehub-pr — PRII Federation Hub

`thehub-pr` is the central control-plane and aggregation node for the Puerto Rico Integrated Intelligence (PRII) federation.

The Hub does not own domain data collection. It discovers producer repositories, validates their manifests and export packages, aggregates canonical streams, and derives cross-producer relationships from normalized names, external identifiers, locations, dates, source lineage, and confidence metadata.

```text
            ┌──────────────────────────── thehub-pr ────────────────────────────┐
            │ registry → fetch federation.json → validate exports → aggregate    │
            │ aggregate → correlate → publish federation graph                   │
            └───────────────▲───────────────▲───────────────▲───────────────▲────┘
                            │               │               │               │
              moneysweep-pr │   spiderweb-pr│    aguayluz-pr│    ovnis-pr  │  skywatcher-pr
            (moneysweep-pr) (spatial/ops)  (water/grid)   (case corpus)    (airspace)
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
make test
```

## Boundary rules

| Rule | Meaning |
|---|---|
| Producers collect and normalize | Domain repos own data acquisition and local validation |
| Hub validates and aggregates | Hub owns federation schemas, registry, package validation, readiness rollup, and aggregate graph generation |
| Hub correlates across producers | Cross-domain joins belong here, not inside individual producer repos |
| Consumers rank and analyze | Analytical systems consume Hub outputs; they do not replace the Hub |

## Status docs

See [docs/FEDERATION_STATUS.md](docs/FEDERATION_STATUS.md) for gap-closure status and [ARCHITECTURE.md](ARCHITECTURE.md) for topology, node roles, and producer registration protocol.
