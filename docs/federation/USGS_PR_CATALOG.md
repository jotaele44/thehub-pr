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

## 2026-10-16 continuation (supersedes current-status statements above)

The historical 174 HTTP 403 responses remain unchanged. An independent GitHub
Actions acquisition retrieved all 174 root metadata items with HTTP 200; the
root archive SHA-256 is
`47488d1d72a2a43b8c2a4d3b44b600d4852ceca99e6796aae334814f95e7f7c8`.
Recursive ScienceBase child pagination closes at 463 items (174 roots plus 289
children), 2,286 file descriptors and 1,388,684,784,993 declared bytes. This
closure covers the files/children API, not every external service or web link.

A bounded 256 MiB acquisition produced 593 source size/checksum passes, 82
checksum disagreements and 1,611 blocked assets. All 593 passes and 82 failures
were independently checked against frozen bytes. Source disagreement causes
remain unresolved; failed bytes and original descriptors are quarantined,
never corrected or substituted. Structural inspection is separate from byte
verification. Scientific semantics, actual PR coverage, units, CRS/Z/M,
lineage, constraints and consumer fitness remain OPEN. Activated payloads: 0.

Frozen payload evidence is GitHub Actions run `38859073401`, artifact
`12028712192`, archive SHA-256
`b8fed761b822c9287a6423e9ca9ad4df5d49453e57dffb727d40568873459b72`.
The 193,972,102-byte archive was also delivered as a durable downloadable copy.
Git stores its exact inventory as deterministic gzip, the narrow verification
receipt and quarantine inventory, plus the small root metadata archive.
Ordinary CI validates frozen evidence offline; it does not repeat acquisition.
`scripts/continue_usgs_pr.py` supports explicit continuation with verified
caches, preserves all root memberships and rejects cycles and count changes.

The six repository identities and declared roles were checked against frozen
`federation.json` manifests. `registry/usgs/binding_review.v1.json` distinguishes
repository identity PASS from consumer fitness OPEN. Proposed bindings are
unchanged discovery candidates. In particular, biodiversity is not established
utility ownership, a historical science release is not an early signal or UFO
case, and terrain context alone does not establish an aviation observation.
A producer's declared readiness is not readiness for these new inputs.

`data/usgs/staging` contains six reference intake envelopes. These are reviewable
producer handoffs with release IDs, asset IDs, byte verdicts, source contract
blobs and unresolved gates. They do not emit canonical producer streams.
Production producer exports and staged activation remain BLOCKED. No sibling
repository runtime has been changed or certified by these envelopes.

A source-native GeoJSON adapter is tested on three checksum-verified NSHM2025
assets: 51 site points (`SiteID`), six fault polygons (`PolyID`) and 35 fault
sections (`FaultID`). Native features, raw CRS and source keys are retained;
keys are scoped to their asset. The adapter rejects duplicate/missing keys and
never transforms coordinates, fabricates geometry, clips to PR or certifies
hazard meaning. These 92 source features remain staged and inactive. Raw
compressed GeoJSON copies allow repeatable adapter checks without redownload.
Rebuild review packages with:

```sh
python scripts/stage_usgs_pr.py --archive /absolute/path/USGS_PR_Asset_Evidence_20261016.zip
python scripts/verify_usgs_build.py
```

Title reconciliation closes at 174 unchanged titles and identical stable-ID
sets. All 171 nonblank workbook DOIs agree with authoritative identifiers;
three blanks remain blank. One lowercase `doi` type label superseded an initial
case-sensitive diagnostic miss. Raw metadata and the diagnostic contradiction
are preserved in `metadata_contradictions.v1.json`.

Validation for this continuation: 53 focused/adjacent Python tests, static GUI
parity and changed Python lint pass. Earlier catalog browser checks passed at
desktop, tablet and mobile web sizes using Chromium 153; that is not physical
iOS evidence. The standard pinned CI browser and full repository CI have
separate receipts. Broader local GIS browser checks were blocked by the local
WebGL environment. Do not infer complete GUI or scientific certification from
the catalog checks. Root `TERMINAL_READY.txt` is included, with an additional
staging-level copy. Historical build hashes are preserved separately.

The inherited dual-run comparator also received a local-variable rename to
resolve five mypy errors across text, set and numeric branches; behavior is
unchanged and its existing readiness tests were rerun.

Final local checks: 53 USGS/adjacent API tests plus 32 dual-run readiness
tests pass, mypy passes across 99 source files, repository Ruff passes, two
catalog UI tests and frontend build pass. Catalog navigation/search/filter
passes in three Chromium 153 viewport projects. Static GUI parity reports
1,428 current symbols, 255 mapped, 1,173 unchanged legacy symbols, zero new
residue; the broader contract audit reports PASS with zero material findings.
The source audit pin is `a96c7bf64805d784af579410a800dda304bac282`.

## Producer export continuation (2026-10-16)

Spiderweb PR [419](https://github.com/jotaele44/spiderweb-pr/pull/419) owns the
native reference adapter and declares its explicit diagnostic export command
in its federation manifest. It uses Spiderweb's existing canonical writer,
rather than creating another producer implementation in the Hub. The exact
code pins and executed-file hashes are in
`registry/usgs/producer_export_code.v1.json`. Original repository manifest
snapshots remain unchanged; this draft command is not a merged production
capability.

`data/usgs/producer_inputs/spiderweb-native.v1.json` binds three assets to the
original inventory, descriptors, source checksum, raw SHA-256, root release IDs
and actual retrieval UTC. No successful source asset was fetched again.
`data/usgs/producer_exports/spiderweb-native-v1` is a real **test-mode** canonical
package: three source records and 92 documentary snapshot observations.
The Hub canonical validator accepts its schemas and byte/count manifest.
The independent `src/hub/usgs_exports.py` validator also checks the source
inventory, typed source keys, content-scoped producer IDs, source references,
timestamp meaning and entire native feature objects. It does not trust a
successful producer script or recomputed export hashes as sufficient proof.

Membership reconciliation on `(asset_id, source-key type, raw source key)`:
intersection 92, A_ONLY 0, B_ONLY 0, union 92, symmetric difference 0. Whole
features and collection metadata including CRS are preserved by canonical JSON
comparison; the original compressed GeoJSON still preserves raw bytes. No
coordinate transformation, canonical location, inferred event date, PR-only
filter, jurisdiction assignment or hazard claim is emitted. `observed_at`
means source retrieval. Confidence 0 is explicitly unassessed domain confidence,
not a contradiction of successful byte verification. Geometry and scientific
fitness remain unresolved.

`registry/usgs/activation_matrix.v1.json.gz` retains all 2,286 assets: 593 byte
PASS, 82 FAIL, 1,611 BLOCKED. Three assets have a passed documentary test adapter;
the remaining adapter states are OPEN. Every production export and activation
row remains BLOCKED. The 174-release catalog is unchanged. Other producer
candidate sets remain intact; no historical science release was promoted into
an early signal, money record, anomaly case or airspace event.

Regenerate validation/gate receipts, without network access:

```sh
python scripts/validate_usgs_exports.py --write-receipts
python scripts/verify_usgs_build.py
```

The API and normal catalog page expose the bounded 3/2,286 test-export scope and
production blocker. The producer command rejects production mode before writing
and refuses nonempty output directories. Regression negatives cover duplicate
and lost rows, changed geometry/CRS/raw attributes, timestamp reinterpretation,
foreign IDs/source links, forged root membership and promotion flags even when
package hashes and IDs are recalculated. The producer adds path/size, malformed
JSON, duplicate fields, non-finite values and typed-key gates.

Current local validation: 1,712 Hub tests pass, 17 skip; 33 producer adapter and
writer tests pass; 16 dedicated independent export tests pass. Hub mypy checks
100 source files, changed producer Ruff and Hub Ruff pass. The first producer
USGS CI job independently validated the frozen fixture export against pinned
Hub schemas. A documentation reference failure was corrected without changing
source bytes or weakening checks. Exact release-head CI is tracked separately.
These results establish the bounded test export, not production certification.

An isolated consumer rehearsal now also passes: the existing Hub aggregator
retains all 3 sources and 92 observations with zero collisions, adding only its
`_producers` provenance. Whole source rows and memberships are conserved. The
original test package and production producer registry remain byte-identical.
Rehearsal outputs under `data/usgs/rehearsals/spiderweb-native-v1` are explicitly
NONCANONICAL/test-only, and include their own root `TERMINAL_READY.txt`. No live
consumer activation was performed. The receipt is
`registry/usgs/consumer_rehearsal.v1.json`.

The full local coverage run passes: 1,712 tests, 17 skipped, 88.83% coverage
against the unchanged 88% minimum. 18 catalog/adjacent GIS UI tests, lint and
frontend build pass. The final catalog status regression also passes.
Producer command compatibility metadata was updated when CI required its
additive federation-manifest change to carry a compatibility receipt; no gate
was removed or weakened. The Hub source audit pin now identifies
`cbaa7d0c25c81b650e3a6354c0cd5631c39cbeb0`.


## Frozen source review and release refusal (2026-10-17)

The producer-owned review compares the frozen NSHM PRVI GeoJSON assets with
three paired CSVs and the root FGDC XML. No source bytes are reacquired or repaired.
The XML records access/use constraints as literal `none`; this closes recording
of those fields only. All three native geometries pass format checks. All three
cross-format comparisons fail: SiteID EGQ5 versus EQG5, 15 raw numeric CSV X/Y
versus GeoJSON tuple differences, shortened text, blank/N/A/null differences,
and FS6 CountryTer HIS versus Offshore remain preserved. CSV CRS/axis semantics
are unverified; numeric deltas are not physical distances. Two layers extend
outside the publisher's PRVI bounding box, which is not a PR jurisdiction mask.
The source's migration/no-data-change annotation is a claim, not byte lineage.

The documentary export and isolated consumer rehearsal retain 3 sources and
92 observations. Neither closes scientific staging. The activation matrix retains
all 2,286 files (593 byte PASS, 82 quarantined failures, 1,611 blocked), with zero
production-eligible or activated files. Source consistency, PR jurisdiction,
consumer fitness, units, semantics and current-version lineage block certification.

Use `scripts/certify_usgs_release.py` with `--expected-commit` and a new `--out`
path. It requires the exact clean Git checkout and scoped evidence checksums.
Exit 2 means expected scientific refusal, even when software identity passes.
Exit 0 is not issued by this evidence-limited build. An operational exception
cannot substitute for source adjudication. Full source review is retained in
`registry/usgs/source_review.v1.json`; an initial superseded derived review is
preserved separately. No canonical identity or geometry repair was performed.

## Frozen top-level NSHM review (2026-10-19)

The independent parent/child check covers 14 legacy top-level file references for
root 64a85bf3d34e70357a27ddd5: FGDC XML, three CSV, three GeoJSON, three KML,
two change logs, a README and bibliography. Intersection=14, A_ONLY=0,
B_ONLY=0, union=14, symmetric difference=0. This bounded closure excludes
other releases, services, external links and current-version claims. All original
2,286 inventory assets and their 593/82/1,611 byte states remain unchanged.

KML-to-GeoJSON stable-key intersections are 51/6/35 with zero set differences.
All 92 geometry comparisons fall within 1e-10 raw numeric tolerance (maximum
5e-14), while only 36 comparison objects/topologies are exactly equal. Raw
coordinate text, geometry type/dimensions, schemas, property serialization and
missing-versus-null distinctions remain preserved. Agreement does not choose
canonical authority. The polygons KML's v0 schema versus v1 filename is unresolved.

Four support files narrow prior uncertainty. The README records WGS84 and
44 field definitions, including scientific units, and directs users to CSV for
complete Obsern descriptions. Published definitions are recorded; scientific
value validation remains unresolved. Its X=latitude and Y=longitude labels
conflict with negative-longitude X values and native geometry. No axis swap is
performed. RecurUn versus data RecurUnc remains an unresolved schema alias.
The README allows sites outside the hazard area; this does not establish that
its hazard area is the metadata bbox or a Puerto Rico jurisdiction mask.

The fault changelog retains all 36 rows: 35 keyed matches and one blank-key
Bowin row. No name-based join fills that key. The polygon changelog has six
keyed matches. FS6 Offshore is supported by the change log and KML/GeoJSON,
but CSV HIS remains a conflicting source observation. EGQ5/EQG5 and 15 raw
numeric CSV/geometry differences remain unresolved. The bibliography is
preserved; cited publications were not newly acquired by this bounded review.

The producer's [KML review command](https://github.com/jotaele44/spiderweb-pr/blob/c752506a1d4ddd8e3f26bf9bf9d1e5e86ab4c5ed/scripts/review_usgs_kml.py) is a diagnostic maintenance command
with expected exit 2. It rejects malformed schemas, duplicate IDs/fields,
network links, DTD/entity declarations, nonfinite coordinates and automatic
ring repair. The Hub pins its review bytes and inputs and checks every source
against the frozen inventory. Rehashed fake PASS reports and swapped inputs
remain rejected. The catalog evidence inspector exposes the added summary.
Scientific staging, activation and exact dataset certification remain BLOCKED.
The previous iOS companion CI observation is now PASS at d637786; it does not
certify a new head or physical-device installation. The prior SIGE TLS failure
remains historical evidence, not a new live-provider observation.

## Nested file enumeration correction (2026-10-19)

The 14/14 closure above is explicitly top-level only. A recursive walk of all
463 frozen item JSON responses finds 850 facet-file references and 3,136
distribution-file references beyond the original 2,286 top-level references.
The 6,272 combined observations are not a certified unique-asset count: mirror
relationships require adjudication. 702 files fields are empty strings rather
than arrays; their raw values are retained as UNRESOLVED, never coerced to zero.
All array descriptors and JSON pointers are preserved in the nested inventory;
full metadata/file/payload closure remains OPEN. No nested payload was acquired.
The reviewed NSHM release contributes 16 facet shapefile components and 30
distribution references. SHP availability is not inferred absent from top-level
files. Full dataset activation remains BLOCKED for this independent reason.

The new all-item metadata ZIP preserves exact frozen response bytes, assembled
from the original root snapshot and child evidence archive. Its outer bytes
are a new subset artifact, not a recompression identity claim. The old inventory,
checksums, acquisition failures and 593/82/1,611 byte-state counts are unchanged.
`src/hub/usgs_nested_inventory.py` and `scripts/inventory_usgs_nested.py` implement
the offline reference audit. Duplicate members, wrong requested/returned IDs,
baseline descriptor changes and malformed descriptors fail regression checks.
Repeated descriptors retain separate pointer IDs; they are not deduplicated into
canonical assets. The catalog evidence inspector exposes the corrected scope.

## Controlled facet acquisition (2026-10-28)

The frozen sixteen-component plan remains unchanged: 378,473 declared bytes,
with a 1 MiB response-body cap. The new maintenance command
`scripts/acquire_usgs_facets.py` performs one explicit new snapshot; it does not
refresh earlier passed assets. Every attempt retains its URL, UTC, status,
size, SHA-256, truncation state and source checksum result. A BYTE pass requires
both the source-declared size and checksum. Redirects, timeouts and HTTP errors
remain blocked transport observations, never evidence of source absence.

The local snapshot 20261028-local-01 returned sixteen HTTP 403 observations,
with 343 captured response bytes, zero checksum passes and zero activations.
Its request receipts and bounded response fragments are preserved. The initial
probe used an uncommitted implementation, so its executed-code identity remains
UNRESOLVED; it does not support exact-release certification. Cached revalidation
passes without new requests. Existing observations, including failures, are reused
under the same snapshot ID. Corruption, orphan bodies, missing members of a
completed snapshot and plan changes require recovery or a separately named new
snapshot; they do not silently trigger refetching.

Ordinary PR CI remains offline. A same-repository label event on this draft PR
can trigger the separately scoped controlled-facet-snapshot runner job. The
explicit label is usgs-facet-snapshot-20261028. It checks out the exact PR head,
uses only read permissions and preserves all receipts as an Actions artifact,
including a commit/code-hash execution receipt. Re-running a job attempt cannot
repeat acquisition. A new label event is a new run/snapshot, not a replacement
of prior observations. This control does not close mirror identity, CRS/axis,
source conflicts, consumer fitness or any production activation gate.

At the restored head 3634c894, USGS and GUI checks pass. The broader CI failure
is consumer grid-authority pin drift (0c66e13 versus b8f5cf3), and the October 25
live-provider run still reports four SIGE TLS-chain failures. Those observations
are recorded independently; neither gate is waived by this acquisition work.

The independent runner snapshot 20261028-gh-40683670587 passed all sixteen
source size/checksum checks (378,473 captured bytes). Its exact 36-member ZIP
is frozen at `data/usgs/snapshots/20261028_runner_facets.zip`; its archive hash,
run/artifact IDs, executed commit and code hashes are retained in
`registry/usgs/facet_runner_evidence_20261028.v1.json`. CRC and every archived
body were independently checked. The normal offline readiness assessment now
replays these byte checks against the frozen acquisition plan. Tests reject
self-consistently rehashed changed bodies, wrong identities, missing members,
typed receipt disagreement and attempted promotion. Local HTTP 403 evidence
remains separately preserved. No shapefile semantic adapter or canonical export
is certified by these checks; full nested closure, scientific staging,
activation and exact dataset certification remain BLOCKED, activated=0.
