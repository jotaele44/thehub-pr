# Skywatcher AI and imagery contract namespace

These Draft 2020-12 schemas implement the additive contract foundation ratified by ADR 0006.

They are deliberately isolated under `schemas/contracts/skywatcher_ai/` because the open Phase-1 contract reconciliation PR owns the existing flat `schemas/contracts/` namespace. The namespace avoids parallel-file collisions while preserving a clear migration path into the broader contract registry.

The schemas define records only. They add no provider SDK, model execution, network route, database access or producer RPC.

- `acquisition_receipt.v1.schema.json`
- `bounded_producer_job.v1.schema.json`
- `bounded_producer_job.v2.schema.json`
- `bounded_producer_job_record.v1.schema.json`
- `legacy_artifact_disposition.v1.schema.json`
- `model_field_provenance.v1.schema.json`
- `producer_package_admission_receipt.v1.schema.json`
- `producer_package_manifest.v1.schema.json`
- `producer_output_lineage.v1.schema.json`
- `producer_run_receipt.v1.schema.json`
- `satim_provisional_signal.v1.schema.json`
- `skywatcher_ai_common.v1.schema.json`

`bounded_producer_job.v2` is the signed, pinned and fail-closed H06 execution-boundary contract. It adds immutable content identities, detached-signature metadata, authorization and audit references, H05 egress binding, explicit provisional-input handling, resource limits, strict workspace isolation and designated-output accounting. It remains a record contract and does not launch a worker.

The H07 job-record, run-receipt, package-manifest, output-lineage and admission-receipt contracts freeze the offline transfer from a verified H06 producer package into Evidence Engine quarantine. They require complete source/output accounting, classification inheritance, derivation-specific provenance and explicit non-eligibility for certification, active promotion, retrieval, claims, answers and citations.

## Phase-1 contract compatibility

This namespace is additive to the broader Phase-1 contracts proposed in TheHub PR #139. It does not redefine retrieval, snapshot, claim, evidence-lifecycle or analytical-run ownership.

Compatibility rules:

- `classification` uses the same seven level values as `access_classification.v1`; the broader contract remains authoritative for inheritance and effective-access calculation.
- `model_field_provenance.v1` stores immutable field-level copies of provider/model identifiers and also requires `model_run_receipt_id`; it does not replace `provider_reference.v1` or `analytical_run_receipt.v1`.
- Acquisition, bounded-producer, producer-package, lineage and admission records are operational child records that may be referenced by later Evidence Engine or analytical-run envelopes.
- No schema in this directory defines an `ACTIVE` snapshot, retrieval object, claim ledger or citation surface.

`tests/test_skywatcher_ai_contracts.py` activates cross-namespace checks automatically when the Phase-1 schemas are present on the target branch.
