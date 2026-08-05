# H06 bounded producer-worker boundary

H06 implements the signed job, validation, package-verification and immutable
receipt boundary required by ADR 0006. It does not launch a worker, invoke a
container runtime, execute a model, resolve credentials, access a database,
answer a query or promote an `ACTIVE` snapshot.

## Signed job specification

`bounded_producer_job.v2` is a strict additive successor to the H01 planning
contract. The Control Plane computes a content identity from the canonical job
body excluding the self-referential `job_id` and detached `signature`, then
requires:

```text
job_id = producer-job-sha256-<job-identity-sha256>
```

The detached signature covers the canonical job body including `job_id`. H06
accepts injected signature and authorization verifiers; it does not load signing
keys, credentials or secret values.

Every job pins:

- the exact 40-character Skywatcher revision;
- signed-command policy identity;
- worker-profile ID, version and SHA-256;
- every producer/output schema revision;
- Control Plane authorization and audit-event references.

Revision, profile, policy or schema drift is denied.

## Input and workspace boundary

Inputs are immutable content references only:

```text
artifact_id = artifact-sha256-<sha256>
read_only_locator = content://sha256/<sha256>
read_only = true
```

`ACTIVE` inputs are accepted for normal bounded processing. Non-`ACTIVE` inputs
require `workflow_mode=PROVISIONAL_PROCESSING` and an explicit per-input
`provisional=true` marker. This permission does not make the input certified,
queryable or citable.

The required workspace contract is:

```text
ephemeral = true
persistent_db_mounts = false
skywatcher_db_access = false
thehub_db_access = false
secret_readback = false
unrestricted_shell = false
database_mounts = []
persistent_mounts = []
```

Only opaque `secret://...` references may appear. Secret values, tokens,
passwords, API keys and authorization-header material fail closed.

## Network and H05 binding

Outbound network is always default-deny. An offline job must have no hosts, no
request budget and no exception authorization.

A network or model operation requires an immutable H05 egress-decision receipt
whose ID and canonical SHA-256 match the job reference. The receipt must be
allowed, bind the same authorization and audit references, and refer to one of
the job's content-addressed inputs. A network exception additionally requires an
external selected provider, explicit host allowlist, request limit and matching
exception authorization reference.

Core job defects cannot be repaired by an egress receipt.

## Resource and output contract

Each job fixes positive limits for duration, aggregate input bytes, aggregate
output bytes, output-file count and per-file size. The output contract names one
single designated write directory and a complete required-output set.

H06 receives a caller-supplied run report and verifies it without executing the
worker. Every input must appear exactly once as processed, excluded with a typed
reason, or failed with a typed failure. Every required output must appear exactly
once as a declared output or typed output failure.

Output paths must be safe relative paths under the designated directory. H06
rejects absolute paths, traversal, symlinks, duplicate paths and output-root
mismatch. Every output file is reread and its SHA-256 and size are recomputed.

## Immutable package and run receipts

Verified output entries form an immutable package manifest:

```text
<storage-root>/registry/producer_packages/<package-sha256>.json
```

The package SHA-256 is computed over the canonical manifest body containing the
job identity, producer revision, worker profile, schema revisions and verified
file entries. A caller-declared package digest must match this recomputation.

The signed job record and producer run receipt are stored at:

```text
<storage-root>/registry/producer_job_specs/<job-identity-sha256>.json
<storage-root>/registry/producer_runs/<sha256(run-id)>.json
```

Exact replay is idempotent. Reuse of a run ID with a changed job, run report or
package fails closed. Run receipts retain typed reasons, complete accounting,
resource measurements, package identity, signature state, authorization and
audit references, and H05 verification state.

All records explicitly state that H06 performed no worker, provider or model
execution, no active promotion and no runtime query answer.

## Excluded scope

H06 adds no subprocess call, worker launcher, container client, provider SDK,
model adapter, database client, producer RPC, credential readback, retrieval
engine, source-artifact mutation, existing-ledger mutation, operational deletion
or query-answering route.
