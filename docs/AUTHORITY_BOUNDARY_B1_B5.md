# Authority Boundary Closure — B.1 through B.5

**Candidate date:** 2026-09-05  
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
  - municipios blob `b3a240482478261577b27140d7918f311e2d46a0`, expected 78 features;
  - barrios blob `ae6a8a26233ba53293bd814cac050bab85ab8b35`, expected 901 features;
  - canonical CRS EPSG:4326.
- External lineage is closed to the **2023 U.S. Census Bureau GENZ cartographic boundary
  release**. The frozen producer script explicitly names `cb_2023_us_county_500k.zip` and
  `cb_2023_72_cousub_500k.zip`, filters Puerto Rico by `STATEFP == 72`, reprojects to
  EPSG:4326, simplifies with topology preserved, and emits the pinned GeoJSON manifestations.

**B.2 candidate state: CLOSED.**

## B.3 — identifier namespaces

`registry/federation/identifier_namespaces.json` establishes the central namespace ledger and
fail-closed policy. Proven local namespaces now include federation stream/persistent IDs,
MoneySweep GOV IDs, Spiderweb pin/intake IDs, AguaYLuz water/power IDs, Skywatcher SATIM IDs,
OVNIS PRUFON/PRUAP master IDs, and Centinelas signal/matter/RSS-source IDs.

The registry remains intentionally `PROVISIONAL_UNTIL_REPOSITORY_CRAWLER_PASSES`. It must not be
promoted to exhaustive merely because all seven repositories now have at least one declared
family; the crawler must demonstrate zero undeclared emitted/local families.

## B.4 — relationship authority

`registry/federation/relationship_types.json` separates shared identity relationships from
producer-domain semantics. MoneySweep's authoritative government relationship enum is pinned
by blob SHA. Repository inspection additionally confirms representative producer-export verbs
such as AguaYLuz `operated_by`, `located_in`, `affected_by`, `duplicate_of`, `energized_by`;
Skywatcher `detected_by`, `located_in`; Spiderweb `reported_by`, `observed`; OVNIS `located_in`,
`reported_by`, `duplicate_of`; and Centinelas `involves_agency`, `located_in`.

Those observations do not substitute for the executable full-tree crawl. Every literal/enum
must still resolve to exactly one authority owner and any cross-producer same-literal collision
must be classified as an explicit shared semantic or separated into owner-qualified namespaces.

## B.5 — source/duplicate/producer-consumer census and arithmetic

- `registry/federation/repository_snapshots.json` freezes the seven-repository denominator and
  exact baseline commits.
- `registry/federation/authority_boundary_census.json` freezes producer/consumer edges,
  duplicated source families, SHARED vs DOMAIN authority classes, and static arithmetic.
- `.github/workflows/authority-boundary-certification.yml` checks out the six peer revisions
  beside the candidate TheHub checkout and invokes the quarantine-aware
  `scripts/validate_authority_boundary_v2.py`.

The validator fails closed on active identity-authority leakage, invalid grid/admin geometry,
malformed or unreconciled identifier namespaces, unowned/colliding relationships and any
repository-denominator mismatch.

The produced `reports/authority_boundary_validation.json` is the machine certification receipt.
Only `blocker_count = 0` may emit `AUTHORITY_BOUNDARY_CERTIFIED` and unlock Phase A.

## Current material residue

1. `AB-003` — full seven-repository identifier crawler has not yet produced and reconciled a
   zero-unknown receipt.
2. `AB-004` — full relationship literal/enum crawler has not yet produced and reconciled a
   zero-collision / exactly-one-owner receipt.
3. `B-RUNTIME-RECEIPT` — the new GitHub Actions authority-boundary run is currently failing
   before executing job steps (the first run reported a failed job with an empty step list), so
   no executable B.3/B.4 receipt exists yet. This is treated as infrastructure residue, not as a
   semantic PASS.

`AB-001`, `AB-002`, and `AB-005` are closed in the candidate. Static B.5 arithmetic closes at
7/7 repositories and 6/6 producers, but runtime certification remains blocked by the receipt
requirements above.

Therefore `AUTHORITY_BOUNDARY_CERTIFIED` is **not issued** and Phase A remains locked.