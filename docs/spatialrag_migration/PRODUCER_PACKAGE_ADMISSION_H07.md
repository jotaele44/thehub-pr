# H07 producer-package admission and lineage gate

H07 closes the offline boundary between H06 producer-package verification and
the Evidence Engine quarantine/validation pipeline. It accepts caller-supplied
H06 records and a local package directory, validates their identity and lineage,
and writes eligible output bytes to content-addressed quarantine before creating
immutable producer-output, provenance, and admission records.

H07 does not acquire content, launch a worker, execute a provider or model,
resolve credentials, access a database, certify evidence, promote an `ACTIVE`
snapshot, retrieve evidence, create claims, cite evidence, or answer a query.

## Frozen operational child contracts

H07 freezes five records under `schemas/contracts/skywatcher_ai/`:

- `bounded_producer_job_record.v1`
- `producer_run_receipt.v1`
- `producer_package_manifest.v1`
- `producer_output_lineage.v1`
- `producer_package_admission_receipt.v1`

These are subordinate operational records. They do not replace the authoritative
Evidence Lifecycle, Analytical Run Receipt, snapshot, retrieval, claim, or
citation contracts.

## Admission inputs

`record_producer_package_admission()` accepts only:

1. an immutable H06 signed-job record;
2. an immutable H06 terminal run receipt;
3. an immutable H06 producer-package manifest;
4. a complete output-lineage manifest;
5. the caller-supplied local designated package directory.

The module validates all four JSON records under Draft 2020-12 using only local
schema references. It recomputes the H06 job identity, signed-payload digest,
producer-package digest, and lineage-manifest identity.

A package is eligible only when the run succeeded with complete input and output
accounting and no output failures. The package entries must exactly equal the
signed job's required outputs.

## Lineage and classification

Every package entry has exactly one lineage entry and at least one source
artifact from the signed H06 input set. Every signed input has exactly one source
disposition: `USED`, `EXCLUDED`, or `FAILED`.

Output classification may not be less restrictive than any source. The inherited
restriction floor is recomputed, `TEST_ONLY` is preserved, and incomplete or
conflicting classification lineage fails closed.

Derivation-specific requirements are:

- `DETERMINISTIC`: method, method revision, and output schema identity; no model
  or SATIM record.
- `MODEL_DERIVED`: one or more complete `model_field_provenance.v1` records,
  each bound to an admitted source artifact and source SHA-256.
- `SATIM_PROVISIONAL`: a valid `satim_provisional_signal.v1` record with
  `provisional=true` and exactly matching source-artifact IDs.

Producer review and Evidence Engine certification remain separate. H07 does not
create `CERTIFIED` evidence.

## Package-root confinement

H07 verifies that the supplied root is the signed job's designated write root.
It rejects path traversal, absolute paths, symlinks, undeclared files, missing
files, duplicate identities, and SHA-256 or size mismatch.

The pure
`compute_producer_package_admission_decision()` evaluates supplied records,
lineage, and normalized file observations without performing writes.

## Quarantine-before-registry ordering

For an accepted package, H07:

1. rereads and rehashes every verified output;
2. writes all bytes to `quarantine/sha256/<prefix>/<sha256>`;
3. creates immutable producer-output records;
4. creates immutable source-to-output provenance edges;
5. writes the immutable package-admission receipt.

Producer outputs are never mislabeled as acquisition receipts. Output records
remain `QUARANTINED`, and answer, claim, retrieval, and citation eligibility are
all false.

## Accounting and replay

Every package entry terminates as admitted, excluded, or failed. Every signed
source input terminates as used, excluded, or failed. Both accounting partitions
must be complete.

Admission receipts are stored at:

```text
<storage-root>/registry/producer_admissions/<sha256(admission-id)>.json
```

Exact replay is idempotent. Reusing an admission ID with changed job, run,
package, or lineage content fails closed.

## Excluded runtime

H07 contains no network client, subprocess or container launcher, provider/model
SDK, producer RPC, credential loader, database client, retrieval engine,
snapshot promotion path, claim generator, citation engine, or query-answering
route.
