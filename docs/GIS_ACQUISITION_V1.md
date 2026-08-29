# GIS Acquisition v1 — Device + Online

Status: **IMPLEMENTED / provider runtime certification remains bounded and provisional until exact-head browser execution closes**.

This contract extends the first `/gis` GeoJSON slice without changing the product boundary or renderer authority.

## Acquisition invariant

Acquisition method is not source identity and is not canonical layer identity.

Both paths converge on the same downstream model:

`acquire → preserve RAW manifestation → hash/receipt → validate schema/count/geometry/CRS/identity/provenance → canonical layer manifest → canonical map state → renderer adapter`

### Device

- File picker remains bounded to GeoJSON FeatureCollection.
- The exact RAW text is preserved.
- SHA-256 is computed with Web Crypto before generated source/layer IDs are allowed.
- Failure to hash without explicit stable IDs fails closed.

### Online

- Provider and dataset are selected through the registry, not hard-coded UI branches.
- Only entries whose protocol adapter is `IMPLEMENTED` are executable.
- Registry-only WFS, STAC and imagery providers remain visible but disabled.
- Online acquisition preserves the exact count response and every exact page response separately from the normalized merged GeoJSON layer.

## Puerto Rico-first registry

The first executable online tranche is Puerto Rico SIGE ArcGIS FeatureServer data:

- Municipios — `MIPR/LimitesAdministrativos_v10/FeatureServer/0`
- Represas — `MIPR/Infraestructura/FeatureServer/1`
- Aeropuertos — `MIPR/Infraestructura/FeatureServer/17`
- Helipuertos — `MIPR/Infraestructura/FeatureServer/18`

The registry also records, without falsely claiming runtime completion:

- Puerto Rico government WFS / GeoServer catalog;
- USGS 3D Hydrography Program;
- USGS Landsat STAC;
- NASA Earthdata CMR-STAC;
- Copernicus Data Space STAC;
- NOAA Digital Coast imagery/elevation catalog.

## ArcGIS FeatureLayer adapter

The implemented adapter:

1. requests `returnCountOnly=true`;
2. requires a non-negative integer denominator;
3. requests GeoJSON pages ordered by the declared provider stable-ID field;
4. requests `outSR=4326`;
5. conserves every returned feature without deduplication or aggregation;
6. requires fetched count = provider count;
7. requires unique, non-null provider stable IDs;
8. rejects unexpected geometry types;
9. validates returned coordinate positions as bounded lon/lat;
10. preserves count/page RAW responses;
11. hashes the framed RAW response sequence as the source snapshot;
12. hashes a canonical, retrieval-time-independent query receipt;
13. creates a separate normalized GeoJSON layer manifestation.

For the municipality source, the registry additionally asserts the bounded Puerto Rico municipality denominator of 78. A different provider count fails closed rather than silently redefining the denominator.

## Identity classes

The following remain separate:

- provider registry source ID;
- provider feature stable ID;
- query receipt SHA-256;
- source snapshot SHA-256;
- normalized layer byte SHA-256;
- canonical layer ID;
- canonical feature identity, if/when separately adjudicated.

A fetched provider feature is `CANDIDATE_NOT_IDENTITY` by default. Provider membership, name equality, source category or proximity do not promote cross-source canonical identity.

## Deterministic query receipt

The receipt freezes:

- provider ID;
- registry source ID;
- protocol;
- exact count URL;
- exact page URLs;
- WHERE clause;
- output fields;
- requested output CRS;
- source-native CRS;
- stable-ID field;
- page size.

Retrieval UTC is deliberately excluded from the query-receipt hash so the same query plan has the same query identity across refreshes. Retrieval UTC remains in the source manifestation. Snapshot SHA-256 changes when the fetched raw response set changes.

## Regression gates

Positive:

- registry provider IDs and source IDs are unique;
- every source resolves to a provider and protocol adapter;
- implemented sources cannot ride an OPEN protocol adapter;
- identical remote query + identical raw responses produce identical query/snapshot hashes across retrieval times;
- raw provider responses remain accessible exactly;
- schema/count/geometry/CRS/identity/provenance gates all close PASS for a successful mocked provider path.

Negative:

- provider count/fetched count mismatch fails closed;
- duplicate provider stable IDs fail closed;
- registry-only provider execution fails closed;
- unexpected geometry fails closed;
- invalid WGS84 coordinate bounds fail closed;
- missing Web Crypto prevents online certification rather than producing an unstable identity.

## Certification boundary

- Device GeoJSON acquisition contract: **IMPLEMENTED**, subject to exact-head CI/browser closure.
- Generic ArcGIS FeatureLayer GeoJSON adapter logic: **IMPLEMENTED**, subject to exact-head CI/browser closure.
- Puerto Rico SIGE provider runtime paths: **PROVISIONAL_PROVIDER_RUNTIME** until actual browser fetch/CORS/provider responses close at exact head.
- WFS adapter: **OPEN**.
- STAC search/asset selection adapter: **OPEN**.
- NOAA/ArcGIS image service raster rendering: **OPEN**.
- Universal format/source denominator: **OPEN**.
