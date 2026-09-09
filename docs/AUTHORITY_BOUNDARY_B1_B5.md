# Authority Boundary Closure — B.1 through B.5

**Candidate date:** 2026-09-08
**Certification state:** `NOT_CERTIFIED`
**Successor phase:** `A — FEDERATION IDENTITY CONTRACT` is forbidden until blocker count = 0.

## B.1 — identity authority

- ADR 0009 is superseded.
- ADR 0010 assigns shared spatial identity to the independent logical authority
  `prii-federation-spatial-identity`.
- TheHub is bounded to governance, validation, aggregation and query/client functions.
- The historical `src/hub/identity_registry.py` remains byte-retained only as
  `LEGACY_NONAUTHORITATIVE_TEST_FIXTURE`; a regression gate forbids production imports.

**B.1 candidate state: CLOSED BY SUPERSESSION + ENFORCED QUARANTINE.**

## B.2 — shared geometry

- The 98,304-cell raster-derived PR grid is `NONCANONICAL_LEGACY_IMAGE_SPACE`.
- Ground joins, containment, parcel operations, metric distance and identity use are forbidden.
- Municipio and barrio references are pinned to the frozen AguaYLuz manifestation at
  `3678271a03e36375dc3e9f2fb4da0b6b655622bd` with expected counts 78 / 901.
- Serialized GeoJSON is CRS84 longitude/latitude and source lineage is U.S. Census GENZ2023.

**B.2 candidate state: CLOSED.**

## B.3 — identifier namespaces

The original prefix-assignment census was not sufficient: it could miss IDs emitted from
f-strings, tuple-driven layer maps, JSON/JSONL records and workflow constructors. The candidate
now adds `scripts/identifier_namespace_census.py` and upgrades the canonical CLI receipt to
`authority_boundary_validation_v3`.

The structured denominator is intentionally bounded to identifier construction and emitted
fields rather than arbitrary taxonomy labels:

- explicit `*_ID_PREFIX` / `uid_prefix` / `visual_id_prefix` constructors;
- structured literal fields ending in `_id`;
- Python assignments and dictionary outputs ending in `_id`;
- deterministic ID-constructor calls;
- tuple/map prefix families used by an ID constructor;
- seven frozen repository trees, excluding tests, docs, fixtures, build products and reports.

Newly surfaced families were reconciled without collapsing producer-local identities into shared
federation IDs. In addition to the previously registered families, the registry now explicitly
covers:

- AguaYLuz `PMP_`, `RSV_`, `OSMS_`, `OSML_`, `EIA_PLANT_`, `EIA_UTIL_` and imported `PWR*`;
- OVNIS `CAND-` intake IDs and `assess_` federal/military review assessments;
- the already proven WTR/WWT/OSMP/HIFLD, PRUFON/PRUAP, SATIM, Spiderweb and Centinelas families.

The registry is now marked `EXHAUSTIVE_CRAWLER_RECONCILED`, but that declaration is not itself a
certification: `scripts/validate_authority_boundary.py` executes the structured crawler on all
seven exact checkouts and re-opens B.3 on any unknown family, ambiguous match, owner mismatch,
unresolved ID expression or census-denominator failure.

**B.3 candidate source state: RECONCILED; EXECUTABLE RECEIPT STILL REQUIRED.**

## B.4 — relationship authority

`registry/federation/relationship_types.json` separates shared identity relationships from
producer-domain semantics and pins literal-bearing sources to exact blobs.

The exact seven-repository local crawl reconciles 25 unique literals across 45
repository/literal observations with zero unknown, ambiguous, owner-mismatch, cross-producer,
source-pin or Python-parse blockers. `duplicate_of`, `located_in` and `reported_by` are centrally
shared because multiple producers emit them; Hub correlation types remain non-identity
candidates.

**B.4 candidate state: CLOSED BY EXACT LOCAL CRAWL + PINNED SOURCE VERIFICATION.**

## B.5 — source/duplicate/producer-consumer census and arithmetic

- `registry/federation/repository_snapshots.json` freezes the seven-repository denominator and
  exact baseline commits.
- `registry/federation/authority_boundary_census.json` freezes producer/consumer edges,
  duplicated source families, SHARED vs DOMAIN authority classes, and static arithmetic.
- `.github/workflows/authority-boundary-certification.yml` checks out all six peer revisions next
  to the candidate TheHub checkout and invokes `scripts/validate_authority_boundary.py`.

The machine receipt is `reports/authority_boundary_validation.json`. Only an actually executed
receipt with `blocker_count = 0` may emit `AUTHORITY_BOUNDARY_CERTIFIED` and unlock Phase A.

## Current material residue

The latest candidate-triggered Authority Boundary workflow, run `34293153449`, was admitted as a
failed job but again exposed no executable steps (`steps = null`). The crawler therefore did not
run on GitHub-hosted infrastructure and no zero-blocker machine receipt was produced.

This is consistent with the previously recorded account-level GitHub Actions admission/billing
blocker. Source reconciliation cannot be substituted for an execution receipt.

Therefore:

- `AB-001`: CLOSED
- `AB-002`: CLOSED
- `AB-003`: SOURCE RECONCILED / RUNTIME RECEIPT BLOCKED
- `AB-004`: CLOSED
- `AB-005`: CLOSED
- static B.5 arithmetic: 7/7 repositories, 6/6 producers
- `B-RUNTIME-RECEIPT`: BLOCKED_EXTERNAL

`AUTHORITY_BOUNDARY_CERTIFIED` is **not issued** and Phase A remains locked until the exact
seven-tree validator actually executes and returns `blocker_count = 0`.
