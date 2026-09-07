# GIS Architecture v1 — bounded freeze

Status: **PROVISIONAL implementation / architecture PASS for declared scope**

This document freezes the first federation GIS architecture contract. It does not claim universal GIS-format, imagery-provider, or renderer exhaustion.

## Product boundary

- `thehub-pr/server/frontend` is the supported federation product surface.
- Producer repositories, including `spiderweb-pr`, remain spatial/data producers unless separately promoted.
- RAW source manifestations are preserved separately from normalized/canonical layer identity.
- Geographic state is canonical; renderer state is implementation-local.

## Plugin responsibilities

| Plugin | Frozen responsibility | Not authoritative for |
| --- | --- | --- |
| GitHub | canonical code, tests, review, lineage | runtime imagery/data hosting |
| Lovable | implementation accelerator only when bound to canonical repository | source of truth |
| Vercel | preview/runtime validation after canonical project binding | canonical code |
| Figma | interaction/design contract | geographic or source identity |
| Google Drive | fixture/source interchange | production geospatial datastore |

No shadow project is to be created merely to exercise a plugin.

## Runtime responsibilities

| Technology | Responsibility | v1 state |
| --- | --- | --- |
| Leaflet | existing transitional 2D adapter used by first vertical slice | PROVISIONAL |
| MapLibre GL JS | canonical 2D/2.5D renderer; vector/raster/WMS/terrain | TARGET |
| deck.gl | high-volume GPU analytic overlays inside map context | TARGET; not a user-visible renderer mode |
| CesiumJS | advanced 3D globe, terrain, 3D Tiles, point clouds/photogrammetry | TARGET |
| STAC | imagery/EO discovery contract | TARGET |
| COG | preferred cloud-raster manifestation when available | TARGET |
| PMTiles | static tiled artifact manifestation | TARGET |

Redundancy rule: do not add OpenLayers/Mapbox GL JS as parallel map authorities without a separately approved capability gap. Leaflet retires only after a MapLibre adapter reaches bounded feature parity.

## Canonical map state

`MAP_STATE != RENDERER_STATE`.

Canonical state includes:

- geographic center and ground resolution;
- bearing and requested pitch policy;
- AOI/view footprint;
- stable active layer IDs and per-layer visibility/style state;
- stable selected feature IDs;
- imagery product selection;
- terrain source identity;
- temporal state and filters;
- display CRS;
- provenance references.

Renderer-local caches, collision buckets, atmospheric effects, terrain occlusion, and 3D Tiles LOD state are excluded from geographic identity/equivalence.

## 2D ↔ 3D equivalence

Equivalence is geographic-state equivalence, **not pixel equality**.

For a proposed 2D/3D equivalence:

- INTERSECTION = canonical geographic fields both renderers must preserve.
- A_ONLY = 2D-local runtime fields.
- B_ONLY = 3D-local runtime fields.
- UNION = canonical + both renderer-local field sets.
- SYMMETRIC_DIFFERENCE = renderer-local fields intentionally excluded from equivalence.

PASS requires: source/layer identities, AOI/center within defined tolerance, ground resolution within tolerance, bearing, selected feature IDs, imagery identity, terrain identity, time, filters, CRS, and provenance to agree. Round-trip 2D→3D→2D must recover canonical state. A renderer may clamp displayed pitch while preserving requested pitch canonically.

## Source identity contract

Source manifestation and product identity remain separate. A source manifest may bind:

- provider ID;
- catalog/API ID;
- collection ID;
- item ID;
- asset key;
- href manifestation;
- acquisition datetime;
- geometry/bbox/CRS;
- bands/GSD/cloud cover;
- license/attribution;
- retrieval UTC;
- metadata SHA-256 when frozen.

A URL or filename alone never proves canonical product identity.

## Imagery discovery architecture

Primary discovery protocol: STAC where the authoritative provider supports it.

Initial registry classes:

1. Copernicus Data Space Ecosystem STAC — Sentinel/Copernicus discovery.
2. USGS Landsat STAC — Landsat discovery.
3. NASA Earthdata — STAC/catalog discovery depending collection.
4. Additional NOAA/USGS Puerto Rico-relevant aerial/elevation services are to be added only after endpoint/licensing/currency verification.
5. Commercial providers remain credential-gated and are never silently substituted for public sources.

Selection policy must preserve the full candidate set and record AOI, temporal window, cloud threshold, resolution/GSD, collection, item, asset, sort rule, and retrieval time.

## Universal ingestion contract

Before parsing: inspect magic/signature, archive members, preamble/header, encoding, delimiter, schema, row/feature count, CRS, geometry types, Z/M, null/empty geometry and duplicates. Never assume row 1 is a header. RAW bytes/text remain immutable.

| Format | Intended path | v1 implementation |
| --- | --- | --- |
| GeoJSON | browser-native validation/render | **IMPLEMENTED first slice** |
| KML/KMZ | browser/worker with RAW archive preservation | OPEN |
| CSV/TSV coordinates | schema/header/encoding discovery first | OPEN |
| Shapefile ZIP | member inventory + `.shp/.shx/.dbf/.prj/.cpg` validation | OPEN |
| GeoPackage | WASM/server inspection depending size | OPEN |
| GeoTIFF/COG | range-aware browser or server tiler | OPEN |
| PMTiles | direct browser tile archive | OPEN |
| GPX | browser conversion preserving RAW | OPEN |
| LAS/LAZ | server conversion/tiling for production 3D | OPEN |
| 3D Tiles | direct advanced-3D renderer | OPEN |

Archive classification must preserve member PATH + UNCOMPRESSED_SIZE + SHA256 when archive support is implemented.

## First production vertical slice

Route: `/gis`.

Implemented chain:

`local RAW GeoJSON → JSON/FeatureCollection validation → geometry/Z/M inspection → SHA-256 where Web Crypto is available → canonical layer manifest → canonical map state → transitional Leaflet visualization`

The UI deliberately labels other formats/renderers as not yet implemented. No fake universal-support claim is permitted.

## Regression gates

Positive gates:

- 2D→3D mode switch preserves canonical state;
- RAW GeoJSON text remains byte-for-byte identical in the ingestion result;
- FeatureCollection count and geometry types are conserved;
- Z detection is retained;
- layer/provenance stable IDs survive state transitions.

Negative gates:

- duplicate layer/feature IDs fail closed;
- layer state cannot reference an inactive layer;
- changed selected-feature identity fails equivalence;
- non-FeatureCollection JSON is rejected rather than guessed;
- malformed JSON is rejected.

## Superseded candidate

PR #183 (`feat/federation-gis-ui-v0-1`) remains historical evidence and a useful interaction/identity prototype, but its branch is stale/diverged from current `main`. Valid ideas are reused by the successor architecture; stale lineage is not promoted to canonical status.

## Certification boundary

Architecture responsibility freeze: **PASS** for this declared v1 scope.

GeoJSON vertical slice: **PROVISIONAL** until exact-head frontend lint, typecheck, Vitest, build, and browser/visual gates complete.

MapLibre adapter: **OPEN**.

Cesium adapter and 2D↔3D runtime round-trip: **OPEN**.

Full imagery-provider denominator: **OPEN**.

Universal layer-format denominator: **OPEN**.
