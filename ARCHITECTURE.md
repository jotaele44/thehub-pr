# PRII Federation — Architecture

## Roles

| Role | Repos | Responsibility |
|------|-------|----------------|
| **Hub** | `thehub-pr` (this repo) | Owns canonical schemas; discovers producers; validates + aggregates their exports; correlates entities across producers into derived relationship edges. |
| **Producer** | `moneysweep-pr`, `spiderweb-pr`, `aguayluz-pr`, `ovnis-pr`, `skywatcher-pr`, `centinelas-pr` | Domain node. Emits `federation.json` + an export package of JSONL streams. |
| **Consumer** | `Puerto-Rico-Integrated-Intelligence-System` (PRIIS) | Downstream analytics. Reads Hub aggregate outputs to rank leads. **Not** the hub. |

The **producer boundary** is artifact-based, not a live network service: producers publish export
packages in their own repos; the Hub fetches and merges them. Producers never share a database with
the Hub and do not depend on Hub RPC. This constraint does not make the Hub's own product surface
artifact-only: under ADR 0001 and ADR 0003, `server/backend` is a live application and may host the
Control Plane and read-only Intelligence API. Evidence ingestion runs as separate workers inside the
Hub deployment boundary. Those workers exchange data with the API only through promoted snapshots;
no producer contract or producer runtime boundary changes.

**One deliberate, scoped exception (ADR 0001, Phase 3):** `packages/prii_maintenance/` is a
dependency-free stdlib package hosted in this repo and consumed by producers as a pinned
git-URL pip dependency — the first time a producer takes a *build-time* dependency on
`thehub-pr`. This does not reverse the artifact-only design: it is one shared library with
no runtime coupling, versioned by tag, bumped one producer at a time.

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
                                       │  link cross-producer entities (name / external-id / location /
                                       │  funding-date / alert / observation footprint)
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
| `alerts` | `alrt_[a-f0-9]{32}` | `federation_alert.schema.json` | optional |

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

## Governance

Cross-repository dependencies, contract versions, compatibility dispositions, impact detection,
and documentation-drift gates are defined under `governance/` and enforced by
`.github/workflows/federation-governance.yml`. Undeclared dependencies and unresolved impacted-repo
compatibility fail closed.

## Decision records

Architecture decisions are recorded under [`docs/adr/`](docs/adr/):

- [ADR 0001 — Federated engines, one hub app](docs/adr/0001-federated-engines-single-hub.md):
  keep the six producers independent as engines and consolidate the final product into the
  single `thehub-pr` app, rather than merging the repositories into a monorepo.
- [ADR 0004 — Federation governance layer](docs/adr/0004-federation-governance-layer.md):
  make cross-repo dependencies, contract compatibility, impact disposition, and documentation
  synchronization machine-enforced merge gates.
