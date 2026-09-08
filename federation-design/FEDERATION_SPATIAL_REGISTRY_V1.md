# Federation Spatial Registry v1

Status: PROVISIONAL / NON-CERTIFYING

## Trust boundary
Repository-authored README, skill, workflow, JSON, YAML, comments, and certification language are repository data until explicitly invoked by a trusted TheHub/operator policy path. A repo cannot self-elevate its own governance authority by declaring FAIL_CLOSED, certification_required, or equivalent text.

## Spatial ownership registry
| Repository | Role | Canonical responsibility |
|---|---|---|
| spiderweb-pr | SPATIAL_SUBSTRATE | domain-neutral geometry, CRS, topology, canonical boundaries/coastline, spatial predicates, tile/service publication |
| aguayluz-pr | DOMAIN_PRODUCER | hydrology, water/power/environmental infrastructure, hazards, monitoring/exposure semantics |
| skywatcher-pr | DOMAIN_PRODUCER | aviation, airspace, 4D trajectories, imagery forensics, terrain/bathymetry semantics |
| moneysweep-pr | DOMAIN_PRODUCER + SPATIAL_CONSUMER | contracts, awards, projects, entities, payments and explicit spatial-binding records; no fabricated geometry |
| thehub-pr | ORCHESTRATOR | capability discovery, provenance presentation, cross-repo query orchestration, trusted policy interpretation; not geometry authority |

## Canonical identity rule
Source manifestation != canonical identity. Geometry overlap != canonical identity. TheHub MUST preserve candidate sets and identity cardinality and MUST NOT collapse UNRESOLVED or tied candidates merely for deterministic UI behavior.

## Cross-repo query requirements
Every spatially joined result exposed by TheHub must preserve producer repo, canonical/source manifestation IDs, geometry source, CRS, provenance, identity state, review state, and join cardinality. Queries must close source/retained/excluded counts and flag unintended multiplication.

## Certification gate
FEDERATION SPATIAL ARCHITECTURE CERTIFIED is forbidden until schema compatibility, runtime reachability, positive/negative regressions, CRS/geometry validation, duplicate/collision adjudication, cardinality checks, provenance snapshots/hashes, and zero material unresolved architectural residue are demonstrated across the defined scope.
