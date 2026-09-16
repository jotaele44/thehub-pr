# Federation GIS Capability Audit

**Scope:** every PRII federation repository that uses GIS, benchmarked against Google Earth,
Google Maps, Apple Maps, QGIS, and ArcGIS.
**Method:** first-hand inspection of all seven working trees — dependency manifests, module
sources, data holdings, schemas, and CRS occurrences. Every claim below cites the file it
came from.
**Status:** audit only. No schema, contract, registry artifact, or code is changed by this
document.

---

## 1. Executive summary

All seven federation repositories touch GIS, but capability is distributed very unevenly: one
repository carries a genuine geospatial engine, two carry domain-specific geometry work, and
three carry effectively none.

The federation is **not** a competitor to any of the five benchmarked products, and reading it
as one misframes it. Google Earth, Google Maps, and Apple Maps are global consumer basemap and
navigation products. QGIS and ArcGIS are general-purpose desktop GIS platforms. The federation
is a **jurisdiction-locked, provenance-first spatial evidence system** for Puerto Rico. It
consumes ArcGIS services rather than replacing them
(`spiderweb-pr/spiderweb/subsurface/arcgis_adapter_v2.py`).

Where it genuinely leads is narrow and real: **evidence provenance that fails closed**, and
**mountain-to-seafloor coverage of one archipelago** that none of the five offer off the shelf.

Where it genuinely lags is broad: **geoprocessing breadth, imagery, routing, 3D, and
cartographic output** — all absent or minimal.

**The single most consequential defect** is documented in §5: the artifact the federation
designates as its canonical cross-repo spatial index is not georeferenced.

---

## 2. Capability inventory by repository

### Tier 1 — `spiderweb-pr` — the federation's GIS engine

`federation_role: spatial_operational_producer`. This is the only repository with a full
geospatial dependency stack and non-trivial geoprocessing.

| Capability | Evidence |
|---|---|
| geopandas ≥1.0, shapely ≥2.1, rasterio ≥1.4, folium, netCDF4, xarray, scipy, duckdb | `pyproject.toml` |
| Embedded spatial SQL — DuckDB `spatial` extension, six allow-listed binary predicates (`ST_Intersects`, `ST_Contains`, `ST_Within`, `ST_Touches`, `ST_Crosses`, `ST_Overlaps`), point-in-polygon reverse geocode | `spiderweb/spatial/duckdb_engine.py` |
| Archipelago geography contract — `IdentityState`, `SpatialState`, `GeometryRepresentation` enums; adjudication, denominator, provider, history (6 `archipelago*.py` modules, 8 in `spatial/` total) | `spiderweb/spatial/archipelago*.py` |
| Subsurface / void program — **26 modules**: AOI freeze from KML/KMZ via shapely with dimension-loss tracking, ArcGIS REST adapter, source-exhaustion v03→v06, residuals, relevance, evidence packs | `spiderweb/subsurface/` |
| Terrain derivatives — Horn (1981) slope, Zevenbergen & Thorne (1987) profile/plan/general curvature, moving-window roughness, seafloor rugosity, NaN-aware convolution, latitude-correct cell size in metres | `gebco/terrain.py` |
| Affine georeferencing — control-point fit, degeneracy rejection, explicit residual policy, `pixel_to_lonlat` | `pipeline/marine_visual_registration.py` |
| Marine suite — 9 modules: lidar/archive/product sources, observation binding, reference run, alternate products | `pipeline/marine_*.py` |
| Vector tile delivery — MapLibre Martin 1.13.0 pinned by SHA-256; publication state machine `candidate → validated → published` with `quarantined` rollback | `martin/`, `configs/martin_delivery.yaml`, `server/backend/martin_ingress.py` |

**Data holdings:** TIGER 2025 municipios (78 features) and tracts (981 features), EPSG:4326,
both SHA-256-pinned (`data/tiger/2025/manifest.json`); USGS OFR 98-038 metallic occurrences;
NCEI coastal DEM registry; GNIS-keyed natural features (684 KB).

### Tier 2 — `skywatcher-pr` — airspace geometry

Geodesic and corridor math, no vector GIS stack.

- **No geopandas, shapely, fiona, or pyproj** — verified zero matches in `pyproject.toml`.
  Stack is numpy / scipy / xarray / netCDF4.
- `src/skywatcher/corrim/gis_intelligence.py`: `haversine_nm`, `point_to_line_distance`,
  `CorridorAnalyzer`, `HeatmapGenerator`, `AnomalyDetector`, `PuertoRicoInfrastructure`,
  KML colour output.
- GeoPackages present: `Gazetteer_PR_GNIS.gpkg` (7.5 MB), `PR_Landing_Zones_Master.gpkg`,
  `Military_and_Aviation.gpkg`.
- Carries its own second copy of `gebco/` (`io.py`, `terrain.py`), divergent from spiderweb's.

### Tier 3 — `aguayluz-pr` — water and power

- `geopandas==1.1.4`, `shapely==2.1.2`; MapLibre GL 4.7.1 dashboard.
- NHDPlus V2.1 **VPU 21** enrichment and EPA WATERS REST
  (`scripts/enrich_waters_nhd.py`, `src/aguayluz/waters/`).
- USGS NWIS surface, groundwater, and water-quality ingest; water balance; drought and soil enrichment.
- `data/geo/`: `pr_barrios.geojson` (1.1 MB), `pr_municipios.geojson`, `pr_natural_features.geojson`.

### Tier 4 — minimal or none

| Repo | Geospatial libraries | Reality |
|---|---|---|
| `ovnis-pr` | none | MapLibre GL 6.6 dashboard, `ovnis_cases_master.geojson` (776 KB), municipios basemap |
| `moneysweep-pr` | **none** (verified zero in `pyproject.toml` and `requirements.txt`) | 146 FEMA-referencing files, but joins to space only at *municipality* granularity. `networkx` is non-spatial graph work |
| `centinelas-pr` | **none** | No geospatial data at all; carries only the shared grid |

### Control plane — `thehub-pr`

- `schemas/federation_entity.schema.json` → `location` is `anyOf` { `lat` + `lon` } |
  { `municipality` }, plus `attribution_source` and `attribution_confidence`.
- `src/hub/correlate.py` — `spatial-haversine` correlation in pure Python, grid-binned,
  default `threshold_km = 1.0`; separate municipality-only join path.
- Frontend: **Leaflet 1.9.4 + react-leaflet 5.0** — diverging from every producer's MapLibre.
- Datastore: **SQLite only**. `docker-compose.yml` runs a single service; `grep -ci postgis`
  returns 0. PostgreSQL + PostGIS + pgvector is a recorded *decision*
  (`docs/spatialrag_migration/DATABASE_BOUNDARIES.md`), not a deployment.

### CRS profile across all repos

`4326` ×120 · `4269` NAD83 ×23 · **`32161` NAD83 / Puerto Rico & Virgin Is.** ×11 ·
`26919`/`26920` UTM 19N/20N ×12 · `3857` ×5 · **`5866` PRVD02** ×5 · **`5715` MSL depth** ×4 ·
`5703` NAVD88 ×1.

Explicit vertical-datum handling is unusual and is a genuine strength — see §4, axis 5.

---

## 3. What the benchmarks are

Comparing across these five as if they were one category produces nonsense. They are three
different things:

- **Google Maps, Apple Maps** — consumer navigation products. Global basemap, routing, live
  traffic, transit, places. Not analysis tools; no CRS control, no vertical datum, no
  user geoprocessing.
- **Google Earth** — global imagery and terrain browser with light measurement and KML
  overlay. Analysis surface is thin by design.
- **QGIS, ArcGIS** — general-purpose desktop GIS. Full CRS and datum machinery, hundreds
  (QGIS, via GDAL/GRASS/SAGA providers) to over a thousand (ArcGIS Pro toolboxes)
  geoprocessing tools, raster and vector analysis, cartographic composition, 3D, and
  server products.

The federation is a fourth thing: a domain-bounded evidence system that *uses* GIS.

---

## 4. Comparison by axis

### Axis 1 — Basemap, imagery, Street View, live traffic
**Federation: absent.** There is no imagery basemap anywhere in the federation. Martin's
committed config declares `sources: {}` (`spiderweb-pr/martin/config.yaml`), and the single
source promoted to `published` in `configs/martin_delivery.yaml` is `municipios` — 78 polygons.
All five benchmarks win decisively. Google Earth and Google Maps additionally offer historical
imagery and Street View, which have no federation analogue.

### Axis 2 — Coverage
All five are global. The federation is deliberately locked to Puerto Rico — EPSG:32161 usage
and an explicit envelope gate, `bbox_intersects_pr()` in `gebco/terrain.py`. This is scope
discipline, not a deficiency, but it means the federation cannot answer any question outside
the archipelago.

### Axis 3 — Geoprocessing breadth
**The largest real gap.** The federation's vector geoprocessing is six DuckDB spatial
predicates plus hand-written terrain math. QGIS and ArcGIS expose orders of magnitude more —
overlay, dissolve, network analysis, interpolation, suitability modelling, geostatistics.
Anything not already written in `spiderweb/` must be written from scratch.

### Axis 4 — Terrain and bathymetry derivatives
**Federation is narrowly competitive.** `gebco/terrain.py` implements Horn slope, Zevenbergen &
Thorne curvature, roughness, and seafloor rugosity over GEBCO grids with correct
latitude-dependent cell sizing. QGIS and ArcGIS do all of this and more. But **Google Maps and
Apple Maps expose none of it**, and Google Earth exposes only visual relief. For seafloor
rugosity specifically, the federation is ahead of all three consumer products.

### Axis 5 — Vertical datums and hydrography
**Federation is ahead of the consumer products and comparable to the desktop GIS.** PRVD02
(5866), MSL depth (5715), and NAVD88 (5703) appear explicitly. Google Maps and Apple Maps have
no concept of a vertical datum at all. On surface hydrography, aguayluz carries NHDPlus V2.1
VPU 21 — the Puerto Rico vector processing unit — which neither consumer product exposes and
which QGIS/ArcGIS would require you to load yourself.

### Axis 6 — Subsurface and voids
**None of the five model this.** Google Earth, Google Maps, and Apple Maps have nothing.
QGIS and ArcGIS can do it only with plugins and data you supply.

The federation's `spiderweb/subsurface/` (26 modules) is therefore genuinely differentiated —
**with an important qualification**. It is an *evidence-management* system: AOI freezing,
source-exhaustion ledgers, residual tracking, relevance scoring, adjudication. It is **not a
geophysical modelling system**. There is no gravity, resistivity, ground-penetrating radar, or
InSAR inversion anywhere in the tree. It tracks what is known and what remains unresolved about
voids; it does not detect them from sensor physics.

### Axis 7 — Provenance and epistemics
**The federation's decisive advantage, and it is not close.** SHA-256-pinned artifacts and
runtime binaries; a publication state machine requiring explicit operator authorization;
`IdentityState` separated from `SpatialState` on the principle that *discovery is not identity
proof*; `GeometryRepresentation` deliberately independent of feature type, so that polygon
absence is not treated as geometry absence; source-exhaustion ledgers and denominator closure.

ArcGIS has metadata and lineage. QGIS has layer metadata. Neither **fails closed** — neither
will refuse to serve a layer because its provenance is unproven. The consumer products expose
no provenance whatsoever.

### Axis 8 — Multi-repository contract governance
No commercial GIS has an analogue. Contract-generation gating across producer repositories is
outside the problem space all five products occupy.

### Axis 9 — Capabilities absent throughout the federation
Routing and isochrones; 3D, mesh, and point-cloud handling; cartographic print composition;
WMS/WFS/WMTS *serving*; geocoding beyond municipality point-in-polygon; historical imagery;
raster algebra beyond the specific terrain derivatives listed.

### Summary matrix

| Axis | Federation | Google Earth | Google Maps | Apple Maps | QGIS | ArcGIS |
|---|---|---|---|---|---|---|
| Imagery basemap | none | strong | strong | strong | BYO | BYO |
| Global coverage | PR only | yes | yes | yes | yes | yes |
| Geoprocessing breadth | minimal | minimal | none | none | broad | broadest |
| Terrain derivatives | targeted | visual only | none | none | full | full |
| Bathymetry / rugosity | yes | visual only | none | none | via plugins | yes |
| Vertical datums | explicit | none | none | none | yes | yes |
| Subsurface / voids | evidence-tracking | none | none | none | BYO | BYO |
| Provenance, fails closed | **yes** | none | none | none | metadata only | lineage only |
| Routing / 3D / cartography | none | partial | routing | routing | yes | yes |

---

## 5. Principal finding: the canonical shared index is not georeferenced

`registry/spatial/pr_grid_full_cell_index_saturated.csv` is replicated **byte-identical across
all seven repositories** (md5 `e654f727aa81acc0f1d49b1e078d356d`), SHA-256-pinned in each
manifest, 98,304 cells, and described in `schemas/pr_grid_cell.schema.json` as:

> "Canonical cell-level spatial index used by the Puerto Rico federation repos for cross-repo joins."

Its columns are:

```
Cell_ID, Row_Index, Column_Index, Pixel_X_Min, Pixel_Y_Min, Pixel_X_Max, Pixel_Y_Max,
Centroid_X, Centroid_Y, Dark_Pixel_Count, Total_Pixel_Count, Land_Pixel_Ratio, Classification
```

There is no CRS, no latitude or longitude, and no affine transform. `Land_Pixel_Ratio` is
derived from dark-pixel counts over a 384 × 256 raster image, and `Classification` values are
`Water_or_Empty`, `Gridline_Dominant`, `Coastline_or_Land` — image-derived, not survey-derived.

**The federation's one canonical cross-repo spatial index is expressed in pixel space.** Any
join performed through it is an image-space join, and its cells cannot presently be related to
a ground coordinate, a municipality boundary, or each other in metric terms.

This is tractable: `spiderweb-pr/pipeline/marine_visual_registration.py` already implements
control-point affine fitting with degeneracy rejection and an explicit residual policy, and
already exposes `pixel_to_lonlat`. The capability to georeference the grid exists inside the
federation; it has simply not been applied to the grid.

---

## 6. Puerto Rico context

The federation's coverage envelope is its most defensible claim, and it is specific to this
archipelago.

**Top to bottom.** aguayluz carries NHDPlus V2.1 VPU 21 surface hydrography plus USGS
groundwater and water-quality ingest; spiderweb's GEBCO stack reaches the marine floor,
including the Puerto Rico Trench off the north coast. Mountain-to-seafloor coverage of a single
jurisdiction, with vertical datums declared at both ends, is not something Google Maps or Apple
Maps model, and is something QGIS or ArcGIS would give you only after you assembled it yourself.

**Voids and karst.** Subsurface void risk in Puerto Rico concentrates in the northern karst
belt, and `spiderweb/subsurface/` is aimed there. The programme's honest position is evidence
custody, not detection — see axis 6.

**The weakest link is the money-to-ground join.** moneysweep carries 146 FEMA-referencing files
and the federation's densest record of public spending, but it declares **no geospatial
libraries at all** and georeferences only to municipality. The federation entity schema
explicitly accommodates this, noting that producers knowing only the municipality "emit the
municipality form and leave the point to a spatial producer." Puerto Rico has 78 municipios;
attributing a recovery project to one of them locates it within an area averaging roughly
115 km². For tying federal recovery dollars to specific infrastructure — a substation, an
intake, a bridge, a sinkhole remediation — municipality granularity is not sufficient, and this
is the join most likely to matter to anyone auditing the contractor ecosystem.

---

## 7. Prioritized gaps

Recommendations only. Nothing here is implemented by this document.

| # | Gap | Evidence | Note |
|---|---|---|---|
| G1 | Canonical shared grid is unreferenced pixel space | §5 | Highest priority. Affine machinery already exists in `spiderweb-pr/pipeline/marine_visual_registration.py` — reuse, do not rebuild |
| G2 | `location` declares no CRS | `schemas/federation_entity.schema.json` | 4326 vs 4269 is ambiguous; roughly 1 m in Puerto Rico, which matters at asset level |
| G3 | No horizontal-accuracy field on `location` | same | `correlate.py`'s 1 km haversine join has no error model; `attribution_confidence` is a source-trust score, not a positional uncertainty |
| G4 | Two divergent `gebco/` copies and two `gis_intelligence.py` | spiderweb ↔ skywatcher | Terrain results may differ between producers |
| G5 | skywatcher ships `.gpkg` data with no driver to read it | no geopandas/shapely/fiona in `pyproject.toml` | 7.7 MB of GeoPackages currently unreadable in-repo |
| G6 | Martin publishes 1 catalogued layer | `configs/martin_delivery.yaml` | Layer-catalog and promotion machinery already built for more |
| G7 | PostGIS decided but not deployed | `docker-compose.yml`, `docs/spatialrag_migration/` | Blocks index-backed geometry queries at hub tier |
| G8 | Basemap library split — producers MapLibre, hub Leaflet | `*/dashboard/package.json` vs `server/frontend/package.json` | Divergent rendering contract across the federation |
| G9 | Money-to-ground join is municipality-only | moneysweep, §6 | The gap with the largest external consequence |

---

## 8. Federation control-plane determination

This document changes no schema, no contract, no `federation.json`, no registry artifact, and
no code. It is documentation-only and therefore **does not constitute a federation-visible
change**: no contract generation is bumped and no affected-repo compatibility demonstration is
required.

Gaps **G1, G2, G3, G6, and G8 are federation-visible** — they touch the shared registry, the
canonical entity schema, or the cross-repo rendering contract. Each must go through control-plane
affected-set determination, with every affected repository either advancing with the change or
demonstrating compatibility under the resulting contract generation, before any implementation
is merged. That requirement is why remediation is scoped out of this audit.
