# H02 artifact intake boundary

H02 introduces the first executable Evidence Engine intake primitive ratified by ADR 0006. It accepts caller-supplied local files and an already-created `acquisition_receipt.v1`; it does not acquire data from a provider.

## Storage layout

```text
<storage-root>/
├── quarantine/sha256/<prefix>/<sha256>
├── registry/content/<prefix>/<sha256>.json
└── registry/intakes/<sha256(receipt_id)>.json
```

Artifact identity is `artifact-sha256-<sha256>`. Bytes that pass the regular-file and pre-read size gates are written to their content-addressed quarantine path before digest, MIME, classification, or registry acceptance is finalized. A digest or MIME failure leaves the bytes quarantined and unregistered. Oversize, missing, non-regular, and symlink inputs are rejected without reading or storing them.

## Registration and replay

Content records are immutable and keyed by SHA-256. Re-registering identical bytes through a later receipt reuses the existing content record. Replaying the same receipt and artifact manifest returns the existing intake ledger. Reusing a receipt ID with different receipt content or a different manifest fails closed.

No accepted artifact leaves `QUARANTINED` lifecycle state in H02. The content record explicitly sets `active_snapshot_eligible=false`, and the intake report explicitly sets `active_snapshot_promoted=false`.

## Access classification

The intake binding preserves all classification sources:

- receipt classification;
- artifact-manifest classification;
- caller-supplied ancestor classifications.

The intended classification uses the most restrictive non-test level defined by `access_classification.v1`. `TEST_ONLY` remains an orthogonal marker and is retained with its non-test restriction floor. While the artifact is in intake quarantine, its effective access classification is always `QUARANTINED`.

## Complete accounting

Each input is assigned exactly one intake disposition:

- `REGISTERED_QUARANTINED`;
- `EXISTING_QUARANTINED`;
- `REJECTED_QUARANTINED`;
- `REJECTED_NOT_STORED`.

Two independent partitions must close:

```text
inputs = registered + existing + rejected
inputs = quarantine_written + quarantine_existing + not_stored
```

## Excluded scope

H02 adds no network provider adapter, credential access, model execution, producer RPC, Skywatcher database access, remote database service, deletion workflow, snapshot promotion, retrieval, model context, or runtime query-answering path.
