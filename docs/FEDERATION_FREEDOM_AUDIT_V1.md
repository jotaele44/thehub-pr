# Federation Cost and Dependency Freedom Audit v1

## Status

- **Snapshot:** `FEDERATION_FREEDOM_STATIC_SNAPSHOT_2026-09-04`
- **Contract:** `FEDERATION_FREEDOM_CONTRACT_v1`
- **Mode:** `STATIC_PRIORITY_DENOMINATOR`
- **Certification:** `FAIL` for the bounded snapshot; no repository is certified.
- **Reason:** confirmed static blockers remain and all eight dynamic gates are unexecuted.

This audit separates four claims that must never be collapsed:

1. `COST_FREE`
2. `SERVICE_INDEPENDENT`
3. `SELF_CONTAINED_RELEASE`
4. `OFFLINE_REPRODUCIBLE_BUILD`

A free-tier hosted service is not service independence. A bundled open-source library is not an
external runtime service. Lockfiles, checksums, SBOMs, license notices, and raw evidence bytes are
preserved.

## Frozen repository denominator

| Repository | Commit | Tree |
|---|---|---|
| `aguayluz-pr` | `3678271a03e36375dc3e9f2fb4da0b6b655622bd` | `7bed39d09f7571ad4fdd78b18c02c61e944ed454` |
| `centinelas-pr` | `caf086598a4f99e2eb0ca4aac6d51e2d9bd46321` | `3c73861bbaeab06c6e3587447037269bb92360e0` |
| `moneysweep-pr` | `74b10245f925bfd9b9ea07b2ce986981d5d65525` | `4bb19ec43c5a3f37508d7fe0e325e93cdf43c33d` |
| `ovnis-pr` | `af066815759fcf479ee79eeeb921c2809a1a20a4` | `ff49216d2dbd569feda8d551a3b597bc707ffaa1` |
| `skywatcher-pr` | `6b95f816f1dc2c2081734df582920703743fbdf3` | `72d38523436040815103d9d9502be3b23bb1b292` |
| `spiderweb-pr` | `f46546ef24c7dc2164b3f203d1af57e7d2570219` | `5e15d00e7346ef61e39401498de5426e8c17ed49` |
| `thehub-pr` | `6474028904af463cab513d1755bce0380f7b2ad1` | `e69df351b38bc447cb5057669352279be737065a` |

Earlier mutable-head observations are superseded. Findings bind to the commit/tree pairs above.

## Four-axis static disposition

`PROVISIONAL` means no blocker was established by this bounded static vector; it is not a pass.
`OPEN` means a candidate requires dynamic or scope adjudication. `FAIL` means a confirmed blocker
exists inside the stated axis.

| Repository | COST_FREE | SERVICE_INDEPENDENT | SELF_CONTAINED_RELEASE | OFFLINE_REPRODUCIBLE_BUILD |
|---|---:|---:|---:|---:|
| `aguayluz-pr` | **FAIL** | **FAIL** | **FAIL** | **FAIL** |
| `centinelas-pr` | **FAIL** | **FAIL** | OPEN | **FAIL** |
| `moneysweep-pr` | PROVISIONAL | **FAIL** | OPEN | **FAIL** |
| `ovnis-pr` | PROVISIONAL | **FAIL** | OPEN | **FAIL** |
| `skywatcher-pr` | PROVISIONAL | **FAIL** | **FAIL** | **FAIL** |
| `spiderweb-pr` | PROVISIONAL | **FAIL** | **FAIL** | **FAIL** |
| `thehub-pr` | PROVISIONAL | **FAIL** | OPEN | **FAIL** |

## Confirmed blocker ledger

### Federation-wide

1. Five frontends resolve `@pr-federation/react` from GitHub release tarballs rather than a local
   workspace or retained offline package.
2. Six producer repositories resolve shared Python packages from a remote TheHub Git/archive source.
3. No approved offline dependency-byte manifest was identified for any of the seven repositories.
4. GitHub `repository_dispatch` is used as operational federation transport. It must become an
   optional bridge over a local artifact outbox/inbox authority.
5. CI and hosted deployment remain conveniences only. They cannot serve as evidence of an offline
   build path.

### `aguayluz-pr`

- Remove Sentry tracing/session replay and retain a local structured error ledger.
- Replace the Anthropic-backed `/ai/query` route with deterministic local status synthesis.
- Register OSM and Esri basemaps as optional data connectors with cache policy and a neutral offline
  background.
- Vendor/checksum the shared frontend and Python packages for disconnected builds.

### `centinelas-pr`

- Move `anthropic` from the core dependency plane to an optional adapter.
- Make the keyword classifier the local default and lazy-import any optional model adapter.
- Remove default workflow injection of `ANTHROPIC_API_KEY`.
- Make local outbox/inbox artifacts authoritative; keep GitHub dispatch only as an optional bridge.

### `moneysweep-pr`

- Separate `pytest` and `pytest-cov` from the runtime dependency plane.
- Vendor/checksum the shared frontend and Python packages.
- Replace GitHub event transport as the authoritative federation handoff.
- Preserve downloaded source snapshots exactly; remote URLs inside raw evidence are not application
  dependencies and must not be rewritten.

### `ovnis-pr`

- Move `pytest` and `pytest-cov` from runtime requirements to the development/test plane.
- Register the OSM basemap as an optional data connector with an offline fallback.
- Vendor/checksum shared frontend and Python packages.
- Replace GitHub event transport as the authoritative federation handoff.

### `skywatcher-pr`

- Bundle Leaflet and Vis Network used by generated HTML instead of loading them from `unpkg.com`.
- Bundle/checksum Tesseract for the declared FR24 release profile or exclude FR24 from the certified
  self-contained core.
- Register OSM tiles as an optional connector with an offline map fallback.
- Vendor/checksum shared frontend and Python packages and make GitHub handoffs optional.

### `spiderweb-pr`

- Replace every direct `"latest"` frontend specification with the exact lock-resolved version.
- Replace `INSTALL spatial` with loading a locally retained, checksum-bound DuckDB spatial extension.
- Preserve the mature local scientific/GIS stack; do not rewrite Shapely, GeoPandas, Rasterio,
  DuckDB, or related libraries merely because they are third-party.
- Make missing copied Cesium assets a release-build failure instead of silently skipping them.
- Vendor/checksum shared Python packages and dependency archives.

### `thehub-pr`

- Retain the local `file:` binding for the shared React package as the reference implementation.
- Replace `repository_dispatch` as the authoritative ingest/synchronization transport with a local
  artifact exchange contract.
- Produce a provider-neutral build and an offline dependency-byte bundle for the Hub, audit tool,
  frontend, desktop host, and server profiles.

## Data-access exemption boundary

A network path qualifies only when it acquires evidence or geographic/source data and is:

- declared in the connector registry;
- isolated from application startup;
- independently disableable;
- bounded by timeout, retry, pagination, and failure-state controls;
- backed by raw local caching or manual import where technically possible;
- incapable of converting failure into an apparently valid empty result.

Anthropic, Sentry, Slack, ntfy, GitHub repository dispatch, remote executable CDNs, package registries
at runtime, and extension download services are not data-access exemptions.

## Dynamic gates still required

1. Clean-cache installation for every supported target.
2. Startup with all network denied.
3. Connector execution with only registered data hosts allowed.
4. Startup and core operation with all secrets removed.
5. Packaged-release DNS and socket capture.
6. Postinstall/native binary and extension download capture.
7. Offline browse, map, analyze, filter, report, and export.
8. Rebuild from frozen source plus locally retained dependency bytes.

Static scan success cannot close these gates.

## Arithmetic and certification rule

The scanner must preserve every whole-row finding and assert:

- discovered findings = classified findings;
- repository finding totals = federation total;
- seven declared repositories = present + missing;
- exact commit bindings have no unexplained mismatch;
- raw evidence exclusions are counted and preserved;
- every dynamic gate has an explicit state.

A repository remains `FAIL`, `OPEN`, or `PROVISIONAL` until its exact-head static blockers are removed,
all dynamic gates run, and unresolved residue inside the certification scope is zero.
