# H08 dual-run readiness contracts and evaluator

H08 implements the offline readiness boundary required by ADR 0006 before any
legacy retirement can be considered. It validates caller-supplied evidence from
at least two pinned legacy/candidate shadow trial pairs, compares deterministic
outputs and model-derived fields, validates rollback evidence, and writes
immutable comparison and campaign-readiness receipts.

H08 does not execute either lane, perform rollback, acquire content, call a
provider or model, launch a worker, access a database, certify evidence, promote
an `ACTIVE` snapshot, retrieve evidence, answer a query, or authorize retirement.

## Frozen contracts

H08 freezes six Draft 2020-12 records:

- `dual_run_campaign_manifest.v1`
- `model_field_equivalence_policy.v1`
- `dual_run_lane_evidence.v1`
- `dual_run_comparison_receipt.v1`
- `dual_run_readiness_receipt.v1`
- `rollback_drill_evidence.v1`

The campaign pins TheHub and Skywatcher revisions, source artifacts, schemas,
provider/model revision, prompt, policy, worker profile and equivalence policy.
Its identity is content-addressed and requires at least two distinct trial IDs.

## Pair comparison

Each trial contains exactly two lanes:

- `LEGACY_SHADOW`
- `ADR0006_CANDIDATE`

Both lanes must bind to the campaign's exact source-set and pin-set digests and
must reference unique signature-verified execution receipts. Lane evidence must
have zero schema violations, zero missing required provenance, and complete input
and output accounting.

Deterministic outputs are compared by exact required-output identity and exact
normalized SHA-256. No tolerance exists for deterministic data.

Model fields are matched by stable field key. Each required field has exactly one
versioned rule. Wildcards, ignore rules and unconditional equivalence are not
available. Missing, additional, duplicate, non-equivalent or unresolved fields
block the trial. Provider, model, source, prompt, policy, access-context and
extraction-schema provenance pins must match exactly even when a value comparator
permits a bounded tolerance.

## Rollback evidence

H08 validates evidence of a rollback drill but does not perform the rollback. A
pass requires a signature-verified successful rollback receipt or a
signature-verified satisfied attestation, complete functional and preservation
checks, managed pre/post state digests, logs by SHA-256 and no unexpected writes.

## Immutable receipts and replay

One immutable comparison receipt is written per trial. One immutable campaign
readiness receipt aggregates all trial comparisons and rollback evidence. Exact
replay is idempotent. Reusing a campaign identity with changed campaign, lane,
policy, comparison or rollback evidence fails closed.

The readiness receipt projects the dual-run result into the existing PRII gate
evidence shape. The dual-run parity gate may pass, but the retirement gate remains
`deferred`. Every H08 contract and receipt fixes `retirement_authorized` to
`false`; certification and active promotion also remain false.

## Cross-repository baseline

The compatibility baseline is Skywatcher `main` at
`3b7ef00006a85c49c88bbbd129f662392fb2f370` (S05), which provides provider-neutral
aviation contracts, provisional SATIM adaptation, provenance-preserving vision
ingestion and deterministic producer-package v2 generation.
