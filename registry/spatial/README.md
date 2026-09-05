# Spatial Registry

This directory contains federation-level spatial reference manifests.

## Legacy pixel grid

`pr_grid_full_cell_index_saturated.csv` is retained byte-for-byte for provenance and regression
reproduction. Its SHA-256 is:

```text
17733f3f18c8a644e31c1eb25fb27b73b4bf353c6de57d5203c4311e05d64483
```

The artifact contains 98,304 cells in a 384 × 256 image-space grid. It has **no declared CRS,
latitude/longitude binding or affine ground transform**. Effective 2026-09-05 it is
`NONCANONICAL_LEGACY_IMAGE_SPACE` and MUST NOT be used for ground-coordinate joins,
municipio/barrio containment, parcel intersection, metric distance or federation identity.

Validation of its retained bytes remains available through:

```bash
python scripts/validate_pr_grid.py --require-sha
```

## Shared administrative geometry

The federation administrative containment reference is declared in:

```text
registry/spatial/federation_admin_geometry.manifest.json
```

The manifest pins the exact producer revision and Git blob identities for the municipio and
barrio manifestations used by the federation. The external source authority remains the U.S.
Census Bureau; `aguayluz-pr` is only the pinned producer manifestation/custodian. Producer
copies are projections/caches and do not become independent competing authorities.

## Authority rule

Shared spatial identity and shared administrative containment are governed by ADR 0010 and the
logical `prii-federation-spatial-identity` authority. `thehub-pr` consumes and governs these
references but is not their sovereign identity authority.