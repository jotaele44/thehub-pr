# ADR 0010 — Independent federation spatial-identity authority

- **Status:** Accepted for B-phase authority-boundary closure
- **Date:** 2026-09-05
- **Scope:** all seven PRII federation repositories
- **Supersedes:** ADR 0009 authority-owner decision

## Decision

The federation establishes a logical authority plane named
`prii-federation-spatial-identity`. It is independent of every producer repository and of
`thehub-pr`.

This authority owns only shared, cross-domain facts:

- federation spatial-entity identity and equivalence classes;
- producer-member crosswalks and reversible merge/split/supersession lineage;
- shared identifier namespace registration;
- shared relationship namespace registration;
- canonical administrative geometry manifestations used for cross-repository containment;
- provenance for the preceding shared assertions.

It does **not** own producer-domain facts. Domain authority remains:

| Domain | Authority owner |
|---|---|
| public money, contracts, finance, control | `moneysweep-pr` |
| spatial/operational evidence and domain geoprocessing | `spiderweb-pr` |
| water, wastewater, electric-grid topology and utility operations | `aguayluz-pr` |
| aviation, aircraft, flight and airspace observations | `skywatcher-pr` |
| anomalous/UAP case facts and case promotion | `ovnis-pr` |
| pre-officialization signals and routing state | `centinelas-pr` |

## TheHub boundary

`thehub-pr` is the federation governance, validation, aggregation and query client. It MAY:

- discover producer manifests and validate export packages;
- aggregate read-only producer projections;
- generate candidate correlations;
- host adjudication UI/workflows;
- query and cache identity-plane decisions;
- display provenance, conflicts, merge/split history and repository usage.

It MUST NOT:

- become the sole persistence owner of federation spatial identity;
- silently convert correlation candidates into identity equivalence;
- overwrite producer-native identifiers or domain facts;
- manufacture canonical geometry from proximity, names, centroids or fuzzy similarity;
- treat a local cache as the authoritative identity registry.

## Identity algebra

One real-world entity may have many source manifestations and producer records but at most one
active federation identity within a frozen scope. Producer records remain immutable members,
not rewritten copies.

Allowed automatic/review bases are inherited from superseded ADR 0009:
`EXACT_IDENTIFIER`, `EXPLICIT_CROSSWALK`, `PROVEN_RELATIONSHIP`, and `REVIEWED_MATCH`.
Name/address/coordinate/proximity/embedding similarity are candidate-generation signals only.

Merges and splits are reversible and event-sourced. Unknown or disputed identity remains
explicitly `UNRESOLVED`; consumers must fail closed rather than choose a winner.

## Geometry boundary

Shared administrative containment uses a separately pinned federation geometry manifestation.
Producer-local geometry remains authoritative only for its declared domain role. A producer may
publish a geometry candidate for a shared entity, but promotion to shared canonical geometry is
an identity-plane decision with provenance and versioned source manifestations.

The historical 98,304-cell PR pixel grid is explicitly non-georeferenced and therefore cannot
serve as canonical ground geometry unless a future, independently certified affine/CRS binding
is established.

## Relationship boundary

Relationship semantics are namespace-owned. Every emitted relationship type must resolve to
exactly one registered authority owner and be classified `SHARED` or `DOMAIN_ONLY`.

- `SHARED`: identity equivalence, membership, supersession/split lineage and generic shared
  spatial containment/crosswalk relationships.
- `DOMAIN_ONLY`: finance/control, utility topology, airspace, case, signal-routing and other
  producer-domain semantics.

TheHub correlation edges are `SHARED_DERIVED_CANDIDATE`, never identity-bearing by themselves.

## Certification gates

`AUTHORITY_BOUNDARY_CERTIFIED` is forbidden unless the frozen seven-repository denominator
passes all of the following:

1. every emitted/local identifier namespace is declared and collision-tested;
2. every emitted relationship type has exactly one owner and scope;
3. no producer or Hub code path claims sovereign shared identity authority;
4. the pixel grid is either certified georeferenced or explicitly noncanonical;
5. canonical municipio and barrio manifestations are pinned by bytes/version/CRS/provenance;
6. producer/consumer and duplicate-source ownership arithmetic closes;
7. all frozen repository revisions and authority artifacts are hashed/pinned;
8. material unresolved authority residue equals zero.

Until those gates pass, this ADR defines the target boundary but does not itself certify it.