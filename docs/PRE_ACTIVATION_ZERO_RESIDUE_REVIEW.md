# Federation Authority Boundary — Zero-Residue Pre-Activation Review

**Review date:** 2026-09-09  
**Branch:** `gpt/authority-boundary-closure-b1-b5`  
**Scope:** B-H1 through B-H8, draft A.1-A.9, D fixture preparation  
**Certification state:** `NOT_CERTIFIED`  
**Phase A activation:** `LOCKED`

This review separates **source implementation state** from **executed evidence state**. GitHub Actions admission is currently failing before job step 1, so no hosted seven-tree v4 receipt exists. Nothing in this document substitutes for that receipt.

## B-H1 — receipt contract

**SOURCE_IMPLEMENTED / EXECUTION_PENDING**

- `registry/federation/authority_boundary_receipt.schema.json` freezes `authority_boundary_validation_v4`.
- Required receipt sections include repository, identifier, relationship, geometry, source ownership, producer/consumer, authority leakage, negative tests, arithmetic closure, blockers, certification decision, and next phase.
- The contract encodes the fail-closed rule: `blocker_count == 0` is required for `AUTHORITY_BOUNDARY_CERTIFIED` and `A_FEDERATION_IDENTITY_CONTRACT`.

## B-H2 — identifier adversarial suite

**SOURCE_IMPLEMENTED / EXECUTION_PENDING**

- `tests/test_identifier_namespace_census_adversarial.py` covers unknown families, unresolved dynamic f-strings/concatenation, tuple-driven prefix resolution, bare-taxonomy false positives, deterministic shared stream helpers, namespace overlap, separator collisions, and positive controls.
- `scripts/identifier_namespace_census.py` now resolves bounded tuple/map-driven `prefix` expressions only when the same module exposes a static prefix family map; otherwise unresolved expressions remain blockers.
- Newly surfaced source-side families already registered include AguaYLuz `PMP_`, `RSV_`, `OSMS_`, `OSML_`, `EIA_PLANT_`, `EIA_UTIL_`, imported `PWR*`, and OVNIS `CAND-` / `assess_`.
- The hosted seven-tree crawl remains the authority for discovering any additional local/external/workflow identifier family.

## B-H3 — relationship adversarial suite

**SOURCE_IMPLEMENTED / EXECUTION_PENDING**

- `tests/test_relationship_authority_adversarial.py` exercises unknown literal, ambiguous owner, cross-producer collision, wrong-domain emitter, Hub correlation boundary, improper SHARED ownership, shared semantic registration, and consumer-projection behavior.
- B.4 source registry remains reconciled at 25 unique literals across 45 repository/literal observations from the prior exact local crawl.

## B-H4 — normalized authority matrix

**SOURCE_IMPLEMENTED / EXECUTION_PENDING**

- `registry/federation/authority_matrix.json` defines bounded authority objects for all seven repositories, shared identity, identifier/relationship registries, admin geometry, legacy pixel grid, domain relationship owners, Hub correlation, GEBCO/Census references, and the MoneySweep→Spiderweb PPP split-domain handoff.
- Shared objects must have exactly one writer.
- Multi-writer rows are permitted only when explicitly `CROSS_DOMAIN` and the writers own disjoint domain facts; shared identity remains single-writer under `prii-federation-spatial-identity`.
- Declared unclassified authority objects: 0.

## B-H5 — source ownership closure

**SOURCE_IMPLEMENTED / EXECUTION_PENDING**

- `registry/federation/source_ownership.json` classifies cross-repo/source families as authoritative/canonical reference, reference copy, domain derivative, cache/materialized view, discovery/evidence/historical manifestation, or noncanonical legacy.
- Explicitly closed families include the 98,304-cell legacy grid, GEBCO, Census admin geometry, power lineage, MoneySweep→Spiderweb PPP spatial derivation, heritage Google manifestations, Azucareras, NRHP/OECH/JP evidence, shared schemas, and TheHub aggregate packages.
- `same bytes == same authority` is forbidden.
- `source lineage == semantic ownership` is forbidden.

## B-H6 — drift/invalidation

**SOURCE_IMPLEMENTED / EXECUTION_PENDING**

- `registry/federation/drift_policy.json` defines `CERT_VALID`, `CERT_STALE`, `CERT_INVALID`, and `CERT_SUPERSEDED`.
- Critical registry, validator, geometry, negative-test, and peer-snapshot changes invalidate or stale certification as appropriate.
- The v4 receipt records SHA-256 for critical candidate manifests so a later certification can be reproduced and invalidated deterministically.

## B-H7 — arithmetic closure

**SOURCE_IMPLEMENTED / EXECUTION_PENDING**

- `registry/federation/arithmetic_closure.json` formalizes repository, identifier, relationship, source, geometry, and global authority equations.
- Required terminal state is `BLOCKED = 0` and `UNCLASSIFIED = 0`.
- Static federation denominator remains 7 repositories = 1 TheHub + 6 producers.

## B-H8 — dormant certification package

**SOURCE_IMPLEMENTED / CORRECTLY DORMANT**

- `registry/federation/certifications/authority_boundary_certification.json` is `READY_FOR_ZERO_BLOCKER_RECEIPT`.
- `issued_at`, `receipt_sha256`, and `blocker_count` are null.
- Manual override is forbidden.
- Phase A remains `LOCKED` until the exact hosted receipt reports zero blockers.

## A.1-A.9 draft contract

**DRAFT_NONAUTHORITATIVE / ACTIVATION_LOCKED**

`registry/federation/draft/federation_spatial_entity_contract_1_0.json` prepares:

1. canonical federation spatial entity ID/object contract;
2. identity algebra and cardinality states;
3. raw + normalized manifestation separation;
4. multiple geometry assertions and authority roles;
5. repository crosswalk semantics;
6. reversible merge/split event sourcing;
7. domain relationship ownership;
8. lifecycle/history semantics;
9. SPATIAL-001 through SPATIAL-030 invariants.

The draft explicitly requires `AUTHORITY_BOUNDARY_CERTIFIED`; it is not an active contract and does not authorize production migration.

## D adversarial fixture corpus

**FROZEN_DRAFT_FIXTURES / NOT YET EXECUTED AGAINST ACTIVE A**

`tests/fixtures/federation_identity_adversarial/corpus.json` closes 10 fixture families:

- Arecibo Observatory vs. Eye to the Universe;
- Central Cambalache site vs. chimney component;
- Hacienda Florida homonym;
- falsified Esperanza/La Luisa N:1;
- Hacienda/site/component/designation distinction;
- conflicting geometry roles;
- cross-repository disagreement;
- duplicated source lineage;
- historical succession;
- hydroelectric multi-domain identity/topology separation.

Expected fixture denominator: 10. Declared material unclassified fixtures: 0.

## v4 hosted job sequence

When GitHub Actions admission is restored, the job must:

1. check out the exact six frozen peer commits plus the candidate TheHub branch;
2. run quarantine, existing authority validator, B-H2 identifier adversarial, B-H3 relationship adversarial, and preactivation contract tests;
3. set `AUTHORITY_NEGATIVE_TESTS_PASSED=1` only after those tests pass in the same job;
4. run `scripts/validate_authority_boundary.py`;
5. produce `authority_boundary_validation_v4`;
6. preserve the uploaded receipt artifact;
7. require `blocker_count = 0` before certification or Phase A unlock.

## Current residue register

| Residue | State | Material? | Disposition |
|---|---|---:|---|
| Hosted seven-tree v4 execution receipt | BLOCKED_EXTERNAL | YES | Await GitHub Actions admission; do not substitute static reasoning. |
| Additional ID families surfaced by the real v4 crawl | UNKNOWN_UNTIL_EXECUTION | CONDITIONAL | Register/reconcile only if actually surfaced. |
| Additional relationship literals surfaced by the real v4 crawl | UNKNOWN_UNTIL_EXECUTION | CONDITIONAL | Register/reconcile only if actually surfaced. |
| B source/engineering package | SOURCE_IMPLEMENTED | NO known static gap in declared scope | Subject to hosted falsification. |
| A contract | DRAFT_NONAUTHORITATIVE | NO, because activation is prohibited | Activate only after B certification. |
| D fixtures | DRAFT_READY | NO, until A activation | Execute immediately after A becomes active candidate. |

## Pre-activation decision

```text
B ENGINEERING / EVIDENCE CONTRACTS     SOURCE_IMPLEMENTED
B HOSTED EXECUTION                     BLOCKED_EXTERNAL
AUTHORITY_BOUNDARY_CERTIFIED           NOT_ISSUED
A.1-A.9                                DRAFT_NONAUTHORITATIVE
A ACTIVATION                           LOCKED
D FIXTURE CORPUS                       FROZEN_DRAFT_FIXTURES
```

No certification statement should be upgraded until a real hosted seven-tree `authority_boundary_validation_v4` receipt exists and its `blocker_count` is exactly zero.
