# Authority Boundary Closure — B.1 through B.5

**Candidate date:** 2026-09-08
**Certification state:** `NOT_CERTIFIED`
**Successor phase:** `A — FEDERATION IDENTITY CONTRACT` is forbidden until blocker count = 0.

## B.1 — identity authority

- ADR 0009 is superseded.
- ADR 0010 assigns shared spatial identity to the independent logical authority
  `prii-federation-spatial-identity`.
- TheHub is bounded to governance, validation, aggregation and query/client functions.
- The historical `src/hub/identity_registry.py` still contains the former
  `FEDERATION_AUTHORITY = "thehub-pr"` value, but repository search shows it has no production
  import path; it is imported only by its regression test. It is therefore explicitly frozen as
  `LEGACY_NONAUTHORITATIVE_TEST_FIXTURE` in
  `registry/federation/legacy_identity_registry_quarantine.json`.
- `tests/test_authority_boundary_quarantine.py` fails if production code begins importing that
  legacy module. The quarantine is valid only while production-import count remains zero.

**B.1 candidate state: CLOSED BY SUPERSESSION + ENFORCED QUARANTINE.**

## B.2 — shared geometry

- The 98,304-cell raster-derived PR grid is demoted to
  `NONCANONICAL_LEGACY_IMAGE_SPACE`; it remains byte-retained for provenance only.
- Ground joins, containment, parcel operations, metric distance and identity use are forbidden.
- Municipio and barrio references are pinned to the frozen AguaYLuz manifestations at commit
  `3678271a03e36375dc3e9f2fb4da0b6b655622bd`:
  - municipios blob `048265807f94e5142c34c9edae27356e27ffae42`, expected 78 features;
  - barrios blob `55786963138da192deccb756a37fab94f096cf13`, expected 901 features;
  - serialized GeoJSON CRS `urn:ogc:def:crs:OGC:1.3:CRS84` with longitude/latitude order.
- External lineage is closed to the **2023 U.S. Census Bureau GENZ cartographic boundary
  release**. The frozen producer script explicitly names `cb_2023_us_county_500k.zip` and
  `cb_2023_72_cousub_500k.zip`, filters Puerto Rico by `STATEFP == 72`, reprojects to
  EPSG:4326, simplifies with topology preserved, and emits the pinned GeoJSON manifestations in
  CRS84 longitude/latitude order.

**B.2 candidate state: CLOSED.**

## B.3 — identifier namespaces

`registry/federation/identifier_namespaces.json` establishes the central namespace ledger and
fail-closed policy. Proven local namespaces now include federation stream/persistent IDs,
MoneySweep GOV IDs, Spiderweb pin/intake IDs, AguaYLuz water/power IDs, Skywatcher SATIM IDs,
OVNIS PRUFON/PRUAP master IDs, and Centinelas signal/matter/RSS-source IDs.

The registry remains intentionally `PROVISIONAL_UNTIL_REPOSITORY_CRAWLER_PASSES`. It must not be
promoted to exhaustive merely because all seven repositories now have at least one declared
family. The current prefix-assignment scanner can return an empty census even though structured
JSON/JSONL records contain many local, external, operational, schema and GUI identifier forms.
That silent-success risk prevents promotion: a replacement crawler must classify the full
structured-ID denominator without treating source taxonomy or normalized names as identity.

## B.4 — relationship authority

`registry/federation/relationship_types.json` separates shared identity relationships from
producer-domain semantics. MoneySweep's authoritative government relationship enum remains
separate from exporter-only manifestations. Every literal-bearing domain or Hub-derived row is
pinned to its exact source blob, and the validator verifies each pin against the frozen checkout.

The exact seven-repository local crawl now reconciles 25 unique literals across 45
repository/literal observations with zero unknown, ambiguous, owner-mismatch, cross-producer,
source-pin or Python-parse blockers. Python helper calls are resolved through AST binding to
locally defined `relationship_type`, `rel_type` or `rtype` parameters, avoiding arbitrary string
matches. `duplicate_of`, `located_in` and `reported_by` are centrally shared because multiple
producers emit them; registration authorizes their semantic type and does not prove any specific
record identity. Hub correlation types remain non-identity candidates.

**B.4 candidate state: CLOSED BY EXACT LOCAL CRAWL + PINNED SOURCE VERIFICATION.**

## B.5 — source/duplicate/producer-consumer census and arithmetic

- `registry/federation/repository_snapshots.json` freezes the seven-repository denominator and
  exact baseline commits.
- `registry/federation/authority_boundary_census.json` freezes producer/consumer edges,
  duplicated source families, SHARED vs DOMAIN authority classes, and static arithmetic.
- `.github/workflows/authority-boundary-certification.yml` checks out the six peer revisions
  beside the candidate TheHub checkout and invokes the quarantine-aware
  canonical `scripts/validate_authority_boundary.py` entry point. The historical v2 filename is a
  compatibility wrapper over the same implementation.

The validator fails closed on active identity-authority leakage, invalid grid/admin geometry,
malformed or unreconciled identifier namespaces, unowned/colliding relationships and any
repository-denominator mismatch.

The produced `reports/authority_boundary_validation.json` is the machine certification receipt.
Only `blocker_count = 0` may emit `AUTHORITY_BOUNDARY_CERTIFIED` and unlock Phase A.

## Current material residue

1. `AB-003` — the seven-repository identifier crawler has not yet classified the complete
   structured-ID denominator and remains vulnerable to empty-census silent success.
2. `B-RUNTIME-RECEIPT` — GitHub Actions jobs are rejected before source execution because the
   account is locked for a billing issue. The exact local B.4 receipt does not substitute for the
   hosted runtime matrix, and the admission failure is infrastructure residue rather than source
   evidence.

`AB-001`, `AB-002`, `AB-004`, and `AB-005` are closed in the candidate. Static B.5 arithmetic
closes at 7/7 repositories and 6/6 producers, but runtime certification remains blocked by the
identifier-census and hosted-receipt requirements above.

Therefore `AUTHORITY_BOUNDARY_CERTIFIED` is **not issued** and Phase A remains locked.
