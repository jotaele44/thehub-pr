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

## Deterministic derivatives

Supported normalization algorithms are deliberately bounded:

- `canonical-json-v1`: UTF-8 JSON serialized with sorted keys and canonical separators plus one trailing newline;
- `utf8-newline-v1`: UTF-8 text with CRLF/CR converted to LF and at most one required trailing newline.

Derivative identity is `artifact-sha256-<derivative_digest>`. Bytes and provenance records use immutable write-once paths:

```text
<storage-root>/
├── normalized/sha256/<prefix>/<derivative_sha256>
├── registry/derivatives/<prefix>/<derivative_sha256>.json
└── registry/validation_runs/<sha256(validation_run_id)>.json
```

A later validation run for the same source content reuses an identical derivative. Reusing one validation-run ID with a different request set fails closed.

## Provenance and access

Every derivative provenance record preserves:

- source and derivative artifact IDs;
- source and derivative SHA-256 digests;
- normalization algorithm and MIME type;
- inherited source access classification;
- `lifecycle_state = QUARANTINED`;
- `active_snapshot_eligible = false`.

H03 does not mutate source bytes, source content records, or H02 intake ledgers.

## Accounting

Two partitions must close:

```text
inputs = validated + failed
validated = derivative_written + derivative_existing
```

The validation report always records `active_snapshot_promoted = false`.
