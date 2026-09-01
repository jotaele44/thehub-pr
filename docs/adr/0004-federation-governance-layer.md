# ADR 0004 — Federation governance layer

- **Status:** Proposed
- **Date:** 2026-08-31
- **Scope:** all seven PRII federation repositories

## Decision

PRII SHALL maintain a machine-readable cross-repository dependency graph, versioned contract
policy, and compatibility matrix. Pull requests that can affect a federation contract, shared
package, registry, aggregation boundary, or declared cross-repository artifact SHALL run a
fail-closed governance gate.

Each impacted repository MUST receive one explicit disposition:

- `UNAFFECTED` — impact analysis proves no dependency exposure.
- `COMPATIBLE` — affected surface was tested and remains compatible without code change.
- `UPDATED` — repository changed to restore compatibility and passed its gates.
- `BLOCKED` — compatibility is not closed; merge is prohibited.

Determinism is not evidence of compatibility. Missing, unknown, stale, or contradictory states
fail closed.

## Canonical artifacts

- `governance/federation_dependencies.yaml` — declared cross-repository edges.
- `governance/contract_versions.json` — contract owners and semantic-version policy.
- `governance/compatibility_matrix.json` — current per-repository dispositions.
- `scripts/federation_governance.py` — deterministic impact and drift gate.
- `.github/workflows/federation-governance.yml` — PR/push enforcement.

## Contract versioning

Contract changes use semantic versioning:

- PATCH: backward-compatible correction with no schema/cardinality/semantic requirement change.
- MINOR: backward-compatible additive change.
- MAJOR: any breaking field, schema, semantic, identity, cardinality, requiredness, or behavior change.

A contract change without the required version change is a governance failure.

## Dependency policy

Declared dependency kinds include artifact exports, signal intake, derived artifacts, and explicitly
versioned shared build-time libraries. Producer-to-producer runtime RPC and shared producer databases
remain forbidden unless a later ADR explicitly supersedes that rule.

An observed cross-repository dependency absent from the canonical graph is a failure, not an
implicit new edge.

## Impact policy

Changes to canonical schemas, contract-version metadata, dependency metadata, or shared federation
packages impact every declared consumer transitively. Registry and Hub aggregation/control-plane
changes impact the Hub and all registered producers unless a narrower rule proves otherwise.

The impact detector returns the complete candidate set. CI MUST NOT silently convert timeout,
missing repository, missing disposition, or unknown contract version into `UNAFFECTED`.

## Documentation drift

Machine-readable topology is authoritative for federation membership. Human architecture documents
must agree with it. Missing or extra producer names, stale contract versions, or contradictory roles
cause the governance gate to fail until adjudicated.

## Merge enforcement

The GitHub Actions job is named `federation-governance`. The repository branch protection/ruleset
for `main` SHOULD require this status check before merge. A passing workflow without a required
status rule is `PROVISIONAL`, not a certified merge block.

## Invariants

- Expected federation repositories = 7 until membership is deliberately versioned.
- Registry producers = dependency-graph producers = compatibility-matrix producers minus TheHub.
- All compatibility states are from the allowed state set.
- No `BLOCKED` impacted repository may merge.
- Every impacted repository is `COMPATIBLE` or `UPDATED` before merge.
- Every declared contract version is valid semantic version syntax.
- No known documentation contradiction remains inside the certified scope.

## Rollout

1. Land governance artifacts and central gate in `thehub-pr`.
2. Require `federation-governance` on TheHub `main`.
3. Add lightweight consumer workflows to all six producer repositories.
4. Extend impact detection from path classes to contract fingerprints and transitive graph closure.
5. Add cross-repository dispatch/check reporting once authentication policy for CI-to-CI dispatch is
   established.

## Certification boundary

This ADR certifies the governance model only after the required GitHub status check is enforced on
protected branches and each producer has a corresponding compatibility gate. Until then the central
TheHub implementation is `PROVISIONAL PASS`.
