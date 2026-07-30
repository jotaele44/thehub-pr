# Skywatcher AI and imagery contract namespace

These Draft 2020-12 schemas implement the additive contract foundation ratified by ADR 0006.

They are deliberately isolated under `schemas/contracts/skywatcher_ai/` because the open Phase-1 contract reconciliation PR owns the existing flat `schemas/contracts/` namespace. The namespace avoids parallel-file collisions while preserving a clear migration path into the broader contract registry.

The schemas define records only. They add no provider SDK, model execution, network route, database access or producer RPC.

- `acquisition_receipt.v1.schema.json`
- `bounded_producer_job.v1.schema.json`
- `legacy_artifact_disposition.v1.schema.json`
- `model_field_provenance.v1.schema.json`
- `satim_provisional_signal.v1.schema.json`
- `skywatcher_ai_common.v1.schema.json`

## Phase-1 contract compatibility

This namespace is additive to the broader Phase-1 contracts proposed in TheHub PR #139. It does not redefine retrieval, snapshot, claim, evidence-lifecycle or analytical-run ownership.

Compatibility rules:

- `classification` uses the same seven level values as `access_classification.v1`; the broader contract remains authoritative for inheritance and effective-access calculation.
- `model_field_provenance.v1` stores immutable field-level copies of provider/model identifiers and also requires `model_run_receipt_id`; it does not replace `provider_reference.v1` or `analytical_run_receipt.v1`.
- `acquisition_receipt.v1` and `bounded_producer_job.v1` are operational child receipts that may be referenced by a later analytical-run envelope.
- No schema in this directory defines an `ACTIVE` snapshot, retrieval object, claim ledger or citation surface.

`tests/test_skywatcher_ai_contracts.py` activates cross-namespace checks automatically when the Phase-1 schemas are present on the target branch.
