# ADR 0011 — Wherobots RasterFlow: record the capability catalog, adopt nothing

- **Status:** Proposed
- **Date:** 2026-11-05
- **Deciders:** PRII federation maintainers
- **Scope:** `thehub-pr` only (a reference record). No producer repository changes.
- **Relates to:** [ADR 0006](0006-skywatcher-ai-imagery-centralization.md) (provider access, credentials, model egress); [ADR 0004](0004-federation-governance-layer.md) (dispositions); [GIS Architecture v1](../GIS_ARCHITECTURE_V1.md); [GIS Raster Certification Vector v1](../gis/GIS_RASTER_CERT_VECTOR_v1.md); [GIS Acquisition v2](../GIS_ACQUISITION_V2.md)
- **Evidence:** [`docs/gis/WHEROBOTS_RASTERFLOW_CATALOG_2026-11-05.md`](../gis/WHEROBOTS_RASTERFLOW_CATALOG_2026-11-05.md) and `registry/external_services/wherobots_rasterflow_catalog.v1.json`

## Context

A user-supplied transcript of a Wherobots RasterFlow webinar was extracted into a 157-entry
capability catalog (13 groups, `RF-001`..`RF-157`) together with a recommendation for how each
federation repository might use it. The evidence is **tier T4**: a vendor-presented webinar seen
through an automatic transcript. No vendor documentation was independently checked, current
availability is unverified, and every price, volume and timing in it is a vendor-presented figure.

Three existing federation decisions bear on whether and how RasterFlow could ever be used:

1. **ADR 0006 (Accepted).** TheHub owns satellite-provider network access, credential brokering
   with no-readback injection, provider and model allowlists, model routing, content-addressed
   source-artifact storage, acquisition/tool/model-run receipts and egress policy. Producers do
   not call external model services; a producer worker runs with outbound network denied by
   default.
2. **Spiderweb's DuckDB decision** (`spiderweb-pr/docs/DUCKDB_SPATIAL.md`, "Why DuckDB, not
   Spark/Sedona/Wherobots"). Spiderweb's data is Puerto-Rico-scoped and megabytes in size with no
   documented scaling bottleneck, so a cluster-scale engine was rejected. Its stated trigger to
   revisit is a producer ingesting data that no longer fits single-machine memory.
3. **The GIS freeze.** TheHub's frontend is the supported product surface and producers remain
   spatial/data producers unless separately promoted (GIS Architecture v1). Spatial proximity
   defaults to `CANDIDATE_NOT_IDENTITY`; five identity layers stay separate (GIS Acquisition v2);
   a missing CRS or geotransform fails closed, and "TIFF decoding is not COG certification"
   (Raster Certification Vector v1). In the capability matrix, Spiderweb is a *consumer* of the
   raster/DEM contract, AguaYLuz adds the v1 raster contract, and Skywatcher owns GEBCO terrain.

The recommendation names Spiderweb the primary spatial authority for RasterFlow-style pipelines
and Mucaro a "governed agent Task API client". Read against 1–3, that mapping would need
amendments to accepted decisions. Separately, `mucaro-ai` is not a registered federation
producer: it appears in neither `registry/producers.yaml` nor
`governance/federation_dependencies.yaml`.

## Decision

**D1 — Record the catalog as a non-authoritative reference.** The catalog is kept as a dated
snapshot (human-readable) and a registry file (machine-readable). Each entry keeps the status the
presenter gave it (claimed, demonstrated, case study, planned, preview, inferred risk, and so on).
Claims stay claims.

**D2 — Adopt nothing.** This ADR authorizes no client code, adapter, dependency, credential,
bucket, provider account, scheduled job, network egress or contract change. No runtime reads the
registry file. Listing a capability authorizes nothing.

**D3 — Evidence handling.** Anything that cites the catalog for a decision cites the entry ID and
its status. A `DEMO` or `PREVIEW_DEMO` status is not evidence that a capability is available
today. Vendor figures (prices, data volumes, timings, cost comparisons) are not restated without
the words "vendor-presented". Entries flagged `INFERRED_RISK`, `TRANSCRIPT_ISSUE` or
`TRANSCRIPT_UNCERTAIN` are never used as support for a capability.

**D4 — The authority mapping is OPEN.** Two options are recorded. This ADR takes no position
between them until the gates in D5 close.

| Aspect | Option A — Hub brokers, producers consume | Option B — Spiderweb primary, as recommended |
|---|---|---|
| Vendor credentials, S3 integration, egress decisions | TheHub Control Plane (ADR 0006 as written) | Spiderweb; needs an amendment to ADR 0006 |
| Who triggers RasterFlow jobs | A Hub-authorized job; results land as a content-addressed source artifact with an immutable receipt | A Spiderweb pipeline directly |
| Spiderweb's role | Producer. Consumes certified outputs and publishes candidate layers (`CANDIDATE_NOT_IDENTITY`) | Primary spatial authority for the pipeline stages named in the recommendation |
| Spiderweb DuckDB decision | Stays in force; its "no longer fits one machine" trigger is the revisit condition | Must be superseded, with evidence of a scaling bottleneck |
| Mucaro's role | A client only through a Hub-brokered contract; it must be registered before any dependency exists | "Governed" Task API client, but where the governance lives is undefined until the amendment |
| Conflicts with accepted decisions | None identified in the documents read for this ADR (not an exhaustive check) | ADR 0006 (provider access, credentials, egress, deny-network producers); the Spiderweb DuckDB decision; GIS Architecture v1 ("producers remain producers"); the capability matrix (Spiderweb as raster consumer, AguaYLuz adding the v1 raster contract) |
| Needs before any implementation | The D5 gates plus a new Hub contract for external-service jobs and receipts | The D5 gates plus an amendment ADR and updates to Spiderweb's own documents |

Neither option is free. Option A needs a Hub contract that does not exist yet. Option B needs
accepted decisions changed first.

**D5 — Gates.** The recommendation lists thirteen gates that must close before implementation or
certification. They are governance requirements, not capabilities proved by the transcript. Each
is mapped below to the federation document that already covers it, or marked new.

| # | Gate (as supplied) | Existing federation coverage | Gap |
|---|---|---|---|
| 1 | Independent API / current-availability verification | None | **New.** Every entry rests on a webinar; the Task API was described as upcoming. |
| 2 | Data rights / licenses | GIS Architecture v1: commercial providers are credential-gated and never silently substituted; the source identity contract carries license and attribution | **New** for RasterFlow and model terms. RF-019 itself says licensed imagery needs separate checking. |
| 3 | S3 least privilege and credential rotation | ADR 0006: credential brokering, no-readback injection | **New** for bucket policy and the vendor-side storage integration (RF-094–RF-099). |
| 4 | CRS, vertical datum, resolution, spatial/temporal alignment | Raster Certification Vector v1 (fail-closed CRS and geotransform; explicit reprojection); capability matrix rule 4 (WGS84/CRS84 canonical) | Vertical datum is not covered (Mucaro's V1 GIS controls explicitly exclude vertical CRS). Multi-season alignment is new (RF-025, RF-048). |
| 5 | No-data, cloud and seam controls | Raster Certification Vector v1; Skywatcher's SATIM imagery seam-origin firewall document | **New** for vendor mosaics and window-based inference (RF-043, RF-050–RF-052, RF-057, RF-153). |
| 6 | GPU / economic estimates | None | **New.** RF-140–RF-149 are vendor claims, not quotes. |
| 7 | Versioned model and cache keys | ADR 0006 model-field provenance (immutable model revision, prompt hash, policy version) | Extend to cache identity: parameters, model version, data version and AOI must be part of the key (RF-154). |
| 8 | Classification and polygonization accuracy tests | Precedent: Mucaro's analytic-control manifest (`mucaro-ai/_architecture/gis_v1_control_manifest.json`) | **New.** The source gave no accuracy metrics or benchmark protocol (RF-157). |
| 9 | Spatial identity constraints | Capability matrix rule 3 (`CANDIDATE_NOT_IDENTITY`); GIS Acquisition v2 | Covered in principle. RF-156: same class plus touching polygons is a post-processing rule, not identity. |
| 10 | Immutable SHA-256 source provenance | GIS Acquisition v2 identity layers (RAW, QUERY_RECEIPT, SNAPSHOT, NORMALIZED, CANONICAL) | Extend to vendor-produced Zarr mosaics and PMTiles. |
| 11 | False-positive / false-negative audits | None | **New** (RF-150–RF-153 show confusion, partial delineation, misses and tile-edge fragmentation). |
| 12 | Consumer performance / regression testing | The `gis-renderer-lock` workflow | PMTiles and COG are still OPEN in the GIS Architecture v1 format table, and Zarr is not listed there. |
| 13 | Human review and exact-build / federation receipts | ADR 0006 (producer review and Hub certification are distinct; model-run receipts); ADR 0004 (dispositions) | Reuse as is. |

**D6 — Proposed, unadopted roles.** The recommendation is preserved in full in the catalog
snapshot. In short, with the guard-rail each role came with:

| Repository | Proposed role (recorded input) | Guard-rail as supplied | Note |
|---|---|---|---|
| spiderweb-pr | Primary spatial authority: catalogs and indexes, mosaics, model outputs, windowed inference, vectorization, seam review, joins, PMTiles, lineage and geometry QA | Predicted features remain candidates until independently checked | Option B; see D4 |
| aguayluz-pr | Canopy and vegetation risk, solar candidates, wildfire/environmental change layers, aerial context | Do not present predicted utility connectivity as authoritative | Adds the v1 raster contract in the capability matrix |
| skywatcher-pr | Controlled image-analysis context and independent annotation | Never convert a static imagery detection into verified live aircraft identity or UAP proof | ADR 0006 migrates its imagery and model access to the Hub |
| moneysweep-pr | Imagery-derived facility and parcel leads for source-linked investigation | Never image-only contractor or ownership identity | Has its own claim-language policy |
| centinelas-pr | Model-output triage, false-positive review, confidence scores, change-alert queues, adjudication trails | None beyond adjudication | |
| ovnis-pr | Contextual Earth-observation layers with explicit "model inference" provenance | Not an evidentiary substitute for observations | |
| mucaro-ai | Governed agent Task API client, pipeline templates, cache/provenance binding, preflight cost estimates, adversarial QA | None stated | Not a registered producer |
| thehub-pr | Cross-repo contracts, scheduling, authorization and security boundaries, exact-version receipts, verification and release gates | No duplicate domain authority | Fits Option A directly |

**D7 — Revisit.** This ADR is revisited, and either accepted with one option or superseded, when
any of these happens: the vendor's documentation and availability are independently verified
(gate 1); a producer's data stops fitting single-machine memory, which is the Spiderweb DuckDB
trigger; or a maintainer asks for Option B and brings the amendments with it.

## What this does not do

- It does not verify the vendor, the Task API's release state, any price or any model's accuracy.
- It does not amend ADR 0006, supersede the Spiderweb DuckDB decision or change any contract.
- It does not add a schema (`schemas/` is frozen), a producer registration or a dependency edge.
- It does not touch `spiderweb-pr`, `aguayluz-pr`, `skywatcher-pr`, `moneysweep-pr`,
  `centinelas-pr`, `ovnis-pr` or `mucaro-ai`.

## Consequences

- The catalog is searchable and cannot be quietly upgraded: `tests/test_wherobots_rasterflow_catalog.py`
  pins the counts, the status vocabulary, the cautioned entries and the parity between the
  snapshot and the registry file.
- Nothing new can reach the network, hold a credential or become a dependency because of this
  change.
- The catalog is a dated snapshot and will go stale; gate 1 is what would refresh it.
- The authority question stays open, so anyone proposing implementation must return to this ADR
  first.

## Verification

1. `tests/test_wherobots_rasterflow_catalog.py` passes: 157 entries in 13 groups, contiguous IDs,
   a closed status vocabulary, the pinned cautions, and snapshot/registry parity.
2. `python3 tools/check_docs_sync.py --base origin/main` reports no violations.
3. The only paths added are this ADR, the snapshot, the registry file and the test.
