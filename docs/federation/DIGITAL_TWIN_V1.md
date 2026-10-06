# Digital Twin v1 (candidate)

TheHub's Digital Twin is the `digital-twin` view of the GIS workspace, opened at
`/gis?view=digital-twin`. It shows the records the Hub store holds over a terrain model whose
heights share one declared vertical datum. Four panels share one camera, one selection and one
time cursor. The view adds temporal playback and exports exactly what is shown.

Under ADR 0001 TheHub is the only product GUI. The records come from the same read model as the
Property Map ([`PROPERTY_MAP_V1.md`](PROPERTY_MAP_V1.md), contract
`federation-spatial-features-v1`), with the same rules: a record is drawn only where its producer
declared a point precision, it is styled by that precision, and every other record is counted.
Nothing is geocoded, and no producer is called at runtime.

## Terrain: why NOAA CUDEM

The 3D source gate (`certifyAdvanced3dSource` in `server/frontend/src/gis/advanced3dContracts.js`)
fails closed. It certifies a terrain source for runtime binding only when the source's heights share
one declared vertical datum (`UNIFORM_BOUND`). The gate is unchanged by this view.

- **Decision (2026-10-04): "Bind a uniform-datum DEM".** This replaced the 2026-10-03 choice of AWS
  Terrarium tiles. Terrarium composites SRTM, 3DEP, GMTED, ETOPO1 and others, with datums that vary
  by tile, so it is not used.
- **The bound DEM** is NOAA NCEI CUDEM Puerto Rico, 1/9 arc-second bathymetric-topographic tiles
  (dataset `m9525`, 2022). NOAA's metadata declares one vertical datum for the whole dataset:
  "Puerto Rico Vertical Datum of 2002 height (m)", EPSG:6641. The horizontal datum is NAD83
  (EPSG:4269).
- **Registry entry.** It appears in `server/frontend/src/gis/advanced3dSourceRegistry.js` as
  `noaa-ncei-cudem-pr-ninth-m9525`, with `verticalDatumStatus: 'UNIFORM_BOUND'`. The Esri world
  elevation entry declares `MIXED_COVERAGE`, so the gate returns `OPEN_VERTICAL_DATUM` for it and it
  is never bound.
- **Binding.** The perspective panel binds CUDEM only when `terrainSource()` returns
  `READY_FOR_RUNTIME_BINDING`. Otherwise it draws a flat ellipsoid and the Details panel says why.

## The CUDEM reader

The reader is `server/frontend/src/gis/cudem.js`. It reads only the windows it needs from NOAA's
public S3 bucket; nothing is copied or hosted.

**Facts it relies on** (T1, checked 2026-10-04/06):

- **Tile list.** `urllist9525.txt` lists **26** tiles. The list is copied verbatim; Spiderweb's
  registry note says 25.
- **Tile bounds.** A tile name gives its north-west corner, and each tile spans 0.25°. The GeoTIFF
  tiepoint of `n18x00_w066x00` is (−66.000185, 18.000185), so neighbouring tiles overlap by a few
  pixels. A pixel is 1/9″ (about 3 m). The nodata value is −9999.
- **Cloud-optimized GeoTIFFs.** Each tile is float32 with deflate compression, 512×512 internal
  tiles, and overviews of 4056, 2028, 1014 and 507 px. All IFDs fit in the first ~2 KB.
- **How S3 answers.** The bucket answers a byte range with `206` and `Access-Control-Allow-Origin: *`.
  It exposes no headers, so a browser cannot read `Content-Range`. geotiff then leaves the file size
  unknown, which is harmless.

**How it reads:**

- **Opening a tile.** `openTile` opens tiles with `allowFullFile: false`. A server that ignores the
  byte range is refused, because geotiff 3.0.5 would otherwise place the whole file at the requested
  offset and misparse it. Up to 16 open handles are cached.
- **Reading heights.** `heightGrid(bbox, width, height)` reads from the coarsest image (full
  resolution or an overview) whose pixels are no larger than the sample spacing. It reads the exact
  pixel window and samples the pixel each grid point falls in.
- **Overlaps and gaps.** Boxes are closed, so a point on the edge two tiles share touches both. Its
  value comes from the first tile in NOAA's list that holds a pixel there. Nodata becomes `NaN` and
  is never reported as a height.
- **Tiles read.** `tilesRead` lists only the tiles that supplied heights.
- **Point readouts.** `elevationAt(lon, lat)` returns `{ metres, tile }`, or `null` outside
  coverage or where CUDEM has no value. `formatElevation` renders it as
  `1322.7 m PRVD02 · CUDEM m9525 1/9″`.

**Live invariant.** `server/frontend/src/gis/liveProviders.test.js` runs against NOAA when
`GIS_LIVE_PROVIDER_TESTS=1`, through the production `openTile`. It checks the header (5 IFDs,
512-px tiles, nodata −9999, tiepoint at the name corner) and two heights:

| Point | Tile | Height |
|---|---|---|
| GNIS 1609905, Cerro de Punta summit (18.172281, −66.5916862) | `n18x25_w066x75` | 1322.7 m PRVD02 |
| (−66.9, 18.6), offshore | `n18x75_w067x00` | −955.1 m |

**Height caveats.** Both are stated in the Details panel wherever heights are used:

- Heights are PRVD02, which is gravity-related. The 3D view places them on the WGS84 ellipsoid
  without a geoid separation, so absolute heights in 3D are offset by the local geoid separation.
  The elevation readout gives the PRVD02 value itself.
- NAD83 positions are used as WGS84 without a horizontal transformation. The two frames differ at
  metre scale.

## Perspective panel

The perspective panel is `server/frontend/src/components/gis/DigitalTwinPerspective.jsx`, built on
Cesium 1.144 with no ion token. It is lazy-loaded.

- **Terrain.** `server/frontend/src/gis/cudemTerrainProvider.js` is a
  `CustomHeightmapTerrainProvider` (geographic tiling, 65×65 samples). Below level 7, or outside
  CUDEM's extent, tiles are flat and nothing is fetched. Cells without data are drawn at 0; they are
  never reported as heights. A failed read draws a flat tile and raises an alert in the Details
  panel.
- **Imagery.** The CARTO base sits under USGS The National Map orthoimagery, which is aerial
  photography, not satellite. The orthoimagery layer is attached only from terrain level
  `ORTHO_MINIMUM_TERRAIN_LEVEL` (10). The reason:
  - Cesium picks a terrain tile's imagery level from the tile's geometric error. With these tiles, a
    terrain tile at level L takes Web Mercator imagery from level L + 1 across Puerto Rico's
    latitudes. This is pinned by a test.
  - Cesium raises that level to the provider's `minimumLevel`, which is 11, because the USGS cache
    has no Puerto Rico tiles at zoom 9–10.
  - Attached to coarser tiles, the layer made each of them ask for every zoom-11 tile it covers;
    the globe's root tiles cover millions. Measured before the fix: 18–25 s per frame, 15 renders
    in 159 s, and no terrain tile ever requested. After it: the panel is ready in under 8 s and
    rendering goes idle.
- **Records.** Records are clamped to the ground and styled by declared precision, in the same
  classes as the Property Map. Picking a record selects it.
- **Rendering.** Cesium renders only when something changes (`requestRenderMode`).

## Panels and synchronization

The view is `server/frontend/src/components/gis/DigitalTwin.jsx`, with pure helpers in
`server/frontend/src/gis/digitalTwin.js`.

| Panel | Built on | Shows |
|---|---|---|
| Perspective | Cesium | CUDEM terrain, draped imagery, records |
| Ortho / top-down | `PropertyMapCanvas` (MapLibre) on the CARTO base | Records and selection |
| Overhead imagery | `PropertyMapCanvas` on USGS orthoimagery (from zoom 11) | Records and selection |
| Details | — | See below |

- **One shared state.** One view (centre, zoom, bearing), one selection, one time window and one
  set of filters drive every panel.
- **Sync rules.** `PropertyMapCanvas` takes an optional controlled `view`/`onViewChange`, and a view
  a panel has just applied is not published back. The perspective panel compares views within a
  tolerance, with bearing compared modulo 360°. It does not re-publish when loading terrain nudges
  its camera.
- **Maximize and Fullscreen.** Each panel has Maximize, which works in the page and is deep-linked
  as `?panel=perspective|ortho|overhead|details`, and Fullscreen, offered when the browser allows
  it.
- **Layout.** Four panels in a grid, one column on narrow screens.

**The Details panel** shows, in this order:

1. The selected record, with its precision, basis and evidence links (`SelectedRecord` from the
   Property Map).
2. The point.
3. The selected record's CUDEM elevation, with its datum and the tile that held it. It reads
   "Outside CUDEM coverage (no height reported)." or "CUDEM has no value here (no height
   reported)." where those apply.
4. The time window and the counts: shown, outside the time window, undated.
5. The records shown. The list is capped at 50 rows and says so when the cap applies.
6. DEM provenance: dataset, provider, dates, citation, datums, resolution, binding status, both
   caveats and the tiles read.
7. Imagery provenance.

## Time

`GET /api/spatial/features` gives every feature its time at the precision the producer recorded.
The code is in `src/hub/spatial_features.py` (`time_span`, `_time_properties`).

| Member | Meaning |
|---|---|
| `observed_at`, `temporal_precision` | The record's time at its declared precision |
| `valid_from`, `valid_to` | A validity window, as recorded |
| `time_start`, `time_end` | The UTC span the time covers, as fixed-width ISO-8601 strings. A validity window wins. Otherwise a year, month or day covers the whole year, month or day, and only a full timestamp is an instant |
| `time_basis` | `validity window as recorded`, `instant as recorded`, `whole year/month/day (UTC; the producer declares no time zone)` or `undated` |
| `temporal_state` and its basis | `LIVE` needs a producer-declared cadence. `CURRENT` is inside a declared validity window. Neither is guessed from recency |

The collection also carries `time_extent` (`start`, `end`), `undated` and `read_at`.

**Time controls:**

- **The slider.** It spans `time_extent` in one-day steps.
- **The window.** The window is "Everything up to the cursor", "One year before the cursor" or "30
  days before the cursor". A record is in the window when its span overlaps it.
- **Undated records** are counted and shown by default ("Show undated (N)"). They are never placed
  in time.
- **Records outside the window** are counted, never silently hidden.
- **Play** steps the cursor 30 days every 400 ms and stops at the end of the extent.

## Counters

The counters say why a zero is a zero.

| Counter | Statement today |
|---|---|
| Findings | "No finding carries geometry: the OVNIS findings ledger records none yet." |
| Live / current | "No producer declares a live cadence, and no mapped record is inside a current validity window." |

**What the committed store holds** (T1, 2026-10-06, synthetic rows excluded as by default):

| Measure | Value |
|---|---|
| Records drawn | 538 of 1625 loaded |
| Dated | 314, all AguaYLuz alerts with a validity window between 1979-10-01 and 2026-10-03, all `HISTORICAL` |
| Undated | 224 (AguaYLuz 153, Spiderweb 71) |
| `LIVE` or `CURRENT` | 0 |
| Findings | 0 |

## Export

Both exports contain exactly the records shown, after the time window and filters. Both carry the
export's own provenance: the contract, `generated_at`, the time window, the filters, the counts
(visible, outside the window, undated, loaded), the layers, and certification `NOT_CERTIFIED`.

- **Export GeoJSON** (`digital-twin.geojson`). A FeatureCollection with every record's properties
  and evidence links, plus a top-level `federation_export` member holding that provenance.
- **Export USD** (`digital-twin.usda`). `usda` text:
  - one `Points` prim, `FederationRecords`, the `defaultPrim`;
  - `metersPerUnit = 1` and `upAxis = "Z"`;
  - points in local east/north metres about the view centre, using an equirectangular
    approximation, with `z = 0`, because terrain heights are not exported;
  - `widths` by declared precision;
  - `evidence_id`, `category`, `producer` and `geometry_precision` as vertex primvars;
  - the provenance, origin and horizontal frame in `customLayerData`.

  An export of the 538 fixture records was opened with Pixar `usd-core` 26.08: the prim, all four
  primvar arrays and the layer data are intact. `usd-core` is not a dependency of this repository.

## Not built

- **The reference's 12-panel grid.** There are four panels, each backed by Federation data.
- **Geoid correction** (ellipsoidal heights from PRVD02). It is stated as a caveat. Datum work is
  Phase 5, P5-C (FDX-025).
- **USGS 3DEP.** The bound DEM is CUDEM, which integrates lidar sources; 3DEP itself is not bound.
- **Saved or resizable layouts.**
- **Terrain heights in USD export.**
- **Findings and live events on the terrain.** The overlays and toggles work, but no finding
  carries geometry and no producer declares a live feed.

## Tests

| Kind | Files |
|---|---|
| Backend | `tests/test_spatial_features.py`, `tests/test_spatial_api.py` |
| Unit | `server/frontend/src/gis/cudem.test.js`, `server/frontend/src/gis/cudemTerrainProvider.test.js`, `server/frontend/src/gis/advanced3dSourceRegistry.test.js`, `server/frontend/src/gis/digitalTwin.test.js`, `server/frontend/src/components/gis/DigitalTwin.test.jsx` |
| Live | `server/frontend/src/gis/liveProviders.test.js` (CUDEM, behind `GIS_LIVE_PROVIDER_TESTS=1`) |
| E2E | `server/frontend/tests/visual/gui-parity.spec.js` ("digital twin") |

The E2E drives the real Cesium, MapLibre and CUDEM reader against a mocked API. Its CUDEM tiles are
synthesized per requested tile name and served as NOAA's bucket serves them: `206` for one byte
range, CORS open, `Content-Range` not exposed. The Chromium in CI cannot reach NOAA.
