# GIS Raster Certification Vector v1

Base checkpoint: `e1bf62be6ad01ed4436e02c627da6daf4477d95a` (`checkpoint/gis-renderer-v1`).

Scope is intentionally independent from advanced 3D and shared-map/device-format work.

Certification rules:
- TIFF decoding is not COG certification.
- STAC/source bbox placement is not pixel-geometric certification.
- projected CRS requires an explicit reprojection path before direct WGS84 placement can pass.
- missing CRS or geotransform fails closed.
- partial-range SHA256 is not whole-asset byte identity.
- no cross-vector merge is permitted merely to simplify CI.
