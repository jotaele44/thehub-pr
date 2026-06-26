# PRII Federation — Architecture

## Roles

| Role | Repos | Responsibility |
|------|-------|----------------|
| **Hub** | `thehub-pr` (this repo) | Owns canonical schemas; discovers producers; validates + aggregates their exports; correlates entities across producers into derived relationship edges. |
| **Producer** | `moneysweep-pr` (moneysweep-pr), `spiderweb-pr`, `aguayluz-pr`, `OVNIS` (ovnis-pr), `skywatcher-pr` | Domain node. Emits `federation.json` + an export package of JSONL streams. |
| **Consumer** | `Puerto-Rico-Integrated-Intelligence-System` (PRIIS) | Downstream analytics. Reads Hub aggregate outputs to rank leads. **Not** the hub. |

The federation is **artifact-based**, not a live network service: producers publish export
packages in their own repos; the Hub fetches and merges them. There is no shared database or RPC.

## Data flow

```
producer repo                         thehub-pr
─────────────                         ─────────
federation.json   ──(discover)──▶  registry/producers.yaml
exports/…/manifest.json + *.jsonl ─(fetch)──▶ hub.validate.validate_package
                                       │  schema-validate every row, verify sha256 + counts
                                       ▼
                                  hub.aggregate.aggregate
                                       │  dedup by deterministic id, record _producers provenance
                                       ▼
                            data/aggregate/{sources,entities,relationships,…}.jsonl
                            data/aggregate/graph_summary.json
                                       │
                                  hub.correlate.correlate
                                       │  link cross-producer entities (name / external-id / location / funding-date)
                                       ▼
                            data/aggregate/correlations.jsonl  (derived federation_relationship rows)
```

## Canonical streams & id namespaces

| Stream | Id pattern | Schema | Required? |
|--------|-----------|--------|-----------|
| `sources` | `src_[a-f0-9]{32}` | `federation_source.schema.json` | yes |
| `entities` | `ent_[a-f0-9]{32}` | `federation_entity.schema.json` | yes |
| `relationships` | `rel_[a-f0-9]{32}` | `federation_relationship.schema.json` | yes |
| `funding_awards` | `awd_[a-f0-9]{32}` | `federation_funding_award.schema.json` | optional |
| `transactions` | `txn_[a-f0-9]{32}` | `federation_transaction.schema.json` | optional |
| `observations` | producer-defined | producer-specific (e.g. airspace) | optional |

Ids are **deterministic functions of row content**, so the same fact emitted by two producers
collapses to one aggregated row whose `_producers` list records every contributor.

## Producer registration protocol

1. Add `federation.json` to the producer repo root (validate with `hub validate-manifest`).
2. Produce an export package and validate it with `hub validate-package`.
3. Add an entry to [`registry/producers.yaml`](registry/producers.yaml) here, with `status`:
   - `planned` → repo not yet created
   - `pending` → repo exists, not yet conformant
   - `ready_for_discovery` → `federation.json` on `main`, exports validate
4. The Hub's `aggregate` step then includes the producer automatically.

## Readiness gates

`federation_readiness_gate.ready_for_hub_discovery` lets the Hub list/aggregate a producer's
already-published exports. `ready_for_hub_live_execution` (running the producer's
`hub_callable_commands` against live sources) is a stricter gate, typically blocked until manual
sources are materialized and runtime keys are supplied.
