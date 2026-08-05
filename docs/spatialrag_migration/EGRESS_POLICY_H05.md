# H05 model-egress policy boundary

H05 implements the policy, identity, receipt and provenance boundary required by
ADR 0006. It does **not** contact a provider, resolve a credential, execute a
model, retrieve evidence, answer a query or promote an `ACTIVE` snapshot.

## Pure policy decision

`compute_egress_policy_decision(policy, request)` is deterministic and performs
no I/O. A request must name all identities explicitly:

- source artifact ID, SHA-256, `ACTIVE` state and complete classification lineage;
- task type, purpose, minimized input fields and expected output fields;
- provider, deployment class, residency, permitted use, model and immutable
  model revision;
- prompt-template version and SHA-256;
- access context, Control Plane authorization reference and audit-event reference;
- approval state and reference when the provider policy requires approval.

There is no default provider, model, revision or prompt. Exact values must occur
in the policy. External use of `RESTRICTED`, `SENSITIVE_LOCATION`, `LEGAL_HOLD`
or `QUARANTINED` additionally requires an exact rule matching classification,
task, purpose, model and revision. `TEST_ONLY` external egress is always denied.

All non-`ACTIVE` artifacts are denied before model context construction. This
includes `CERTIFIED` candidates that have not been independently promoted.

## Provider and fallback policy

Provider entries define explicit:

```text
provider_id
deployment = EXTERNAL | LOCAL_PRIVATE
residencies
permitted_uses
task_types
allowed_classifications
allowed_models[{model_id, revisions[]}]
allowed_prompt_templates[{version, sha256}]
allowed_input_fields
required_input_fields
approval_required_for
credential_references
exact_egress_rules
```

When an external selection fails a provider-specific egress check, H05 may
choose a deterministic local/private fallback only from an explicit fallback
rule tied to the original provider, task, purpose and classification. Core
security failures—non-`ACTIVE` state, incomplete lineage, secret material,
missing authorization/audit references, invalid artifact identity or malformed
task context—cannot be repaired by fallback.

Decisions are typed as:

- `ALLOW_EXTERNAL`;
- `ALLOW_LOCAL_PRIVATE`;
- `USE_LOCAL_PRIVATE`;
- `DENIED`.

## Secret boundary

Only an opaque `credential_reference` may be recorded. Keys representing secret
values, API keys, passwords, access tokens or authorization headers cause a
fail-closed denial. H05 never invokes `CredentialProvider.get()` and never
serializes credential values.

## Immutable decision receipt

`record_egress_decision()` stores:

```text
<storage-root>/registry/egress_decisions/<sha256(decision_run_id)>.json
```

The receipt binds the request digest, policy digest and version, access-context
SHA-256, artifact and task identities, selected provider/model/revision,
prompt identity, authorization and audit references, decision, typed reasons
and complete one-request accounting. Exact replay is idempotent; reuse of a run
ID with changed policy or request fails closed.

## Model-run receipt and field provenance

`record_model_run_receipt()` records caller-supplied model outcomes. It does not
perform execution. Every expected output field must appear exactly once as
either a provenance-bearing output or a typed failure:

```text
expected_fields = output_fields + failed_fields
```

Receipts and field records are immutable:

```text
<storage-root>/registry/model_runs/<sha256(model_run_id)>.json
<storage-root>/registry/model_field_provenance/<prefix>/<field_sha256>.json
```

Every model-derived field preserves the ADR 0006/H01 contract:

- source-artifact ID and SHA-256;
- source region when available;
- model-run receipt ID;
- provider, model and immutable revision;
- prompt-template version and SHA-256;
- policy version and access-context SHA-256;
- extraction-schema version;
- value and confidence;
- validation outcome, review state and reviewer;
- creation time and supersession reference.

The model-run receipt retains the egress-decision identity, provider residency,
credential reference, authorization reference, audit reference, output/failure
accounting and provenance-record locators. It explicitly records that this
module performed no model execution, active promotion or runtime query answer.

## Excluded scope

H05 adds no provider SDK, live provider adapter, credential readback, network
client, producer RPC, Skywatcher database access, source or existing-ledger
mutation, operational deletion, retrieval engine, active-snapshot promotion or
runtime query-answering path.
