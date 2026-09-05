# ADR 0009 — Persistent federation identity authority

- **Status:** Superseded by ADR 0010
- **Date:** 2026-08-10
- **Superseded:** 2026-09-05
- **Deciders:** PRII federation maintainers
- **Scope:** historical `thehub-pr` federation identity resolution design

## Supersession

This ADR originally assigned cross-producer identity equivalence and lineage authority to
`thehub-pr`. That sovereignty is withdrawn. The persistence, provenance, reversibility and
fail-closed identity rules defined here remain useful implementation requirements, but the
**authority owner is replaced by the independent federation spatial-identity plane defined in
ADR 0010**.

`thehub-pr` is now a governance/query client of that authority. It MAY validate packages,
aggregate producer projections, correlate candidate records, present adjudication workflows,
and cache read-only identity projections. It MUST NOT independently create authoritative
federation identity equivalence, shared spatial identity, merge lineage, or canonical shared
geometry.

Producer-native identifiers remain immutable and producers remain authoritative for their own
domain facts. Existing records that carry `federation_authority = "thehub-pr"` are legacy
manifestations and MUST NOT be treated as current authoritative decisions after ADR 0010.

## Retained identity-resolution rules

The following match classes remain the only bases that may support an identity-equivalence
decision after they are recorded by the federation spatial-identity authority:

1. `EXACT_IDENTIFIER` — same authoritative namespace + identifier value.
2. `EXPLICIT_CROSSWALK` — authoritative or reviewed producer-to-federation crosswalk.
3. `PROVEN_RELATIONSHIP` — evidence explicitly establishes identity equivalence.
4. `REVIEWED_MATCH` — a human adjudicator accepts a candidate with evidence and reason code.

`normalized_name`, shared address, shared coordinates, co-occurrence, spatial proximity,
temporal proximity, embedding similarity, and other similarity signals MAY create candidates
but MUST NOT auto-merge entities by themselves.

The registry remains append/audit preserving. Merge, rejection, supersession, split, or
tombstone events never delete historical producer identifiers or prior decisions.

## Migration requirement

Before `AUTHORITY_BOUNDARY_CERTIFIED` may be issued:

- no active code path may assign `thehub-pr` as the sovereign federation identity authority;
- legacy Hub-owned decisions must be classified and migrated or explicitly quarantined;
- shared geometry authority must be pinned outside producer-local caches;
- identifier and relationship namespace registries must pass their exhaustive gates;
- the authority-boundary certification report must show zero material blockers.

See `docs/adr/0010-federation-spatial-identity-authority.md`.