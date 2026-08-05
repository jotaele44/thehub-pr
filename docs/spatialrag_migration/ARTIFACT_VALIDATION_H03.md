# H03 validation and normalization boundary

H03 validates content already registered by H02 and creates deterministic normalized derivatives. It performs no acquisition, provider access, model execution, producer RPC, remote database access, snapshot promotion, retrieval, or runtime query answering.

## Inputs

Each request identifies one H02 content record by:

- `source_artifact_id = artifact-sha256-<digest>`;
- `source_sha256`;
- optional expected MIME type;
- optional Draft 2020-12 JSON schema.

The implementation requires the content record and quarantine bytes to exist locally, remain in `QUARANTINED` lifecycle state, and remain ineligible for an active snapshot.

## Validation

H03 recomputes SHA-256 over the quarantine bytes and fails closed when identity, MIME, schema, content-record state, or local-file requirements do not hold. Every input receives exactly one outcome: `VALIDATED` or `FAILED` with a stable failure code.

Caller-supplied JSON Schemas are meta-validated as Draft 2020-12. Only local fragment references beginning with `#` are permitted. External or file references fail as `SCHEMA_EXTERNAL_REF_DENIED`; malformed schemas and evaluation failures receive stable schema failure codes rather than escaping the input-accounting loop.

## Deterministic derivatives

Supported normalization algorithms are deliberately bounded:

- `canonical-json-v1`: UTF-8 JSON serialized with sorted keys and canonical separators plus exactly one trailing LF;
- `utf8-newline-v1`: CRLF/CR converted to LF, all trailing LFs removed, then exactly one LF appended. Empty text therefore normalizes to one LF byte.

Derivative identity is `artifact-sha256-<derivative_digest>`. Derivative content and source-specific provenance are separate immutable objects:

```text
<storage-root>/
├── normalized/sha256/<prefix>/<derivative_sha256>
├── registry/derivative_content/<prefix>/<derivative_sha256>.json
├── registry/provenance_edges/<prefix>/<edge_sha256>.json
└── registry/validation_runs/<sha256(validation_run_id)>.json
```

A provenance edge key is the SHA-256 of the canonical tuple `(source_sha256, derivative_sha256, normalization_algorithm)`. Distinct source artifacts may therefore reuse the same normalized derivative without colliding or overwriting source-specific provenance.

A later validation run for the same request set replays the immutable ledger. Reusing one validation-run ID with a different request set fails closed.

## Provenance and access

Every provenance edge preserves:

- source and derivative artifact IDs;
- source and derivative SHA-256 digests;
- normalization algorithm and MIME type;
- H02 intended-classification level, restriction floor, `TEST_ONLY` marker and lineage-completeness state;
- `lifecycle_state = QUARANTINED`;
- `active_snapshot_eligible = false`.

Legacy H02 records without persisted intended lineage are represented explicitly with `lineage_complete=false`. H03 does not silently infer the missing restriction floor. H04 blocks certification for those edges.

H03 does not mutate source bytes, H02 content records or H02 intake ledgers.

## Accounting

Two partitions must close:

```text
inputs = validated + failed
validated = derivative_written + derivative_existing
```

The validation report always records `active_snapshot_promoted = false`.
