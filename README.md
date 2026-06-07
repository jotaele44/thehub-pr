# thehub-pr — the PRII Federation Hub

The central node of the **Puerto Rico Integrated Intelligence (PRII) federation**.
The Hub does not collect data itself. It **discovers** producer nodes, **validates**
that their exports conform to the shared federation contract, and **aggregates** them
into one cross-domain graph.

```
            ┌──────────────────────────── thehub-pr (this repo) ───────────────────────────┐
            │  registry/producers.yaml → fetch federation.json → validate export → aggregate │
            └───────────────▲───────────────▲───────────────▲───────────────▲───────────────┘
                            │               │               │               │
              moneysweep-pr │   spiderweb-pr│    aguayluz-pr│    prufon-pr  │  skywatcher-pr
            (Contract-Sweeper)  (spatial/ops)  (water/grid)   (anomaly)       (airspace)
                  PRODUCERS  ──────────────  emit federation.json + JSONL export packages
```

A separate **analytical consumer** (`Puerto-Rico-Integrated-Intelligence-System`) reads the
Hub's aggregate outputs to rank leads. It is *not* the Hub.

## The contract (what a producer must satisfy)

1. A root **`federation.json`** conforming to [`schemas/repo_federation_manifest.schema.json`](schemas/repo_federation_manifest.schema.json):
   `schema_version: repo_federation_manifest_v1`, `hub_parent: thehub-pr`, offline-safe
   `hub_callable_commands` (`setup`, `test_suite`), `canonical_outputs`, and a
   `federation_readiness_gate`.
2. An **export package** — a directory with `manifest.json`
   ([`federation_export_manifest.schema.json`](schemas/federation_export_manifest.schema.json))
   plus JSONL streams (`sources`, `entities`, `relationships`, optionally
   `funding_awards`, `transactions`, `observations`). Every row carries a deterministic id
   (`src_/ent_/rel_/awd_/txn_…`), a `lineage` object, `confidence`, `synthetic`, and ISO
   timestamps. The manifest records each file's `sha256` and `record_count`.

The Hub owns the canonical schemas under [`schemas/`](schemas/); producers conform to them.

## Usage

```bash
make setup                                   # pip install -e ".[dev]"
hub list                                      # show registered producers
hub validate-manifest ../Contract-Sweeper/federation.json
hub validate-package <export-dir>            # check a producer export package
hub fetch --run --root ws                     # clone/refresh producers from GitHub (+ run their export)
hub aggregate --root .. --out data/aggregate # merge all discoverable producer packages
make test
```

See [docs/FEDERATION_STATUS.md](docs/FEDERATION_STATUS.md) for the gap-closure status —
what's live, what's blocked, and each blocked gap's unblock requirement.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the topology, node roles, and the producer
registration protocol.
