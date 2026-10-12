# Subsurface separation, negative controls and datum awareness v1 (candidate)

Phase 5, P5-C adds three things to TheHub's GIS workspace (`/gis`), all under ADR 0001:

- **Datum awareness.** The Digital Twin applies the NOAA geoid to its terrain heights and reports
  both the orthometric and the ellipsoidal height.
- **Subsurface separation** (`/gis?view=interpretive-layers`). Documented layers and modelled layers
  are held apart, and a terrain profile is drawn from one datum.
- **Negative controls** (`/gis?view=aoi-comparison`). A study area is compared with control areas,
  and the result is labelled a background comparison, never a finding.

The view switch now has five views: the workbench, the Property Map
([`PROPERTY_MAP_V1.md`](PROPERTY_MAP_V1.md)), the Digital Twin ([`DIGITAL_TWIN_V1.md`](DIGITAL_TWIN_V1.md)),
and the two above. The records come from the same read model as the Property Map (contract
`federation-spatial-features-v1`). Nothing is geocoded, no producer is called at runtime, and nothing
here is certified.

## Datum awareness: GEOID18

CUDEM heights are PRVD02 (EPSG:6641), which is gravity-related. Cesium places heights on the WGS84
ellipsoid. Before this change the Digital Twin drew PRVD02 heights as if they were ellipsoidal, which
put the terrain about 39–43 m too high. The relation is `h = H + N`, where `H` is the PRVD02 height,
`N` the geoid height and `h` the NAD83(2011) ellipsoidal height.

**The grid** (T1, read 2026-10-07). NOAA NGS publishes GEOID18 for Puerto Rico and the U.S. Virgin
Islands, and the PROJ project mirrors it as a GeoTIFF at `https://cdn.proj.org/us_noaa_g2018p0.tif`.
It is 218,771 bytes, answers byte ranges and allows cross-origin reads, so the browser reads it
directly. It is 301×361 nodes at 1 arc-minute, longitudes run 0–360 from 291, and the values sit on
the nodes (PixelIsPoint). The code is `server/frontend/src/gis/geoid.js`.

**When the geoid is applied.** `geoidBinding` returns `BOUND` only when the terrain passed the 3D
source gate (`READY_FOR_RUNTIME_BINDING`) and the EPSG code of its vertical datum equals the geoid's
orthometric datum (6641). Anything else is `NOT_BOUND` with the reason. The gate in
`server/frontend/src/gis/advanced3dContracts.js` is unchanged: the geoid is a separate check, so the
gate still refuses an unknown datum.

**How it is applied.**

- `geoidHeight(grid, lon, lat)` interpolates bilinearly between nodes. It returns `null` outside the
  grid and on a no-value node.
- `server/frontend/src/gis/cudemTerrainProvider.js` adds `N` to every terrain sample inside the grid.
  A cell where CUDEM has no value is drawn at `0 + N`, so the sea surface sits on the geoid. Outside
  the grid nothing is added or extrapolated.
- The Digital Twin reads the geoid before it builds the 3D panel. Cesium does not re-request tiles it
  already holds, so building the terrain first and correcting it later would leave it uncorrected. The
  panel says "Reading the geoid (GEOID18) before the terrain is built…" while it waits.
- If the geoid cannot be read, the terrain is drawn without it and the Details panel says so, with the
  size of the offset. This is the same flat caveat as before, no longer silent.

**What the readout shows.** The selected record's elevation is the PRVD02 value itself, labelled
with its datum and source. Beside it, the ellipsoidal height with the separation used, for example
"Geoid N -40.0 m (GEOID18) → 1282.7 m NAD83(2011) ellipsoidal · H + N". `formatHeight` prints
"datum not declared" where a datum is missing, and `sharedDatum` refuses to combine heights of
different datums.

**Cross-validation** (T1, 2026-10-07). NGS also serves its own GEOID18 computation at
`https://geodesy.noaa.gov/api/geoid/ght`, with no key. The bilinear value from the grid was compared
with it at six points:

| Point | Grid N (m) | NGS N (m) |
|---|---|---|
| San Juan | −43.132 | −43.131 (±0.043) |
| Cerro de Punta | −38.746 | −38.733 (±0.071) |
| Mayagüez | −40.607 | −40.607 |
| Culebra | −41.900 | −41.896 |
| Vieques | −41.662 | −41.659 |
| St Thomas | −42.194 | −42.191 |

The largest difference is 0.0125 m, against NGS's own stated error of 0.04–0.07 m. Nearest-cell
samples of the same grid differ from the bilinear values by up to 0.09 m (−38.839 against −38.746 at
Cerro de Punta), which is why the grid is interpolated.

`server/frontend/src/gis/liveProviders.test.js` repeats the comparison against NOAA when
`GIS_LIVE_PROVIDER_TESTS=1`, with a tolerance of 0.03 m. The tolerance was set from the measured
difference, not guessed.

**Caveats that remain.** NAD83(2011) ellipsoidal heights are used as WGS84 ellipsoidal heights with no
transformation; the frames differ by about 1–2 m. NAD83 positions are used as WGS84 with no horizontal
transformation either.

## Subsurface separation view

`/gis?view=interpretive-layers` is `server/frontend/src/components/gis/InterpretiveLayers.jsx`, with
pure helpers in `server/frontend/src/gis/interpretive.js`. The directive's rule is that a model must
never visually masquerade as observed underground geometry. The view keeps two groups apart, with
different swatches (solid and hatched) and different map styles, and it states what each group is.

**Documented.** What a source documents. These are surface geometry as published, never a subsurface
model.

- **SIGE layers.** Sumideros (karst sinkholes), acuíferos (aquifer extents) and cuencas (watersheds)
  are loaded on request through the source registry (`acquireOnlineSource`). Each row shows its
  feature count, its gate status and its hashes, or the provider's failure verbatim. A failure is
  never drawn as an empty map. Hiding a layer removes it from the map without discarding it.
- **Hub-held occurrences.** Records of the category `mineral_occurrence` (USGS OFR 98-038) are drawn
  here with the Property Map's precision styling. The category comes from the data.

**MODELLED — not observed geometry.** `groupOf` puts a record here only when its producer declared the
`INTERPRETIVE` epistemic class, whatever its category. The class is read from the new feature
property `declared_epistemic_class`, which carries what the producer declared and nothing else (`null`
when undeclared; there is no crosswalk and no guess). A modelled point is a violet ring on every
paint property, so it cannot inherit a documented style.

**What the committed store holds** (T1, measured 2026-10-12 over `data/fixture.json` ingested with
`hub.ingest`, synthetic rows excluded as by default):

| Measure | Value |
|---|---|
| Records drawn | 538 of 1625 loaded (542 with the 4 synthetic Skywatcher rows) |
| Declared `COMPUTED` | 313 (AguaYLuz alerts) |
| Declared `CURATED` | 225 |
| Declared `INTERPRETIVE` | **0** |
| Rows carrying a `review_state` | 0 |

The modelled group is therefore empty, and it says so: "No producer exports a modelled or
interpretive layer: no record in the Hub store declares the INTERPRETIVE class. Spiderweb's committed
subsurface models are test fixtures and are not shown." Spiderweb holds no production subsurface
model, reported void or area of interest; its models are test fixtures. When a producer exports a
record declared `INTERPRETIVE`, it appears in this group with its count, and not in the documented
one. The unit test exercises that path with a synthetic record.

**Terrain profile.** Two clicks on the map, or two typed "lat, lon" pairs, draw a line. Up to 200
great-circle samples read CUDEM.

- The y axis is metres PRVD02 and the datum is printed with the chart. `buildProfile` refuses a
  profile with no datum.
- A sample where CUDEM has no value is a gap in the line, never a zero. The statistics count samples
  with and without a height. If CUDEM has no value anywhere on the line, no chart is drawn.
- Loaded documented layers that the line crosses are listed as surface intervals, for example "karst
  sinkhole, SIGE surface outline".
- The band below the surface reads "No subsurface model supplied — nothing is drawn below the
  surface." The profile shows terrain only.
- A CSV download (`distance_km,longitude,latitude,height_m_PRVD02`, an empty height for a gap).

## Negative controls: AOI comparison

`/gis?view=aoi-comparison` is `server/frontend/src/components/gis/AoiComparison.jsx`, with the pure
statistics in `server/frontend/src/gis/aoiComparison.js` (contract `aoi-comparison-v1`). It answers
the directive's question: is this more common inside the target area than in comparable background
areas? Every result is labelled **BACKGROUND COMPARISON — not a finding**.

**Areas of interest (AOIs).** A bounding box typed as `minLon,minLat,maxLon,maxLat`, or a municipio
polygon from the TIGERweb 2025 layer ("Load municipio boundaries"). One is the study AOI and one or
more are controls. A bbox area is `bboxAreaM2`; a polygon area is the spherical `polygonAreaM2` in
`server/frontend/src/gis/propertyMap.js`, on a 6371008.8 m sphere (checked against `bboxAreaM2`).
The PR grid V2 cells are not offered as AOIs: the geometry belongs to Spiderweb and Hub holds only
the pin.

**Fail-closed rules.**

- A control that overlaps the study AOI is refused, and so are two overlapping controls. Touching
  counts as overlapping, so no record or area is counted twice.
- Only `OBSERVED_POINT` and `INTERPRETED_POINT` records are placed by their position. A
  `REPRESENTATIVE_POINT` is a stand-in (a municipio centroid, for example), so inside an AOI it is
  counted separately as "membership not determined" and never as a record located there.
- Synthetic records are excluded.
- Below `MIN_COMBINED_RECORDS` (5) records in a row, the row reads "too few records to compare" and
  gets no ratio.

**Per row** (producer, stream, category, as the data declares them): the study count and its density
per km², the pooled controls' count and density, each control's own, and the not-determined counts.
Controls are pooled by summing counts and areas.

**The test.** Under no difference, a record is as likely to fall in the study AOI as the study's share
of the combined area, so the study count is binomial.

- The p-value is the exact two-sided conditional binomial test, summing every outcome no more likely
  than the observed one, as R's `binom.test`.
- The 95% interval is Clopper-Pearson, transformed to a rate ratio `p/(1−p) · A0/A1`.
- With no control records the ratio is infinite and says so. P-values are not adjusted for multiple
  comparisons, and the result states how many comparisons were tested.

Reference values the tests pin:

| Call | p | 95% interval |
|---|---|---|
| `binom.test(8, 10)` | 0.109375 | 0.4439045 – 0.9747893 |
| `binom.test(3, 20, 0.1)` | 0.444650 | — |

The second value is also checked with exact rational arithmetic. A remembered value of 0.3213 for it
was wrong and was found by that check.

**The sample.** The statement is carried by the data, not assumed. The Hub store is a bounded sample,
so the view shows, in a `role="note"` banner above the results: "The Hub store is a bounded sample (at
most 400 records per stream): alerts 400 of 4399, entities 825 of 48224… Counts and densities
describe this sample, not Puerto Rico; how representative it is has not been established." The
sample's spatial representativeness is not established, so a density here is a property of the
sample.

**Receipt.** "Download receipt (JSON)" writes what was compared and how: the contract, the spatial
contract, `generated_at`, the store basis, each AOI with its geometry source, area and area method,
the method statement (membership rule, density, test, minimum, multiplicity, synthetic records
excluded), the rows with their statuses, ratios, intervals and exact p-values, and certification
`NOT_CERTIFIED`.

## The store basis

`GET /api/spatial/features` now carries a `store` member (`hub.spatial_features.store_basis`, served
by `server/backend/spatial_api.py`). It is read from `fixture.json`, which the build writes beside the
database, and is never assumed.

| `kind` | Meaning |
|---|---|
| `bounded-sample` | Declared by the build, with `cap_per_stream` and, per stream, `sampled` and `actual`; `closure_added` is kept where recorded |
| `not_recorded` | There is no `fixture.json`; the counts are not known to be totals |
| `unreadable` | The file could not be read; the counts are not known to be totals |

`server/frontend/src/gis/storeBasis.js` (`describeStore`) turns it into the sentence above, and the
comparison receipt carries it. The committed store is built by `scripts/build_hub_fixture.py`: 400
records per stream, sampled round-robin by producer and record type. Streams (sampled of actual):
alerts 400 of 4399, entities 825 of 48224 (425 re-admitted so that surviving relationships resolve),
observations 400 of 572, relationships 400 of 66769, sources 400 of 43842.

## Not built

- **A subsurface model.** No producer exports one, so nothing is drawn below the surface and no depth
  schematic exists (TWIN-078, TWIN-081). The group is wired and empty.
- **Findings, anchors and underground topics.** None is recorded (TWIN-176, TWIN-178, TWIN-187). The
  timeline's categories come from data, so one appears when a producer exports it.
- **PR grid V2 cells as AOIs.** They need cell geometry exported by Spiderweb, and the grid is RC1.
- **A SIGE-independent karst source.** SIGE's Geología layers returned `502` in the 2026-10-06 CI live
  runs, so the documented layers can fail to load; the failure is shown, not hidden.
- **Historical-name resolution** (FDX-070), a gazetteer task.
- **A geometry-certifier handoff** (FDX-072). No stored row carries a `review_state`, and the
  comparison never upgrades approximate geometry.
- **Multiple-comparison adjustment.** The p-values are unadjusted, and the number of comparisons is
  stated beside them.

## Tests

| Kind | Files |
|---|---|
| Backend | `tests/test_spatial_features.py`, `tests/test_spatial_api.py` |
| Unit | `server/frontend/src/gis/geoid.test.js`, `server/frontend/src/gis/cudemTerrainProvider.test.js`, `server/frontend/src/gis/interpretive.test.js`, `server/frontend/src/gis/storeBasis.test.js`, `server/frontend/src/gis/aoiComparison.test.js`, `server/frontend/src/gis/propertyMap.test.js`, `server/frontend/src/components/gis/InterpretiveLayers.test.jsx`, `server/frontend/src/components/gis/AoiComparison.test.jsx`, `server/frontend/src/components/gis/DigitalTwin.test.jsx` |
| Live | `server/frontend/src/gis/liveProviders.test.js` (CUDEM and GEOID18 against NGS, behind `GIS_LIVE_PROVIDER_TESTS=1`) |
| E2E | `server/frontend/tests/visual/gui-parity.spec.js` ("digital twin", "interpretive layers", "aoi comparison") |

The E2E drives the real map and Cesium against a mocked API, a mocked geoid grid (301×361, N = −40 m),
mocked SIGE and TIGERweb, and CUDEM tiles synthesized per requested name. The Chromium in CI cannot
reach those hosts.
