# Wherobots RasterFlow — webinar capability catalog (snapshot 2026-11-05)

**Status: non-authoritative reference. Nothing here is adopted, certified or verified.**
Adoption and authority mapping are decided (or deliberately left open) in
[ADR 0011](../adr/0011-wherobots-rasterflow-evaluation.md). The machine-readable form of this
catalog is `registry/external_services/wherobots_rasterflow_catalog.v1.json`; the tables below are
generated from it, and `tests/test_wherobots_rasterflow_catalog.py` fails if the two disagree.

This is a dated snapshot of what one vendor webinar presented. It describes a moment, not the
current product or the current federation, which is why the file name carries a date.

## Evidence basis

- **Source:** a user-supplied transcript of a Wherobots RasterFlow webinar (16 chapters, last
  timestamp 42:39), extracted into a 157-entry catalog and recorded here on 2026-11-05.
- **Source SHA-256:** `feaf45c04e6bf72a2798695650289860bcbb0ae2b0568a887eb9bac6dcdcbaa6`.
- **Evidence tier: T4 (secondary analysis).** It is a vendor-presented webinar seen through an
  automatic transcript. No vendor documentation, API reference, pricing page or release note was
  independently checked. Whether any entry is available today is **unverified**.
- **Transcription normalizations.** The transcript is noisy, so product names were cautiously
  normalized: "whereabouts" → Wherobots, "NAPE" → NAIP, "ZAR" → Zarr, "geoparet" → GeoParquet.
  Where a proper name could not be resolved the transcription is kept and flagged (RF-022,
  RF-102, RF-132).
- **Scope of the catalog.** It lists capabilities and patterns. It is **not** 157 named
  executable functions or exact API endpoints. The webinar mentions more than 300 Apache Sedona
  spatial functions but does not name any of them.
- **Not provided by the source:** exact API method signatures, pricing plan terms, a complete
  enumerated nine-stage workflow, current provider access, model benchmarks, and a list of the
  Sedona functions.

## Status vocabulary

The source defines six status tokens. The other ten appear in its tables without a definition; the
meanings below are inferred from the wording of the entries that carry them and are labelled as
such. Compound flags join tokens with `+` (for example `CLAIMED+DEMO`) and mean the entry
overlaps both. A status says how the *presenter* treated the item, never that it was verified.

| Token | Defined by | Meaning |
|---|---|---|
| `CASE_STUDY` | source | Presenter-reported example. |
| `CLAIMED` | source | Described but not separately tested. |
| `DEMO` | source | Presenter demonstrated or walked through. |
| `DEMO_DISCUSSION` | inferred from use (not defined in the source) | Practice discussed around the demo (QA, labeling, model choice); not a demonstrated tool. |
| `DIRECTION` | inferred from use (not defined in the source) | Stated direction or use case; not a specified, implemented API. |
| `DISCUSSION` | inferred from use (not defined in the source) | Topic raised in discussion; no capability demonstrated. |
| `EXAMPLE` | inferred from use (not defined in the source) | Illustrative scenario used to explain a workflow, input or price; not a separately demonstrated feature. |
| `EXTERNAL` | inferred from use (not defined in the source) | Third-party technology, platform or format named in the session; not a vendor capability. |
| `EXTERNAL_COMPARISON` | inferred from use (not defined in the source) | Third-party product named for vendor comparison. |
| `INFERRED_RISK` | source | Analytical caution inferred from example rather than feature claimed by speaker. |
| `PLANNED` | source | Upcoming as of the presentation. |
| `PREVIEW_DEMO` | source | Demonstrated with preview/upcoming API. |
| `PREVIOUS_APPROACH` | inferred from use (not defined in the source) | Earlier approach described as being superseded. |
| `TRANSCRIPT_ISSUE` | inferred from use (not defined in the source) | Statement internally inconsistent in the transcript; not usable as verified. |
| `TRANSCRIPT_UNCERTAIN` | inferred from use (not defined in the source) | Name rests on noisy speech transcription; exact identity unverified. |
| `VENDOR_CLAIM` | inferred from use (not defined in the source) | Claim made by the vendor presenter; not independently verified. |

## Catalog — 157 entries in 13 groups

### Platform — 14 entries (RF-001–RF-014)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-001 | Wherobots RasterFlow | 01:14 | CLAIMED | Planetary-scale Earth-observation raster pipeline and model-inference execution engine. |
| RF-002 | WherobotsDB | 01:23 | CLAIMED | Distributed spatial SQL/compute for large raster and vector datasets. |
| RF-003 | Apache Sedona integration | 01:31 | CLAIMED | Open-source distributed geospatial engine supporting more than 300 spatial functions; specific function inventory not enumerated. |
| RF-004 | Wherobots Cloud / central hub | 01:55 | CLAIMED | Coordinates hosted and user-owned spatial datasets, models, jobs, and outputs. |
| RF-005 | Spatial lakehouse pattern | 02:22 | CLAIMED | Use existing storage, public data, and private S3-based sources without requiring an entirely separate data lake. |
| RF-006 | Hosted dataset discovery | 02:29 | CLAIMED | Discover vendor-provided datasets. |
| RF-007 | User dataset discovery | 02:29 | CLAIMED | Discover private datasets available to the user's cloud environment. |
| RF-008 | Composable pipeline authoring | 02:38 | CLAIMED | Assemble repeatable imagery, inference, post-processing, and publication pipelines. |
| RF-009 | Recurring automated execution | 02:44 | CLAIMED | Run stabilized pipelines repeatedly to produce updated derived data products. |
| RF-010 | Spatial AI coding assistance | 01:40 | CLAIMED | Use agents and LLMs for GIS code development and orchestration. |
| RF-011 | MCP agent connection | 01:47 | CLAIMED | Connect an agent or developer tool through Model Context Protocol to spatial engines. |
| RF-012 | Wherobots native visualization | 25:49 | DEMO | Inspect cloud-native raster and vector outputs without moving/exporting them first. |
| RF-013 | Model Hub | 35:12 | DEMO | Browse available models, example results, and example input imagery. |
| RF-014 | Distributed WherobotsDB jobs | 38:47 | DEMO | Launch spatial geometry post-processing from an AI-agent-managed sequence. |

### Source Data — 14 entries (RF-015–RF-028)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-015 | Built-in NAIP aerial imagery | 05:44 | CLAIMED | Use high-resolution aerial imagery; transcript transcribes this as 'NAPE'. |
| RF-016 | Built-in Sentinel-2 imagery | 05:52 | CLAIMED | Use multispectral satellite scenes and composites. |
| RF-017 | Sentinel-1 catalog entry | 05:52 | PLANNED | Future radar imagery source; not described as available in the session. |
| RF-018 | Public and open Earth-observation imagery | 02:07 | CLAIMED | Combine open/public image collections with private imagery. |
| RF-019 | Commercial / licensed imagery input | 07:34 | CLAIMED | Index separately acquired imagery for compatible pipelines; licenses require separate checking. |
| RF-020 | Bring-your-own raster imagery | 06:00 | CLAIMED+DEMO | Register imagery supplied as COGs through a raster tile index. |
| RF-021 | AWS S3-hosted Sentinel-2 COGs | 12:07 | EXAMPLE | Reference imagery source for Fields of the World scenario. |
| RF-022 | Kentucky aerial-imagery source | 32:31 | DEMO | High-resolution Kentucky imagery provider transcribed as 'Kai from above'; exact proper spelling unverified from transcript. |
| RF-023 | Spatial AOI collection in GeoParquet | 23:18 | CLAIMED | Supply many parcels or regions of interest to batch tasks from S3. |
| RF-024 | Geospatial raster tile index in GeoParquet | 37:46 | DEMO | Describe user-owned COG footprints and locations for mosaic building. |
| RF-025 | Multi-time-period image inputs | 12:30 | EXAMPLE | Feed different season-specific mosaics into a temporal model. |
| RF-026 | Terrain slope as model covariate | 15:37 | EXAMPLE | Input slope and terrain data to wildfire decision model. |
| RF-027 | Weather forecasts as model covariate | 15:44 | EXAMPLE | Bring external weather information into wildfire suitability inference. |
| RF-028 | Soil-moisture data as model covariate | 15:44 | EXAMPLE | Combine modeled environmental variables in wildfire workflow. |

### Models — 9 entries (RF-029–RF-037)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-029 | SAM 3 model | 06:10 | CLAIMED+DEMO | Text-prompted high-resolution image object detection and geometry production. |
| RF-030 | Fields of the World | 06:18 | CLAIMED+EXAMPLE | Predict agricultural field boundaries from Sentinel-2 mosaics. |
| RF-031 | Canopy-height model | 06:26 | CLAIMED+DEMO | Estimate height of trees and render canopy-height raster overlay. |
| RF-032 | USDA Forest Service FireCon | 15:30 | CASE_STUDY | Use slope, weather, and moisture to identify candidate wildfire containment locations. |
| RF-033 | Bring-your-own PyTorch model | 06:33 | CLAIMED | Register and run an independently developed model using a PT2 archive. |
| RF-034 | Model registration | 06:33 | CLAIMED | Make custom model available to RasterFlow execution workflows. |
| RF-035 | Text prompt list | 33:08 | DEMO | Specify several object classes in one SAM 3 inference job. |
| RF-036 | Confidence threshold control | 33:17 | DEMO | Adjust the score cutoff for accepted object detections. |
| RF-037 | Model output confidence scores | 12:59 | EXAMPLE | Use per-pixel or model probability scores when converting predictions to boundaries. |

### Imagery — 15 entries (RF-038–RF-052)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-038 | Imagery search and sourcing | 03:33 | CLAIMED+DEMO | Find appropriate source imagery for target AOI and date coverage. |
| RF-039 | Imagery ingestion from COGs/S3 | 06:57 | CLAIMED+DEMO | Read cloud-optimized remote-sensing scenes. |
| RF-040 | Imagery catalog/index preparation | 07:42 | CLAIMED+DEMO | Create machine-readable indexes for custom image collections. |
| RF-041 | Time-range selection for compositing | 07:48 | CLAIMED | Choose a date/time interval for making a composite. |
| RF-042 | Multi-scene image compositing | 06:57 | CLAIMED | Combine scene data across available observations. |
| RF-043 | Averaging/compositing to reduce clouds | 07:05 | CLAIMED | Build cloud-reduced or cloud-free image mosaics where coverage permits. |
| RF-044 | Seamless mosaic construction | 07:56 | CLAIMED+DEMO | Stitch numerous imagery tiles into an inference-ready geospatial mosaic. |
| RF-045 | Inference-ready mosaic preparation | 03:41 | CLAIMED | Ensure suitable image assembly, tiling/windowing, and data format for model runs. |
| RF-046 | Zarr raster mosaics | 08:05 | CLAIMED+DEMO | Write efficiently chunked raster mosaic products. |
| RF-047 | Multi-band imagery handling | 19:03 | EXAMPLE | Account for red/green/blue/near-infrared and 12-band inputs in imagery workflows. |
| RF-048 | Multi-temporal pairing | 12:30 | EXAMPLE | Prepare planting-season and harvest-season mosaics as separate inputs. |
| RF-049 | Planting/harvest seasonal heuristics | 12:42 | EXAMPLE | Select candidate seasonal windows for agricultural boundary model. |
| RF-050 | NoData coverage diagnosis | 04:29 | DISCUSSION | Detect or explain imagery mosaics with missing data. |
| RF-051 | Cloud-coverage diagnosis | 04:38 | DISCUSSION | Detect or explain temporal windows without cloud-free imagery. |
| RF-052 | Image seam/edge quality assessment | 04:38 | DISCUSSION | Check visible splits or boundaries in mosaic joins. |

### Inference — 21 entries (RF-053–RF-073)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-053 | Batch image model inference | 08:30 | CLAIMED+DEMO | Execute model over large multi-tile AOIs. |
| RF-054 | Distributed parallel inference | 08:30 | CLAIMED | Distribute processing across spatial mosaic and compute workers. |
| RF-055 | GPU utilization management | 03:48 | CLAIMED | Reduce idle accelerator time through managed task execution. |
| RF-056 | Window-based inference | 08:46 | CLAIMED | Use windows instead of naive independent image tiles to reduce edge effects. |
| RF-057 | Tile-boundary artifact suppression | 08:46 | CLAIMED+DEMO | Avoid or reduce artificial seams in predicted features. |
| RF-058 | Georeferencing of predictions | 33:24 | DEMO | Map model detections back to real-world spatial coordinates. |
| RF-059 | Raster prediction output | 08:54 | CLAIMED | Retain machine-learning output as a raster layer. |
| RF-060 | Raster-to-vector conversion | 09:03 | CLAIMED+EXAMPLE | Generate polygons from model output rasters. |
| RF-061 | Threshold-based polygonization | 13:13 | EXAMPLE | Turn pixel confidence values into field-boundary polygons. |
| RF-062 | Polygon shape/edge cleanup | 09:28 | CLAIMED | Refine rough predicted geometries with distributed GIS functions. |
| RF-063 | Cross-tile detection stitching | 33:32 | DEMO | Consolidate adjacent detections fragmented by source tile boundaries; example says red-car polygon count changed 539 to 375 after cleanup. |
| RF-064 | Connected components over intersects | 39:03 | DEMO | Group touching/intersecting polygons by connected components. |
| RF-065 | Same-category guard for stitching | 39:03 | DEMO | Require a matching prediction class when merging touching detections. |
| RF-066 | Class-specific detection layers | 26:14 | DEMO | Inspect roofs, roads, boats, cars, sports facilities, and more independently. |
| RF-067 | Roof and building detection | 26:14 | DEMO | Use SAM 3 text prompt for roofs/buildings. |
| RF-068 | Road segment detection | 26:57 | DEMO | Identify road features from aerial imagery. |
| RF-069 | Solar-array / solar-panel detection | 21:31 | EXAMPLE | Find distributed solar arrays using very high-resolution imagery. |
| RF-070 | Boat detection | 33:08 | DEMO | Identify boats from high-resolution imagery. |
| RF-071 | Red-vehicle detection | 33:08 | DEMO | Identify cars with specified visual attributes. |
| RF-072 | Baseball field detection | 33:08 | DEMO | Identify sports fields with possible partial geometry coverage. |
| RF-073 | Tennis-court detection | 33:08 | DEMO | Detect courts, subject to basketball-court false positives. |

### Analytics — 9 entries (RF-074–RF-082)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-074 | Raster-vector joins | 09:10 | CLAIMED | Join predicted feature geometries to existing geographic datasets. |
| RF-075 | Spatial SQL joins | 09:28 | CLAIMED | Run spatial matching against enterprise GIS layers. |
| RF-076 | Zonal statistics | 09:36 | CLAIMED | Calculate raster statistics within detected polygons or existing AOIs. |
| RF-077 | Agricultural NDVI by predicted field | 13:42 | EXAMPLE | Calculate vegetation index on predicted agricultural parcel polygons. |
| RF-078 | Agricultural field crop segmentation | 13:34 | EXAMPLE | Use boundary candidates to segment crop-growing regions. |
| RF-079 | Change monitoring at large scale | 10:58 | DIRECTION | Monitoring/change detection identified as key use case; not a fully specified implemented change-detection API. |
| RF-080 | Regional accuracy comparison | 15:00 | CASE_STUDY | Inspect variation in model performance by geography. |
| RF-081 | Annotation/labeling needs assessment | 40:32 | DEMO_DISCUSSION | Identify new labeling data required after visual QA of model results. |
| RF-082 | Model-selection feedback loop | 40:40 | DEMO_DISCUSSION | Compare model failures and choose alternate model. |

### Publish — 11 entries (RF-083–RF-093)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-083 | GeoParquet vector result handling | 24:57 | CLAIMED | Use geospatial columnar vector outputs as inputs to map publication. |
| RF-084 | Distributed GeoParquet-to-PMTiles conversion | 24:57 | CLAIMED+DEMO | Build optimized tiled vector map products. |
| RF-085 | PMTiles vector overlays | 09:50 | CLAIMED+DEMO | Render dense polygons interactively over broad AOIs. |
| RF-086 | Raster pyramid / overview creation | 25:14 | CLAIMED | Generate multiresolution raster levels to support fast pan/zoom. |
| RF-087 | Multiscale Zarr generation | 25:31 | CLAIMED+DEMO | Convert existing Zarr layers into map-browsable multiscale outputs. |
| RF-088 | Raster and vector overlay inspection | 26:14 | DEMO | Display SAM 3 PMTiles geometry on a high-resolution Zarr aerial basemap. |
| RF-089 | Selectable map class overlays | 26:57 | DEMO | Switch class layers on/off for inspection. |
| RF-090 | Tree canopy raster overlay | 27:40 | DEMO | Display canopy height estimates above aerial imagery. |
| RF-091 | Interactive zoom/pan at 30-cm resolution | 26:38 | DEMO | Browse high-resolution imagery without downloading full mosaics to desktop. |
| RF-092 | Downstream map consumer interoperability | 02:52 | CLAIMED | Publish results to environments named in transcript as Esri, CARTO, and Felt; precise integration contracts unspecified. |
| RF-093 | Data product distribution | 02:59 | CLAIMED | Deliver spatial result products to downstream business applications or customers. |

### S3 Security — 6 entries (RF-094–RF-099)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-094 | Use own S3 input buckets | 22:45 | CLAIMED | Use an existing authorized cloud bucket for inputs. |
| RF-095 | Use own S3 output buckets | 23:43 | CLAIMED | Persist derived imagery, detections and geometry in user-controlled storage. |
| RF-096 | Credential-managed storage integration | 23:58 | CLAIMED | Configure S3 permissions once via an administrator-managed connection. |
| RF-097 | No secrets in application code | 23:58 | CLAIMED | Reference configured storage integration rather than embedding access keys. |
| RF-098 | Object-store in-place processing design | 23:25 | CLAIMED | Avoid compulsory duplication of private parcel inputs into hosted vendor storage. |
| RF-099 | Managed vendor output storage | 08:10 | CLAIMED | Optionally save outputs in vendor-managed storage. |

### Agent Api — 14 entries (RF-100–RF-113)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-100 | AI agent driven GIS workflow | 36:25 | DEMO | Delegate imagery selection, mosaic creation, inference-result reuse, and publication sequence to agent. |
| RF-101 | Codex client | 32:41 | DEMO | AI coding agent used in live demonstration. |
| RF-102 | Claude or other LLM client | 41:23 | CLAIMED | Agent-first interface described as usable with multiple LLM coding tools; transcript phonetically transcribes one as 'quad'. |
| RF-103 | Task API | 37:02 | PLANNED+PREVIEW_DEMO | Upcoming agent-first reusable workflow API; release later in the month relative to session, not a verified current release. |
| RF-104 | Prebuilt mosaic task | 37:37 | PREVIEW_DEMO | Use a predefined task to build mosaics from included imagery catalogs. |
| RF-105 | Custom imagery mosaic task | 37:46 | PREVIEW_DEMO | Run task against GeoParquet-indexed custom COGs. |
| RF-106 | Reusable web-optimized raster task | 38:15 | PREVIEW_DEMO | Generate or fetch multiscale Zarr optimized for browsers. |
| RF-107 | Reusable vector publication task | 38:31 | PREVIEW_DEMO | Generate or fetch PMTiles for precomputed model detections. |
| RF-108 | Agent-issued spatial cleanup task | 38:47 | PREVIEW_DEMO | Launch connected-component cleanup over predictions from the agent. |
| RF-109 | Task output and cache reuse | 36:47 | DEMO | Reuse previously computed results instead of rerunning jobs; presenter shows about 55 seconds to fetch a cached mosaic, not a fresh benchmark. |
| RF-110 | Cross-agent-session artifact reuse | 38:15 | PREVIEW_DEMO | Find outputs created in earlier agent sessions. |
| RF-111 | Agent tool calls in lieu of notebooks | 41:14 | PLANNED | Shift from notebook generation/execution to directly invoked API tasks and tests. |
| RF-112 | In-agent task execution and result retrieval | 41:23 | PLANNED+PREVIEW_DEMO | Run workflows and collect outputs without leaving coding-agent experience. |
| RF-113 | Automatic data-source discovery by agent | 36:32 | DEMO | Agent identifies matching imagery for a requested AOI. |

### Workflows — 10 entries (RF-114–RF-123)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-114 | Full Earth-observation pipeline | 03:33 | CLAIMED | Source -> index -> ingest -> composite -> mosaic -> infer -> refine/vectorize -> join/analyze -> publish; nine stages are asserted but not explicitly enumerated one-by-one. |
| RF-115 | Fields-of-the-World agricultural boundaries | 11:58 | CASE_STUDY | Read Sentinel-2 COGs -> create two seasonal mosaics -> infer -> Zarr scores -> polygonize -> optionally NDVI/zonal stats. |
| RF-116 | Global agricultural boundaries 2023 and 2024 | 14:19 | CASE_STUDY | Presenter reports approximately 500 TB Sentinel-2 mosaics, more than 100 TB initial Zarr outputs, and more than 600 GB vector geometries shared with Source Cooperative; unverified. |
| RF-117 | USFS wildfire containment updates | 15:30 | CASE_STUDY | Fuse terrain/weather/moisture -> FireCon -> frequent containment suitability updates; presenter claims less than two hours for western US versus previous daily schedule. |
| RF-118 | Urban solar-roof inventory | 21:31 | EXAMPLE | High-resolution NAIP mosaic -> SAM 3 class detection -> vector spatial output. |
| RF-119 | Kentucky multi-class inventory demo | 32:21 | DEMO | Index nine imagery tiles -> mosaic -> prompt SAM 3 for multiple classes -> georeference -> stitch -> PMTiles review. |
| RF-120 | Canopy-height viewing workflow | 27:40 | DEMO | Aerial base mosaic -> multiscale Zarr -> canopy-height inference -> raster overlay. |
| RF-121 | Tile seam geometry consolidation | 38:47 | DEMO | Take per-tile detections -> intersect same-class polygons -> connected-components merge -> inspect resultant geometry. |
| RF-122 | Agent-driven cached mosaic and publication | 36:25 | PREVIEW_DEMO | Agent finds imagery and cache -> builds/recalls mosaic -> web raster -> detection PMTiles -> geometry cleanup. |
| RF-123 | Recurring EO data products | 02:38 | CLAIMED | Discover/prepare/validate pipeline once, then rerun regularly for downstream apps. |

### Ecosystem — 16 entries (RF-124–RF-139)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-124 | AWS S3 object storage | 02:29 | EXTERNAL | Cloud object-store backbone for source COGs, private AOIs, and generated outputs. |
| RF-125 | Google Earth Engine | 28:23 | EXTERNAL_COMPARISON | Earth-observation platform used as vendor comparison for capability, pricing, and export friction. |
| RF-126 | Google Vertex AI | 29:34 | EXTERNAL_COMPARISON | Referenced as a model-inference service users might integrate with Earth Engine. |
| RF-127 | Esri mapping ecosystem | 02:52 | EXTERNAL | Named downstream visualization consumer; precise interface not specified. |
| RF-128 | CARTO platform | 02:52 | EXTERNAL | Named downstream visualization consumer; precise interface not specified. |
| RF-129 | Felt mapping platform | 02:52 | EXTERNAL | Named downstream visualization consumer; precise interface not specified. |
| RF-130 | Source Cooperative | 14:53 | EXTERNAL | Open-data sharing destination for published worldwide field geometries. |
| RF-131 | Taylor Geospatial | 14:03 | EXTERNAL | Named partner in global Fields of the World agricultural boundary processing. |
| RF-132 | GDAL and Rasterio (likely speech transcription) | 17:27 | TRANSCRIPT_UNCERTAIN | Audience poll appears to name typical self-managed raster tools; transcript gives 'Galileo, Restio', so exact tools unverified. |
| RF-133 | Notebook-based Wherobots workflow | 41:14 | PREVIOUS_APPROACH | Earlier agent approach generated a notebook to execute in vendor cloud; new Task API is positioned as replacement. |
| RF-134 | PyTorch PT2 archive format | 06:33 | CLAIMED | Model package interchange format for registering user models. |
| RF-135 | Cloud Optimized GeoTIFF (COG) | 06:00 | CLAIMED+DEMO | Indexed imagery artifact used as input to mosaic workflows. |
| RF-136 | GeoParquet | 23:18 | CLAIMED+DEMO | Columnar geospatial format used for AOIs, image indexes, and vector publication source. |
| RF-137 | Zarr | 08:05 | CLAIMED+DEMO | Chunked cloud-native raster array format; transcript repeatedly transcribes 'ZAR'. |
| RF-138 | PMTiles | 09:50 | CLAIMED+DEMO | Single-file web map tile format for scalable polygon overlay visualization. |
| RF-139 | Model Context Protocol (MCP) | 01:47 | CLAIMED | Agent-to-spatial-tool connection protocol. |

### Finops — 10 entries (RF-140–RF-149)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-140 | Input-volume based task pricing | 18:39 | CLAIMED | Estimate processing charge from pixels, bands, time slices, and task multiplier. |
| RF-141 | Spatial units calculation | 19:14 | CLAIMED | Normalize into billions-of-pixel-values units; example 500 km2 at 30 cm and four bands is roughly 22 billion band-pixel values. |
| RF-142 | Per-task complexity multipliers | 19:37 | CLAIMED | Different pricing factors for mosaic, inference, vectorization tasks. |
| RF-143 | Up-front workflow cost estimation | 18:55 | CLAIMED | Estimate spend before submission from AOI, resolution, spectral bands and time slices. |
| RF-144 | Agricultural boundary example price | 20:13 | CASE_STUDY | 150,000 km2 Sentinel-2 dual-mosaic example claims $9 mosaic and about $3.60 inference plus minor vectorization, less than $13 total; not current quote. |
| RF-145 | Urban solar example price | 21:31 | CASE_STUDY | 500 km2 NAIP 30 cm example: approximately $167 mosaic plus $25 SAM 3 inference, source price only. |
| RF-146 | GEE comparison | 28:23 | VENDOR_CLAIM | Vendor positions price predictability and integrated model execution against Google Earth Engine. |
| RF-147 | AWS S3 egress considerations | 30:06 | VENDOR_CLAIM | Evaluate export, transfer, and egress costs when comparing cloud platforms. |
| RF-148 | 12-band Sentinel-2 mosaic comparison | 30:41 | VENDOR_CLAIM | Vendor cites $13.50 RasterFlow vs $50 Google Earth Engine in a specified example. |
| RF-149 | Pipeline engineering cost model | 05:02 | VENDOR_CLAIM | Vendor estimates approx. 3 engineers in year 1 and 1.5–2 ongoing; not verified. |

### Quality — 8 entries (RF-150–RF-157)

| ID | Function / tool / workflow | Timestamp | Status | Source-grounded description |
|---|---|---|---|---|
| RF-150 | False-positive class confusion | 34:33 | DEMO | Tennis-court model may confuse basketball courts; human validation needed. |
| RF-151 | Partial object delineation | 34:42 | DEMO | Baseball model may map only the infield, not whole field. |
| RF-152 | False-negative detections | 33:51 | DEMO | SAM 3 may miss some target boats/objects. |
| RF-153 | Tile-edge fragmentation | 33:32 | DEMO | Model predictions crossing source tiles may be split into false separate geometries. |
| RF-154 | Cache-result provenance caution | 36:47 | INFERRED_RISK | Exact task parameters, model/version, data versions and AOI must be part of cache identity; not guaranteed by transcript. |
| RF-155 | Contradictory boat count anecdote | 39:37 | TRANSCRIPT_ISSUE | Speaker says spurious polygons were reduced 'from 24 to 51' (increase): cannot treat as verified reduction. |
| RF-156 | Predicted geometry not authoritative identity | 39:03 | INFERRED_RISK | Same class plus touching polygons is only a postprocessing rule, not proof that real-world features are identical. |
| RF-157 | Source/version/accuracy QA gaps | 40:32 | INFERRED_RISK | No complete accuracy metrics, benchmark protocol, provenance schema, CRS contract, or certification tests given. |

## Data-quality flags

These rows must not be restated as verified facts or used without their caveat.

| Entry | Status | Why it needs a caveat |
|---|---|---|
| RF-155 | TRANSCRIPT_ISSUE | The speaker's spurious-polygon figure "from 24 to 51" is described as a reduction, but 51 is larger than 24. The direction and size of the change are unverified. |
| RF-063, RF-153 | DEMO | A polygon count changing from 539 to 375 after cleanup shows fewer polygons, not that the result is more accurate. No ground truth was given. |
| RF-116 | CASE_STUDY | The volumes (about 500 TB of mosaics, more than 100 TB of initial Zarr outputs, more than 600 GB of vector geometries) are presenter-reported and marked unverified in the source. |
| RF-149 | VENDOR_CLAIM | The engineering-headcount estimate is a vendor estimate, not verified. |
| RF-132 | TRANSCRIPT_UNCERTAIN | The transcript gives "Galileo, Restio"; GDAL and Rasterio are an inference from speech, not a statement. |
| RF-022 | DEMO | The Kentucky imagery provider is transcribed as "Kai from above"; the proper name is unverified. |
| RF-102 | CLAIMED | One client is transcribed phonetically as "quad"; reading it as Claude is an inference. |
| RF-103 and the other planned or preview agent entries (RF-104–RF-108, RF-110–RF-112, RF-122) | PLANNED / PREVIEW_DEMO | The Task API was described as upcoming relative to the session date and shown in preview. Its release state today is unverified, and so is whether the neighbouring preview entries ship with it. |
| RF-017 | PLANNED | Sentinel-1 is a future catalog entry and was not described as available. |
| RF-079 | DIRECTION | Change monitoring was named as a key use case but not as a fully specified, implemented change-detection API. |
| RF-114 | CLAIMED | Nine pipeline stages are asserted, but the source does not enumerate them one by one; the arrow chain in the entry is the extraction's reading. |
| RF-109 | DEMO | The "about 55 seconds" is the time to fetch a cached mosaic. It is not a benchmark of a fresh run. |
| RF-144, RF-145, RF-148 | CASE_STUDY / VENDOR_CLAIM | The prices and the vendor comparison are presenter-reported examples, not current quotes and not a verified comparison. |
| RF-154, RF-156, RF-157 | INFERRED_RISK | These are analytical cautions drawn from the examples, not features or statements by the speaker. They stay in the catalog so that the cautions are not lost. |

Arithmetic check (ours, not the source's): 500 km² at 30 cm resolution is about 5.56 billion
pixels, and four bands make about 22.2 billion band-pixel values, which matches the "roughly 22
billion" in RF-141. This confirms the example's arithmetic only, not the pricing built on it.

## Independently recommended federation integration (not stated in the webinar)

The block below is recorded as supplied with the extraction. It is a recommendation about how the
federation might use these capabilities. **It is proposed and not adopted**, and it conflicts in
places with accepted decisions; ADR 0011 records those conflicts and leaves the authority mapping
open.

- **Spiderweb-PR (primary spatial authority):** imagery catalogs, COG/GeoParquet indexes, Zarr
  mosaics, model outputs, windowed inference, raster-to-vector transformation, tile-seam review,
  spatial joins/zonal statistics, PMTiles publication, lineage and geometry QA. Predicted features
  remain candidates until independently checked.
- **AguaYLuz-PR:** canopy and vegetation risk, solar infrastructure candidates,
  wildfire/environmental change layers, updated aerial context; do not present predicted utility
  connectivity as authoritative.
- **Skywatcher-PR:** controlled image-analysis context and independent annotation, never convert a
  static imagery detection into verified live aircraft identity or UAP proof.
- **MoneySweep-PR:** imagery-derived facility/parcel leads for source-linked project/infrastructure
  investigation, but never image-only contractor or ownership identity.
- **Centinelas-PR:** model output triage, false-positive review, confidence scores, change-alert
  queues, user reports and adjudication trails.
- **OVNIS-PR:** contextual Earth-observation layers with explicit "model inference" provenance;
  not an evidentiary substitute for observations.
- **Mucaro AI:** governed agent Task API client, reusable pipeline templates, cache/provenance
  binding, preflight cost estimates, adversarial QA.
- **TheHub-PR:** cross-repo contracts, scheduling, authorization/security boundaries,
  exact-version receipts, independent verification and release gates; no duplicate domain
  authority.

### Required gates before implementation or certification

Independent API/current availability verification; data rights/licenses; S3 least privilege and
credential rotation; CRS, vertical datum, resolution, spatial/temporal alignment;
no-data/cloud/seam controls; GPU/economic estimates; versioned model and cache keys;
classification and polygonization accuracy tests; spatial identity constraints; source immutable
SHA-256 provenance; false-positive/false-negative audits; consumer performance/regression testing;
human review and exact-build/federation receipts.

These are governance recommendations, not capabilities proved by the transcript. ADR 0011 maps
each gate to the federation document that already covers it, or marks it as new.

## What this snapshot does not claim

- That any listed capability exists today, works as described, or is available to the federation.
- That any price, volume, speed or cost comparison is accurate or current.
- That any model named here (SAM 3, Fields of the World, FireCon, the canopy-height model) is
  accurate for Puerto Rico or for any federation use. No accuracy metrics were given (RF-157).
- That any API, client, credential or network path exists in this repository. None is added.
