# H04 certification candidate and pre-certification gate

H04 consumes one immutable `artifact_validation_report.v1` produced by H03 and the local derivative/provenance paths referenced by that report. It constructs an immutable certification candidate and a deterministic gate decision. It does not create or mutate an `ACTIVE` pointer.

## Candidate construction

The candidate is stored at:

```text
<storage-root>/registry/certification_candidates/<sha256(certification_run_id)>.json
```

Exact replay returns the existing candidate. Reusing the certification-run ID with a different validation-report digest fails closed.

For every H03 disposition, H04 assigns exactly one outcome:

- included in the candidate;
- excluded because H03 reported validation failure;
- excluded because certification-time integrity verification failed.

The accounting partition is:

```text
inputs = included + excluded_validation_failure + excluded_certification_failure
```

## Integrity verification

For every H03 `VALIDATED` row, H04:

1. resolves only relative paths under the storage root;
2. re-reads the normalized derivative and recomputes SHA-256;
3. verifies the immutable derivative-content record;
4. verifies the source-to-derivative provenance edge;
5. verifies complete classification lineage;
6. recomputes a deterministic SHA-256 manifest over the sorted included artifact entries.

The candidate contains complete exclusion, classification-lineage and synthetic/test accounting.

## Pure gate

`compute_snapshot_gate(candidate)` is a pure function. It blocks certification when any of these conditions hold:

- candidate schema is invalid;
- validation or certification accounting does not close;
- no artifact is certifiable;
- the SHA-256 manifest was not recomputed;
- derivative schema or provenance is incomplete;
- classification lineage is incomplete;
- test/synthetic content is present;
- active promotion or query-serving eligibility is asserted.

A candidate with no blockers receives `state=CERTIFIED`; otherwise it receives `state=QUARANTINED`. In both cases:

```text
active_snapshot_promoted = false
query_serving_eligible = false
answer_eligible = false
citation_eligible = false
```

## Pre-certification access

`snapshot_operation_decision()` is a policy decision only; it performs no retrieval or answering.

Before an independently implemented `ACTIVE` promotion:

- `ANSWER` is denied;
- `CITATION` is denied;
- operational status is allowed;
- clearly provisional metadata is allowed.

H05 or a later Control Plane phase must implement policy-controlled egress and any eventual atomic `ACTIVE` promotion. H04 does not do so.

## Excluded scope

H04 adds no provider adapter, model execution, producer RPC, Skywatcher database access, source mutation, existing-ledger mutation, deletion, active-snapshot pointer, retrieval engine or runtime query-answering path.
