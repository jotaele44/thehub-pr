# Federation Local Persistence Protocol v1

Status: PROVISIONAL / NONCANONICAL until repository-by-repository adoption and tests pass.

## Purpose

Define shared migration, backup, receipt, and integrity semantics across fed apps without creating a universal database authority.

## Non-goals

- This protocol does not create `federation.sqlite`.
- TheHub does not become universal row-level data authority.
- SQLite engine equivalence does not establish table/entity identity across apps.
- Server-owned collaborative/runtime state remains server-owned where required.

## Required separation

Each app declares its own authority map:

`LOCAL_DEVICE | DOMAIN_PRODUCER | REMOTE_SHARED | DERIVED_CACHE | NONCANONICAL_DONOR`

A record may move between authorities only through an explicit migration/admission receipt. Name, normalized name, count equality, nearest/proximity, or category equality cannot establish record identity.

## Common migration contract

Every schema migration must include:

- `migration_id` — stable unique identifier;
- `from_version` and `to_version`;
- stable migration name;
- migration artifact SHA-256;
- UTC application timestamp;
- application/build version;
- source database manifestation identifier;
- pre-migration schema hash;
- post-migration schema hash;
- pre/post required-table counts;
- PASS/FAIL state;
- failure reason when not PASS.

Migrations must be deterministic, ordered, restartable, and fail closed. Failed migration may not silently advance the schema version.

## Import/admission receipt

Every externally sourced corpus/database import must record:

- source artifact name;
- source URL/service/revision where applicable;
- retrieval UTC;
- source artifact SHA-256;
- parser/importer version;
- raw row/member count;
- retained count;
- excluded count;
- unresolved count;
- canonical row count when normalization/canonicalization occurs;
- duplicate stable-ID count;
- source schema hash;
- target schema version;
- active generation identifier;
- receipt state.

Arithmetic gate:

`RAW = RETAINED + EXCLUDED + UNRESOLVED`

Any unexplained mismatch is FAIL.

## Generation activation

A new local generation remains `CANDIDATE` until:

1. every declared member/chunk exists;
2. member SHA-256 matches the manifest;
3. required IDs validate and declared uniqueness scopes pass;
4. indexes reference the same generation;
5. row/member arithmetic closes;
6. required schema/integrity tests pass;
7. activation is committed atomically.

On failure, the prior active generation remains authoritative and usable.

## Backup package contract

Recommended logical package:

```text
backup/
  manifest.json
  database.sqlite        # only when the app owns a local DB
  attachments/
  source_manifests/
  hashes.json
```

`manifest.json` must include:

- app/repository identity;
- app version/build;
- schema version;
- export UTC;
- declared authority scope;
- database SHA-256 when present;
- attachment count + hashes;
- source-manifest hashes;
- per-required-table row counts;
- stable-ID uniqueness result;
- format/protocol version.

## Restore gate

Restore must validate all declared hashes and schema compatibility before replacement. Restore is atomic. A failed restore leaves the previous active local state intact.

Post-restore invariants:

- required table counts equal manifest counts;
- required stable IDs are present and unique in the declared scope;
- attachment bytes hash correctly;
- active generation matches the restored manifest;
- no server/domain producer authority is overwritten by a device-local backup unless explicitly allowed by that repository's authority map.

## Attachment storage

Large binary source/evidence artifacts should normally remain outside relational tables. Store content-addressed or otherwise immutable file bytes with relational metadata containing SHA-256, MIME type, provenance, and authority scope.

## Synchronization

Synchronization is repository-specific. Shared semantics are limited to:

- durable record ID;
- revision/version;
- origin authority/device where applicable;
- update timestamp;
- deletion/tombstone state where applicable;
- explicit conflict state;
- no silent last-write-wins where conflict could change evidence, identity, geometry, or canonical research state.

## Certification states

`PASS | FAIL | OPEN | BLOCKED | PROVISIONAL | NONCANONICAL | UNRESOLVED | SUPERSEDED`

A successful migration script is not certification.

## Required negative regressions

At minimum, each adopting repo should test:

- duplicate stable ID;
- missing manifest member;
- member hash mismatch;
- row-count mismatch;
- interrupted migration;
- interrupted import before activation;
- incompatible backup schema;
- corrupted backup/member hash;
- restore failure leaves old state unchanged;
- mobile-local import cannot overwrite producer authority;
- network/Floot unavailable during local-only operations.

## Initial adoption order

1. Skywatcher pilot
2. MoneySweep
3. OVNIS
4. Spiderweb
5. AguaYLuz
6. Centinelas bounded local-review client while retaining remote collector authority
7. TheHub federation of completed module contracts
8. Corillo only after canonical root architecture exists
