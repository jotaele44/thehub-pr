# GIS Advanced 3D Vector v1

Base checkpoint: `e1bf62be6ad01ed4436e02c627da6daf4477d95a` (`checkpoint/gis-renderer-v1`).

Scope is intentionally independent from raster certification and shared-map/device-format work.

Certification rules:
- 3D runtime visibility is not source identity.
- terrain requires explicit vertical-datum metadata before runtime certification.
- point clouds require explicit CRS metadata before runtime certification.
- 3D Tiles source manifests remain `CANDIDATE_NOT_IDENTITY` unless independently bound.
- no cross-vector merge is permitted merely to simplify CI.
