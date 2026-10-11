# USGS Puerto Rico release catalog

The hub registers the supplied workbook as a frozen snapshot: 174 included
releases (86 PR-specific, 15 PR plus other territories, 73 national/global) and
23 excluded candidates. Included ScienceBase IDs are distinct; three DOIs are
blank. Preserve workbook bytes and SHA-256. XLSX empty inline strings remain
empty strings; raw names, punctuation and source notes are unchanged.

The product surface is **Records → USGS Catalog** (`/usgs-catalog`). It reads the
catalog and acquisition receipts. Search and consumer filters do not change
source records. Reload catalog reloads local evidence, not upstream data.

## Repository bindings

Program/repository bindings come from `registry/producers.yaml` at the build's
base commit. Dataset/consumer suggestions remain `CANDIDATE_NOT_IDENTITY`.
Title rules are discovery, not asset-fitness evidence. All releases receive
Spiderweb context-review candidates. Water/environment terms add AguaYLuz;
selected resource-use/infrastructure terms add MoneySweep context candidates.
Preserve the complete candidate set. Do not force releases into OVNIS,
Skywatcher or Centinelas solely because they concern Puerto Rico. These are
staged catalog relationships, not producer ingestion deployments.

## Verification and activation

`data/usgs/snapshots/20261011T013000Z` records 174 direct ScienceBase metadata
attempts: **174 HTTP 403**, **0 activated payloads**. Retain per-request URL,
retrieval UTC, response status, raw bytes, byte length and SHA-256. The directory
label identifies a run; per-request UTC is the retrieval authority. This is
bounded transport evidence, not source absence. Asset enumeration and payload
verification remain BLOCKED. No GIS geometry or operational alert is derived.

The metadata adapter validates requested/returned IDs, preserves ordered file
descriptors, facets and links, caps bytes and refuses redirects. Child
enumeration remains OPEN unless metadata explicitly says `hasChildren=false`.
No child-crawl or CSV/GeoTIFF/NetCDF/SEG-Y/shapefile payload adapter is claimed
as implemented. Those require actual assets and domain-specific inspection.

Reuse frozen observations, including failed responses. A new output directory
creates a new snapshot; never overwrite evidence to obtain a PASS. Activation
requires asset/child denominator closure, hashes, usage constraints, lineage,
actual PR coverage, schema/count invariants, consumer review, format-adapter
tests and producer export compatibility. Preserve raw CRS/Z/M and geometry;
derive separate analysis geometries. Missing/tied evidence fails closed.
Archive comparison requires member paths, uncompressed sizes and hashes.

## Open inventory issues

- 186 workbook-reported keyword hits versus 197 included/excluded rows.
  Supplementary discovery is mentioned without per-row attribution.
- Direct children of one collection are the stated universe. Coverage does
  not extend to every USGS dataset or metadata-silent PR records.
- National/global place keywords do not establish actual PR records.
- Notes flag a global extent, swapped coordinates, deprecated releases and
  an entry under revision. Preserve these as observations, not corrections.

## Validation

Use root `TERMINAL_READY.txt`. The scoped manifest covers source workbook,
catalog, response snapshots and integration files. It does not certify the
entire repository, upstream completeness or payload correctness.

Local results: 40 Python tests (including adjacent API regressions), two UI
tests, frontend production build, lint and static GUI parity passed. Playwright
was attempted but Chromium download failed; browser interaction remains
BLOCKED. Keep the PR in draft until that gate passes. No production publishing,
producer readiness promotion or payload activation accompanies this change.

Execution-plan assessment: 93/100. Hardening assessment: 92/100. These are design
assessments, not certification scores. Live asset access, consumer adjudication
and browser verification remain unresolved.
