# Floot Vector C execution audit — 2026-09-13

Status: AUDIT_ONLY. Bounded byte checks PASS; federation migration, independent backup, native execution and retirement remain OPEN/BLOCKED.

This is an execution observation ledger, not a producer dataset, a database dump, a native-test certificate or release authorization. No main branch was modified, no PR merged and no Floot project unpublished/deleted in this run. Existing fed authority remains above the historical donor.

## A. Archive denominator correction

Frozen source bundle: floot_archive_member_manifests_2026-09-12.zip
Bundle bytes: 227707
Bundle SHA256: 7c68d691e4f826200afb1d1650aa780da4e8a7910dea924b7c08924c48e338fe

The eight original ZIPs were reread locally. Every file member was compared with the frozen manifest using PATH + UNCOMPRESSED_SIZE + SHA256 and a multiplicity-preserving comparison. Directory entries were counted separately. Each supplied gzip manifestation decompresses to its exact supplied JSON bytes. No source strings were normalized.

| Repository | ZIP entries | Directories | File members |
|---|---:|---:|---:|
| skywatcher-pr | 261 | 8 | 253 |
| moneysweep-pr | 231 | 8 | 223 |
| ovnis-pr | 328 | 22 | 306 |
| spiderweb-pr | 288 | 16 | 272 |
| aguayluz-pr | 432 | 24 | 408 |
| centinelas-pr | 250 | 6 | 244 |
| thehub-pr | 326 | 12 | 314 |
| Corillo-Finder | 291 | 10 | 281 |
| TOTAL | 2407 | 106 | 2301 |

COMPUTED: 2407 = 106 + 2301. The previous aggregate 2202 is SUPERSEDED; the arithmetic error was 99 files. The per-archive file counts above were not changed by this aggregate correction.

Archive-identified member tuples: INTERSECTION=2301; A_ONLY=0; B_ONLY=0; UNION=2301; SYMMETRIC_DIFFERENCE=0. Duplicate file paths within each archive: zero. This establishes bounded manifest equivalence, not full GitHub source import, live database recovery or canonical record identity.

Full-manifest publication to OVNIS, Spiderweb, AguaYLuz, Centinelas and TheHub remains OPEN. A ledger or digest reference is not a substitute for the complete manifest bytes. Previous Skywatcher/MoneySweep publication passes are carried forward without implying publication of the other five.

## B. MoneySweep independent pinned-byte rehash

Repository: jotaele44/moneysweep-pr
Exact upstream commit: fca326476f9811553888c4cc02a1fff20cc303fe
Retrieval UTC: 2026-09-13T11:19:33.871Z
Transport: exact raw.githubusercontent.com commit URLs, fetched from an authorized Floot compute VM after local raw transport failed. This did not change project source or provision a database.

All 19 donor-declared objects returned HTTP 200. For every object, raw SHA256, computed Git blob SHA1 and byte count matched the donor's frozen expectations. The Git digest was recomputed over the blob header plus raw bytes, not copied from response metadata.

| Path | Bytes | Parsed CSV data rows |
|---|---:|---:|
| data/canonical_v1/contracts.csv | 1456 | 3 |
| data/canonical_v1/entities.csv | 7251 | 30 |
| data/canonical_v1/edges.csv | 14995 | 66 |
| data/canonical_v1/municipalities.csv | 13108 | 78 |
| data/canonical_v1/debt_instruments.csv | 5708 | 20 |
| data/canonical_v1/evidence.csv | 73347 | 260 |
| data/canonical_v1/funding_sources.csv | 820 | 4 |
| data/canonical_v1/people.csv | 10469 | 60 |
| data/canonical_v1/projects.csv | 2712 | 8 |
| data/canonical_v1/properties.csv | 1374 | 4 |
| reports/current_status.json | 8948 | not applicable |
| reports/materialization_readiness.json | 1038 | not applicable |
| reports/source_registry_status.csv | 51800 | 164 |
| .federation/admin-boundary.json | 318 | not applicable |
| .federation/gui-capabilities.json | 69650 | not applicable |
| .federation/gui-capabilities.extensions/desktop-data-materialization.json | 2764 | not applicable |
| .federation/gui-capabilities.extensions/ownership-deep-dive-v1.json | 2332 | not applicable |
| data/derived/government_organization_change_events.json | 74 | not applicable |
| data/staging/processed/government_organization_change_candidates.json | 136 | not applicable |

COMPUTED: SHA256/size/Git-blob checks PASS 19/19; failures=0; total bytes=268300. Eleven CSVs contain 697 data rows, including 533 in the ten canonical_v1 files and 164 registry-status rows. All eleven passed row-width, duplicate-header, blank-first-column and duplicate-first-column checks. All eight JSON objects parsed. These checks do not establish cross-table referential integrity or certify current producer truth.

Exact bytes and rehash-receipt.json were retained under a commit-specific directory in the VM. Off-Floot local/mobile package generation was not completed. The previous independent-SHA256 OPEN state is SUPERSEDED by this bounded 19-object PASS, not by a general application certificate.

## C. OVNIS historical asset recovery

Floot project ID: 7fe42a06-1945-4b5b-ba78-55418ad90fbc
Initial retrieval UTC: 2026-09-13T11:18:35.103Z
Source keys: public/static/<filename>

| Filename | Bytes | Computed SHA256 matching frozen expectation |
|---|---:|---|
| g03_legales_municipios_2023-4849c09b86ffd58e.zip | 3173521 | 4849c09b86ffd58e4e9e5beeda75510469d8f2b9e9c0be01c991bd586c55907c |
| municipios-2023-derived-wgs84.geojson | 17190798 | 25687f067d469609392e9761aa183cfe81d791026a5c10c4ec5b933b1e492b02 |
| municipios-2023-visual-10m.geojson | 1762668 | b50b9c227dfd5562b7a3bd85309d5802d80d6ad16546f27e452eba5cfa49e691 |
| boundary-topology-comparison-v2.json | 14638 | c89b584eca52e7aa38fae2151b946f03c94ccb430f244256bd7a6be1e1c172ed |

COMPUTED: exact-byte recovery PASS 4/4; total bytes=22141625. Both GeoJSON files contain 78 features with Polygon/MultiPolygon types. No geometry was regenerated and no fresh topological certification is asserted. The source ZIP, analytical derivative, display-only simplified derivative and historical comparison receipt retain separate roles.

All four files were retained in the VM and subsequently reread with identical hashes without redownloading. A VM copy on the service being retired is NOT an independent off-Floot backup. Durable independent transfer and restore verification remain OPEN. Current-default-branch search absence did not prove these historical assets nonexistent.

Observed public storage tree: public/ -> public/static/, fourteen files and no further folders in that listing. Only the four assets above were hashed in this bounded recovery. The ten other listed assets remain outside its hash-completion claim. The private/ listing returned no files or folders; that is not proof of absence from all database or browser storage.

## D. OVNIS live database inventory, not a dump

Read-only table discovery returned 31 public base tables. One UNION ALL count statement returned all 31 table counts without truncation at database statement timestamp 2026-09-13 11:29:05.099514+00.

| Nonempty table | Rows |
|---|---:|
| ovnis_cases | 470 |
| ovnis_artifacts | 244 |
| ovnis_artifact_manifestations | 244 |
| ovnis_artifact_case_links | 470 |
| ovnis_snapshots | 1 |
| ovnis_source_registry | 14 |
| ovnis_source_registry_snapshots | 14 |

Seven nonempty tables plus twenty-four empty tables close the observed 31-table denominator. Summed table rows=1457; this is NOT 1457 distinct cases, entities or independent evidentiary records. No row-content database dump, independent restore or browser IndexedDB recovery was completed in this inventory. Source ZIPs and schemas cannot stand in for these surviving database rows.

Floot published-state readback reported OVNIS still published. No unpublish, deletion, secret change or billing action was performed.

## E. Skywatcher native execution blocker

PR: jotaele44/skywatcher-pr#273
Head: 1230bd0bbb906a408eb1bab2f0efe9c1647f4165
Base: 867e85ae4bb6ba43b81b9ee3ee7c240fd5aa5a8f
PR readback: open, draft, not merged.
Workflow: iOS Native Analyzer
Run ID: 34721912927
Job/check ID: 103629256769
Observation UTC: 2026-09-13T11:30:16.214Z

GitHub job annotation: "The job was not started because your account is locked due to a billing issue."

The job returned runner_id=0, runner_name="", steps=[]. GitHub's conclusion is failure; the cause classification is BLOCKED_ACCOUNT_BILLING. Compile, tests, analyzer, archive and runtime certification remain UNEXECUTED/UNKNOWN, not code PASS or a demonstrated code defect. The annotation endpoint required a public HTTP fallback because GitHub.fetch rejected its URL; both annotation and job returned HTTP 200 through that fallback.

Source URLs:
- https://api.github.com/repos/jotaele44/skywatcher-pr/check-runs/103629256769/annotations
- https://api.github.com/repos/jotaele44/skywatcher-pr/actions/jobs/103629256769

No iOS certification until cold-launch, persistence, migration, rollback, backup/restore and Floot-unreachable executions pass on the exact assessed head. Account access repair is separate from code modification; no billing change or futile repeated rerun was initiated.

## F. Corillo current-repository evidence supersedes empty-repository assumption

Repository stable ID: 1350177598
Repository: jotaele44/Corillo-Finder
PR #1: open, draft, not merged.
Base: 92ff3c458fc25e47a2abe3d4ce8b4b893b50dddf
Head branch: archive/corillo-finder-gui-2026-09-12
Head: 601d22175d564f25ba87404bd76798d8a950ff2a

The earlier empty-repository/initialization blocker is SUPERSEDED. The repository and its staged controls already exist. PR #1 explicitly reports full source import and GitHub member conservation BLOCKED, plus dependency-bootstrap DNS failures. Do not initialize another main or count governance additions as the 281 archive-member import. This run made no Corillo mutation.

## G. Rejected Centinelas transport and preserved baseline

Target archive branch: archive/floot-export-2026-09-12
Pre-write head: 22cab206b3518a4de8ff292d0fcbf2dd8b70b502
Failed write commit: 46718b196a8e2c31896dc6ec7da2907cb82d3d29
Rejected path: archives/floot-2026-09-12/archive-members.full.json.gz.b64
Expected transfer bytes: 15993
Expected Git blob SHA1: 817afe1a3fb53856db454748f6b4d6d90800e543
Observed transfer bytes: 15991
Observed Git blob SHA1: f4eaa01e391c249b5838bd19d921171ba5ef7803
Removal commit: 05f5fce989e65be1b87020c6949cdc89260f08d2

The manually transferred opaque payload failed byte readback and was removed. GitHub comparison of pre-write head against removal commit returned files=[] and ahead_by=2: no net file differences, while both event commits remain in history. FAILED_TRANSPORT is not a successful manifest publication. The validated local source bundle was unchanged.

Required hardening: derive encoded payloads programmatically from frozen files and verify returned blob identity plus decoded readback before any branch-reference publication. Do not send another long opaque manifest through manual model transcription.

## Retirement decision

FLOOT_RETIREMENT=BLOCKED_PENDING_PRESERVATION_AND_EXECUTION.

Every project's applicable database, asset, browser workspace, authentication, producer/server dependency and deployed-client scope must receive explicit disposition. Unexamined scopes cannot pass vacuously. A service-local hash receipt cannot authorize destruction of its only surviving payload. Code success does not supply release or merge authorization. No recovery claim is universal; only the explicit denominators above are closed.
