# GIS Shared Map / Device Format Vector v1

Base checkpoint: `e1bf62be6ad01ed4436e02c627da6daf4477d95a` (`checkpoint/gis-renderer-v1`).

Scope is intentionally independent from raster certification and advanced 3D work.

Certification rules:
- format extension recognition is discovery only.
- archive/schema/encoding/CRS inspection precedes parsing or promotion.
- RAW and NORMALIZED hashes remain separate.
- Leaflet retirement requires behavioral parity for every remaining consumer, not package/search-count equality.
- no cross-vector merge is permitted merely to simplify CI.
