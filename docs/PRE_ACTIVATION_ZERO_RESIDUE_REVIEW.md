# Federation Authority Boundary — Zero-Residue Pre-Activation Review

**Review date:** 2026-09-09  
**Branch:** `gpt/authority-boundary-closure-b1-b5`  
**Scope:** B-H1 through B-H8, draft A.1-A.9, D fixture preparation  
**Certification state:** `NOT_CERTIFIED`  
**Phase A activation:** `LOCKED`

This review separates **source implementation state** from **executed evidence state**. A hosted seven-tree `authority_boundary_validation_v4` receipt is still required before certification. Static/source reconciliation is not a substitute for an executed receipt.

## B-H1 — receipt contract

**SOURCE_IMPLEMENTED / EXECUTION_PENDING**

- `registry/federation/authority_boundary_receipt.schema.json` freezes `authority_boundary_validation_v4`.
- Required receipt sections include repository, identifier, relationship, geometry, source ownership, producer/consumer, authority leakage, negative tests, arithmetic closure, blockers, certification decision, next phase, and receipt hash.
- Certification requires `blocker_count == 0`.

## B-H2 — identifier adversarial suite

**SOURCE_RECONCILED / HOSTED FALSIFICATION PENDING**

- `tests/test_identifier_namespace_census_adversarial.py` covers unknown prefixes, unresolved dynamic f-strings/concatenation, tuple-driven prefix maps, bare-taxonomy false positives, deterministic helper prefixes, colon-delimited helpers, namespace overlap, separator collisions, and positive controls.
- `scripts/identifier_namespace_census.py` now:
  - resolves bounded `prefix` expressions only when the same module provides a static prefix family map;
  - keeps unbounded dynamic constructors as blockers;
  - infers local deterministic helper separators (`_`, `:`, `-`);
  - treats imported known deterministic helpers as separator-neutral family signals rather than guessing;
  - does not treat arbitrary bare `id` fields as identity.
- `registry/federation/identifier_namespaces.json` is v3 and incorporates newly verified frozen-tree families, including:
  - MoneySweep political-finance/workflow families `pfe_`, `candidate_`, `committee_`, `recipient_`, `cfedge_`, `donor_`, `upload_ent_`, `ngo_`, and Case Manager deterministic kinds;
  - shared PR intake `SW-PRINTAKE-` / `CS-PRINTAKE-`, reclassified as shared interchange rather than a Spiderweb-owned identity namespace;
  - TheHub workflow-only `erd_`, `htr_`, `htre_`, `htr2_` families;
  - AguaYLuz analysis-only `AYL_RBU_`, `AYL_RBA_`, `AYL_RBR_` families;
  - Skywatcher `track:`, `vertex:`, `pair:`, `review:`, and `fn:` analytical/workflow families.
- Existing AguaYLuz WTR/WWT/PMP/RSV/OSMP/OSMS/OSML/HIFLD/EIA/PWR, OVNIS PRUFON/PRUAP/CAND/assess, Centinelas CENT-*, Spiderweb PIN, and federation stream namespaces remain explicit.
- The hosted seven-tree crawl remains authoritative for surfacing any residual unknown family.

## B-H3 — relationship adversarial suite

**SOURCE_RECONCILED / HOSTED FALSIFICATION PENDING**

- `tests/test_relationship_authority_adversarial.py` exercises unknown literals, ambiguous owner claims, cross-producer collisions, wrong-domain emitters, Hub candidate-correlation boundaries, improper SHARED ownership, shared semantic registration, and consumer-projection behavior.
- B.4 remains source-reconciled at 25 unique relationship literals / 45 repository-literal observations from the prior exact seven-tree source crawl.
- Shared semantic registration does not prove any individual relationship instance or identity assertion.

## B-H4 — normalized authority matrix

**FROZEN_CANDIDATE / EXECUTION_PENDING**

- `registry/federation/authority_matrix.json` defines bounded authority objects for all seven repositories, shared identity, identifier/relationship registries, admin geometry, legacy grid, domain owners, Hub correlation, source references, and cross-domain handoffs.
- Shared objects require exactly one writer.
- Multi-writer rows are allowed only when explicitly `CROSS_DOMAIN` and writers own disjoint facts.
- Declared unclassified authority objects: 0.

## B-H5 — source ownership closure

**FROZEN_CANDIDATE / EXECUTION_PENDING**

- `registry/federation/source_ownership.json` classifies cross-repo source families as authoritative/canonical reference, reference copy, domain derivative, cache/materialized view, discovery/evidence/historical manifestation, or noncanonical legacy.
- Explicitly covered: legacy 98,304-cell grid, GEBCO, Census admin geometry, power lineage, MoneySweep→Spiderweb PPP derivation, heritage Google manifestations, Azucareras, NRHP/OECH/JP evidence, shared schemas, and TheHub aggregate packages.
- `same bytes == same authority` is forbidden.
- `source lineage == semantic ownership` is forbidden.

## B-H6 — drift/invalidation

**INSTALLED_CANDIDATE / EXECUTION_PENDING**

- `registry/federation/drift_policy.json` defines `CERT_VALID`, `CERT_STALE`, `CERT_INVALID`, and `CERT_SUPERSEDED`.
- Critical registry, validator, geometry, peer-snapshot, and negative-suite drift invalidates or stales certification as declared.
- v4 receipts hash critical candidate manifests.

## B-H7 — arithmetic closure

**STATIC_CONTRACT_PROVEN / EXECUTION_PENDING**

- `registry/federation/arithmetic_closure.json` formalizes repository, identifier, relationship, source, geometry, and global authority equations.
- Required terminal state is `BLOCKED = 0` and `UNCLASSIFIED = 0`.
- Static denominator remains 7 repositories = 1 TheHub + 6 producers.

## B-H8 — dormant certification package

**READY_FOR_ZERO_BLOCKER_RECEIPT / CORRECTLY DORMANT**

- `registry/federation/certifications/authority_boundary_certification.json` has state `READY_FOR_ZERO_BLOCKER_RECEIPT`.
- `issued_at`, `receipt_sha256`, and `blocker_count` remain null.
- Manual override is forbidden.
- Phase A remains locked.

## A.1-A.9 draft contract

**DRAFT_NONAUTHORITATIVE / ACTIVATION_LOCKED**

`registry/federation/draft/federation_spatial_entity_contract_1_0.json` prepares:

1. canonical federation spatial entity IDs/objects;
2. identity algebra/cardinality;
3. raw versus normalized manifestations;
4. multi-role geometry assertions;
5. repo crosswalks;
6. reversible merge/split event sourcing;
7. domain relationship ownership;
8. lifecycle/history semantics;
9. SPATIAL-001 through SPATIAL-030 invariants.

It explicitly requires `AUTHORITY_BOUNDARY_CERTIFIED` and does not authorize migration.

## D adversarial fixture corpus

**FROZEN_DRAFT_FIXTURES / NOT YET EXECUTED AGAINST ACTIVE A**

`tests/fixtures/federation_identity_adversarial/corpus.json` contains 10 fixture families:

- Arecibo Observatory vs. Eye to the Universe;
- Central Cambalache site vs. chimney;
- Hacienda Florida homonym;
- falsified Esperanza/La Luisa N:1;
- site/component/designation separation;
- conflicting geometry assertions;
- cross-repository disagreement;
- duplicated source lineage;
- historical succession;
- hydroelectric shared identity with multiple domain graphs.

Expected fixture denominator: 10. Material unclassified fixtures: 0.

## Atomic branch consistency gate

The PLAN MAX source package must exist together in one branch tree. The required critical paths are:

- `registry/federation/authority_boundary_receipt.schema.json`
- `registry/federation/authority_matrix.json`
- `registry/federation/source_ownership.json`
- `registry/federation/drift_policy.json`
- `registry/federation/arithmetic_closure.json`
- `registry/federation/certifications/authority_boundary_certification.json`
- `registry/federation/draft/federation_spatial_entity_contract_1_0.json`
- `registry/federation/identifier_namespaces.json`
- `scripts/identifier_namespace_census.py`
- `tests/test_identifier_namespace_census_adversarial.py`
- `tests/test_relationship_authority_adversarial.py`
- `tests/test_plan_max_preactivation_contracts.py`
- `tests/fixtures/federation_identity_adversarial/corpus.json`

The branch must be enumerated and each critical file fetched back after the atomic commit before the source package is called coherent.

## v4 hosted job sequence

When GitHub Actions admission permits execution, the job must:

1. check out the candidate TheHub branch plus exact six frozen peer commits;
2. run quarantine, base authority, B-H2, B-H3, and PLAN MAX preactivation tests;
3. set `AUTHORITY_NEGATIVE_TESTS_PASSED=1` only after those tests pass in the same job;
4. run `scripts/validate_authority_boundary.py`;
5. produce and upload `authority_boundary_validation_v4`;
6. require `blocker_count = 0` before certification or Phase A unlock.

## Current residue register

| Residue | State | Material? | Disposition |
|---|---|---:|---|
| Hosted seven-tree v4 execution receipt | `BLOCKED_EXTERNAL` until a job actually executes | YES | Do not substitute static reasoning. |
| Additional ID families surfaced by real v4 crawl | `UNKNOWN_UNTIL_EXECUTION` | CONDITIONAL | Register/reconcile only if surfaced. |
| Additional relationship literals surfaced by real v4 crawl | `UNKNOWN_UNTIL_EXECUTION` | CONDITIONAL | Register/reconcile only if surfaced. |
| B source/engineering package | `SOURCE_RECONCILED_CANDIDATE` | NO known static gap in declared scope | Subject to atomic tree verification and hosted falsification. |
| A contract | `DRAFT_NONAUTHORITATIVE` | NO | Activate only after B certification. |
| D fixtures | `FROZEN_DRAFT_FIXTURES` | NO | Execute after A activation. |

## Pre-activation decision

```text
B ENGINEERING / EVIDENCE CONTRACTS     SOURCE_RECONCILED_CANDIDATE
B HOSTED EXECUTION                     REQUIRED
AUTHORITY_BOUNDARY_CERTIFIED           NOT_ISSUED
A.1-A.9                                DRAFT_NONAUTHORITATIVE
A ACTIVATION                           LOCKED
D FIXTURE CORPUS                       FROZEN_DRAFT_FIXTURES
```

No certification statement may be upgraded until a real hosted seven-tree `authority_boundary_validation_v4` receipt exists and its `blocker_count` is exactly zero.
