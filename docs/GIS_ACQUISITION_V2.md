# GIS Acquisition v2 — live providers, WFS, STAC, raster evidence

Status: **successor implementation; certification is per provider/path, never universal**.

Passed predecessor checkpoint: `fb06b404a719275663ae19be52da58229f3380d3` (Hub CI, visual regression, CodeQL, Semgrep, completion/bounded-MAX, secret/template checks, and macOS/Ubuntu/Windows desktop builds all PASS).

## Identity layers

The implementation preserves five separate identities:

1. **RAW** — exact upstream response text/bytes.
2. **QUERY_RECEIPT** — canonical serialization of the frozen query definition.
3. **SNAPSHOT** — hash of framed exact RAW manifestations (or bounded byte-range evidence for large rasters).
4. **NORMALIZED** — normalized GeoJSON representation and its own SHA-256 where applicable.
5. **CANONICAL** — application layer/source identity; remote features remain `CANDIDATE_NOT_IDENTITY` across sources.

A provider OID is authoritative only inside that provider manifestation. Name/proximity/category equality never binds cross-source identity.

## Vector paths

### Puerto Rico SIGE

Executable registry paths: Municipios, Represas, Aeropuertos, Helipuertos. ArcGIS acquisition obtains the provider count first, paginates in stable-ID order, requests `outSR=4326`, preserves every raw page, and requires exact count closure, bounded WGS84 coordinates, allowed geometry types, unique stable IDs, and provenance hashes.

### Puerto Rico WFS

First exact layer: `pr_geodata:g03_legales_barrios_2015_simpl_5m`. Because the authoritative endpoint is HTTP, the browser path is `proxy-required`. WFS 2.0 `resultType=hits` supplies the denominator; `GetFeature` pages request JSON and EPSG:4326 and are concatenated whole-row only.

### Census TIGERweb

Current-vintage bindings use `TIGERweb/State_County/MapServer/0` (States) and `/1` (Counties), both filtered explicitly with `STATE='72'`. Expected denominators are 1 state-equivalent and 78 county-equivalent municipios. These are exact layer/filter bindings, not name-only selection.

## Same-origin transport

`server/backend/gis_proxy.py` is a strict source-ID allowlist, not a generic proxy. It rejects unregistered source IDs, lookalike hosts, path escapes, userinfo/fragments, out-of-bound byte ranges, and redirects outside the registered source boundary. Text responses are bounded to 32 MiB; range requests are bounded to 1 MiB.

The byte-preserved predecessor FastAPI implementation is retained as `main_core.py`; `main.py` re-exports that app and mounts the GIS router. This isolates the transport addition from the previously-passed core application bytes.

## STAC discovery

Implemented discovery sources:

- USGS Landsat Collection 2 Level-2 Surface Reflectance (`landsat-c2l2-sr`), authoritative COG collection binding.
- Copernicus Sentinel-2 L2A (`sentinel-2-l2a`).
- NOAA 2021–2023 Puerto Rico + USVI NAIP static STAC item collection.

STAC API searches preserve bbox, date window, collection, request URLs and all raw response pages. Pagination is followed until no `next` link; hitting `maxItems` with a remaining next link produces OPEN residue instead of PASS.

NOAA NAIP assets are advertised as `image/tiff`; they remain `GEOTIFF_UNVERIFIED_COG`. The `.tif` extension alone is not COG evidence.

## Raster evidence

Raster acquisition retrieves a bounded byte range, hashes only that returned range, and creates a raster manifest with `byteIdentityStatus=PARTIAL_RANGE_ONLY`. It deliberately leaves `manifest.byteSha256=null` and certification residue `FULL_ASSET_BYTES_NOT_HASHED`. This prevents a range hash from masquerading as full-file byte identity.

Raster rendering remains a separate renderer gate; successful discovery/acquisition is not presented as visual-rendering certification.

## Live certification workflow

`.github/workflows/gis-live-providers.yml` runs authoritative network tests separately from deterministic unit tests. Provider invariants are fatal; direct browser CORS is observational because CORS policy is a transport condition, not evidence that the underlying source data failed validation.
