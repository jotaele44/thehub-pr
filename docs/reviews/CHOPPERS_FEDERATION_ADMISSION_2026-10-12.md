# Choppers flight/geography federation admission — pending gate

**State: BLOCKED / NO LIVE ADMISSION CERTIFIED** (2026-10-12)

This is a bounded cross-producer validation specification, not a production integration. Existing producer ownership remains: Skywatcher owns aviation trajectories and evidence; Spiderweb owns spatial reference features; TheHub owns canonical schema admission and cross-producer relationship authority.

## Frozen audit sources
- `Choppers.zip` original source SHA256: `a4de8fe8ddd9f893a2e89306367a4de8fd21bab280c8de0a491c40774fdf0677` (73,065,927 bytes)
- 740 canonical root-log flights + 76 N999ZY tagged raw-point **reconstructions** = 816 indexed leg keys, 368,755 point counts; daily and monthly indexes close.
- The outer archive source manifest is **not complete**: 1,887 payload members unlisted, 34 listed paths missing; this prevents whole-archive certification.
- Nine Spiderweb airport point references taken from `spiderweb-pr/exports/real/observations.jsonl` Git blob `5dfb03703331bd76eca68eb175eb97bc88aefc08`; audit fixture: `spiderweb-pr/exports/reference/choppers_airport_points_audit_v1.geojson`.
- 1,632 flight endpoints compared, 1,009 possible point-radius associations at 3 km. These are NOT confirmed flight-airport relationships.

## Minimum Hub consumer contract
1. **Input isolation:** require frozen producer package IDs, original member manifest, schema versions, reported source byte hashes, and stable flight keys; never ingest `by_day`, `by_month`, KML and raw-point copies as separate flights.
2. **Authority:** retain all Skywatcher flight records and Spiderweb features as separately owned entities; original attributes immutable. Avoid direct repo-to-repo imports.
3. **Spatial link identity:** attach `flight_id`, `feature_id`, endpoint type, relationship metric/threshold, source feature version, calculation version, evidence state, and candidate set; a nearest point is only discovery, not identity.
4. **Geometry:** enforce CRS, legal coordinates, altitude reference semantics, temporal scope, and FULLY_WITHIN/PARTIAL/TOUCH_ONLY/OUTSIDE/NULL_EMPTY/UNRESOLVED as applicable. Point proximity is not an intersection with an airport footprint.
5. **No manufactured count closure:** tests assert source/retained/excluded rows, unique keys, one-to-many join cardinality, unreconciled-source visibility, and namespace collisions.
6. **Client proof:** GUI route, API contract, rendered desktop/mobile execution, accessible evidence provenance, review state, no dead controls, plus CI, frozen hashes and rollback.
7. **Admission:** require live, nonsynthetic, schema-valid Skywatcher and Spiderweb packages independently and an actual validating TheHub consumer test; only then create an admissible cross-producer association export.

## Status matrix
| Gate | State |
| --- | --- |
| Cross-producer scope/authority defined | PASS (architecture only) |
| Flight index accounting | PASS (bounded 816-leg index) |
| Entire source archive manifest consistency | FAIL |
| Geo point reference fixture | AUDIT_ONLY |
| Full geometry/identity adjudication | OPEN |
| Skywatcher live export | BLOCKED (per Skywatcher federation.json at review time) |
| TheHub live ingestion/consumer validation | BLOCKED |
| Native GUI coverage, monitoring, rollback | OPEN |
| Production release | BLOCKED |

No false positive certification or production merge permitted. Once all technical gates close, train and version the ingestion/enrichment skill and agent from the audit trace and golden/negative fixtures.
