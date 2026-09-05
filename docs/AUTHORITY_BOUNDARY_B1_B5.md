# Authority Boundary Closure — B.1 through B.5

**Candidate date:** 2026-09-05  
**Certification state:** `NOT_CERTIFIED`  
**Successor phase:** `A — FEDERATION IDENTITY CONTRACT` is forbidden until blocker count = 0.

## B.1 — identity authority

- ADR 0009 is superseded.
- ADR 0010 assigns shared spatial identity to the independent logical authority
  `prii-federation-spatial-identity`.
- TheHub is bounded to governance, validation, aggregation and query/client functions.
- **Open implementation residue:** `src/hub/identity_registry.py` on the frozen/candidate tree
  still assigns `FEDERATION_AUTHORITY = "thehub-pr"`. The executable gate treats this as a
  material blocker until migrated/quarantined.

## B.2 — shared geometry

- The 98,304-cell raster-derived PR grid is demoted to
  `NONCANONICAL_LEGACY_IMAGE_SPACE`; it remains byte-retained for provenance only.
- Ground joins, containment, parcel operations, metric distance and identity use are forbidden.
- Municipio and barrio references are pinned to the frozen AguaYLuz manifestations at commit
  `3678271a03e36375dc3e9f2fb4da0b6b655622bd`:
  - municipios blob `b3a240482478261577b27140d7918f311e2d46a0`, expected 78 features;
  - barrios blob `ae6a8a26233ba53293bd814cac050bab85ab8b35`, expected 901 features;
  - canonical CRS EPSG:4326.
- External lineage is now closed to the **2023 U.S. Census Bureau GENZ cartographic boundary
  release**. The frozen producer script explicitly names
  `cb_2023_us_county_500k.zip` and `cb_2023_72_cousub_500k.zip`, filters Puerto Rico by
  `STATEFP == 72`, reprojects to EPSG:4326, simplifies with topology preserved, and emits the
  pinned GeoJSON manifestations.

## B.3 — identifier namespaces

`registry/federation/identifier_namespaces.json` establishes the central namespace ledger and
fail-closed policy. It includes currently proven federation, MoneySweep, Spiderweb, AguaYLuz
and Skywatcher families. OVNIS/Centinelas and any additional dynamically emitted families must
be discovered and closed by the seven-repository crawler before certification.

## B.4 — relationship authority

`registry/federation/relationship_types.json` separates shared identity relationships from
producer-domain semantics. MoneySweep's authoritative government relationship enum is pinned
by blob SHA. Other producer relationship families are assigned to their domain owner, but the
executable crawler must prove every literal/enum value resolves to exactly one owner and that
no cross-producer collision remains.

## B.5 — executable census and arithmetic

`registry/federation/repository_snapshots.json` freezes the seven-repository denominator and
commit pins. `.github/workflows/authority-boundary-certification.yml` checks out those six peer
revisions beside the candidate TheHub checkout and runs
`scripts/validate_authority_boundary.py`.

The validator fails closed on:

- active TheHub identity-authority leakage;
- non-demoted pixel grid;
- unpinned admin geometry;
- malformed/duplicate/shared-owner identifier namespaces;
- undeclared repository identifier families;
- unowned/colliding relationship literals;
- any denominator mismatch.

The produced `reports/authority_boundary_validation.json` is the machine certification receipt.
Only `blocker_count = 0` may emit `AUTHORITY_BOUNDARY_CERTIFIED` and unlock Phase A.

## Current known material residue

1. `AB-001-ACTIVE-HUB-AUTHORITY` — runtime constant still assigns TheHub sovereignty.
2. `AB-003` — full seven-repository emitted/local identifier census has not yet produced a
   zero-unknown receipt.
3. `AB-004` — full relationship literal/enum census has not yet produced a zero-collision,
   one-owner receipt.

`AB-002` and `AB-005` are now closed in the candidate: the pixel grid is noncanonical and the
municipio/barrio source lineage is pinned through Census GENZ2023.

Therefore no certification is asserted by this document.