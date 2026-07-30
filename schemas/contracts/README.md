# Contract schemas (Phase 1)

These 12 flat schemas are the authoritative **Evidence Engine / Intelligence Engine / Control Plane contract boundary** for snapshots, retrieval objects, provenance, claims, abstention, access classification, retrieval profiles, provider reproducibility, lifecycle state and contradiction-preserving entity resolution.

They implement ADR 0003 and the spatial-RAG migration contract model. They remain distinct from the additive ADR 0006 child namespace under `schemas/contracts/skywatcher_ai/`.

## Authority boundary

The flat Phase-1 contracts own:

- effective access classification and inheritance;
- evidence and query lifecycle state;
- certified and `ACTIVE` snapshot identity;
- retrieval-object identity;
- analytical-run provider references;
- claim, contradiction and abstention structure;
- entity-resolution decisions.

The ADR 0006 `skywatcher_ai/` child namespace owns only bounded acquisition/producer receipts, field-level model provenance, provisional SATIM signals and legacy-artifact disposition. It may reference or duplicate immutable identifiers required for audit, but it does not redefine access inheritance, analytical-run authority, retrieval objects, claims, citations or snapshot promotion.

## Frozen boundary

`schemas/FROZEN.sha256` records every schema in:

- `schemas/*.json`;
- `schemas/contracts/*.json`;
- `schemas/contracts/**/*.json`, including `skywatcher_ai/`.

`tests/test_schema_freeze.py` fails if any frozen schema changes, appears or disappears without a reviewed manifest update. Regenerate deliberately with:

```bash
python tests/test_schema_freeze.py --update
```

## Reconciliation ledger

| File | Status | Purpose |
|---|---|---|
| `snapshot_manifest.v1.schema.json` | Adopted | Immutable certified/query snapshot manifest and rollback metadata. |
| `access_classification.v1.schema.json` | Adopted | Seven access classes with most-restrictive inheritance. |
| `abstention.v1.schema.json` | Adopted | Typed answering and abstention outcomes. |
| `evidence_lifecycle.v1.schema.json` | Adopted | Immutable evidence-build lifecycle. |
| `query_lifecycle.v1.schema.json` | Adopted | Index/query lifecycle; only `ACTIVE` answers normal queries. |
| `provenance.v1.schema.json` | Reconciled | Evidence-tier authority, temporal model, synthetic state and access classification. |
| `retrieval_object.v1.schema.json` | Reconciled | Eight retrieval-object types with document and spatial provenance. |
| `claim_ledger.v1.schema.json` | Reconciled | Supported claims, contradictions and confidence basis. |
| `analytical_run_receipt.v1.schema.json` | Reconciled | Snapshot, profile, provider and access-context reproducibility. |
| `retrieval_profile.v1.schema.json` | New | Versioned eight-signal retrieval profiles. |
| `provider_reference.v1.schema.json` | New | Immutable provider/model revision references. |
| `entity_resolution.v1.schema.json` | New | Reversible, evidence-backed entity-resolution decisions. |

## Non-goals

No runtime component reads or writes these schemas in this PR. No database is provisioned. No model/provider SDK, network route, producer RPC or assistant execution surface is introduced.
