# Federation Evidence Object v1 (candidate)

TheHub is the canonical owner of three shared contracts:

| Contract | Schema | Runtime |
|---|---|---|
| FEDERATION_EPISTEMIC_STATE_CONTRACT_V1 | `schemas/federation/epistemic_state.v1.schema.json` | `src/hub/epistemic.py` |
| FEDERATION_EVIDENCE_OBJECT_V1 | `schemas/federation/evidence_object.v1.schema.json` | `src/hub/evidence_object.py` |
| FEDERATION_EVIDENCE_LINEAGE_V1 | `schemas/federation/evidence_lineage.v1.schema.json` | `src/hub/evidence_lineage.py` |

**Status: CANDIDATE**, version `1.0.0-candidate.1` in `governance/contract_versions.json`. The
contracts are not pinned in `schemas/FROZEN.sha256`. They are frozen only after all of the
following pass: producer adoption, positive and negative fixtures, GUI parity, and Federation
compatibility (directive §42).

These contracts are shared rules and meanings. They do not require any repository to store
data in a particular table layout (directive §37).

## Axes

Each axis is independent of the others. A missing or invalid value falls back to the axis
sentinel. Every value also carries a `*_basis` string that says why it holds.

| Axis | Values | Sentinel | Who sets it |
|---|---|---|---|
| `data_stage` | RAW, NORMALIZED, CANONICAL, EVIDENCE_CLASSIFICATION, FINDING, COMPUTATION, INTERPRETATION, REPORT | UNKNOWN (CANONICAL for producer stream rows) | Producer declaration; hub correlations are COMPUTATION |
| `epistemic_class` | MEASURED, COMPUTED, CURATED, INTERPRETIVE | UNCLASSIFIED | Producer declaration only; hub correlations are COMPUTED |
| `identity_state` / `identity_scope` | BOUND, CANDIDATE, UNRESOLVED, CONFLICTING / PRODUCER_LOCAL, FEDERATION | UNRESOLVED | Producer declaration, or the hub identity registry (FEDERATION scope) |
| `source_state` | SOURCE_BOUND, SOURCE_REPORTED, SOURCE_MISSING, SOURCE_BLOCKED | — | Hub, from the row's source references and the source record |
| `temporal_state` | LIVE, CURRENT, STALE, HISTORICAL, UNKNOWN | UNKNOWN | Hub, computed at read time |
| `temporal_precision` | EXACT_TIMESTAMP, BOUNDED_INTERVAL, DATE_ONLY, MONTH_YEAR, YEAR_ONLY, APPROXIMATE, UNKNOWN | UNKNOWN | Producer declaration, `date_precision`, or the `date_local` pattern |
| `observation_state` | OBSERVED_PRESENT, OBSERVED_ABSENT, NOT_OBSERVED, UNKNOWN | UNKNOWN | Producer declaration only |
| `geometry_precision` | OBSERVED_POINT, INTERPRETED_POINT, AREA_REFERENCE, REPRESENTATIVE_POINT, UNKNOWN | UNKNOWN | Producer declaration, crosswalked `coordinate_method`, or area-only location |

Notes on individual axes:

- **Identity:** federation IDs never replace producer IDs (ADR 0009).
- **Source state:** SOURCE_BOUND requires the resolved source record to carry a retrievable locator (an http(s) URL, a DOI, or an archive locator) or a SHA-256 content hash. Free-text citations and producer-internal reference ids are SOURCE_REPORTED; the text is shown as citation text, never as a link. A cited source that the Hub cannot resolve is also SOURCE_REPORTED, not SOURCE_MISSING: the Hub index can be partial, so failing to resolve a source does not show the source is missing. In the committed aggregate, 107 of 400 source records are bound (98 OVNIS URLs, 9 AguaYLuz content hashes).
- **Temporal state:** LIVE and STALE require a declared `expected_cadence_seconds`.
- **Temporal precision:** YEAR_ONLY is added to the directive's list so that year-only records are not collapsed into another class.

## Crosswalks

- **`coordinate_method` → `geometry_precision`.** Values come from the Spiderweb
  `federation_spatial_feature_v1` vocabulary:

  | `coordinate_method` | `geometry_precision` |
  |---|---|
  | EXACT, SURVEYED, AUTHORITATIVE | OBSERVED_POINT |
  | GEOCODED_ROOFTOP, GEOCODED_PARCEL, GEOCODED_STREET, INFERRED, INTERPOLATED, LINKED_ASSET | INTERPRETED_POINT |
  | GEOCODED_LOCALITY, DERIVED_CENTROID, DERIVED_AVERAGE, FIRST_VERTEX | REPRESENTATIVE_POINT |

  A bare coordinate pair with no declared method is UNKNOWN. A location that gives only a
  municipality is AREA_REFERENCE.

- **`date_precision` → `temporal_precision`.** day → DATE_ONLY, month → MONTH_YEAR,
  year → YEAR_ONLY, uncertain_range → BOUNDED_INTERVAL. The value is rendered at that
  precision. For example, OVNIS emits `1929-01-01T00:00:00-04:00` for a year-only case, and it
  is shown as `1929`; the padded producer timestamp is kept in `temporal_basis`.

- **Relationship `match_basis` → `edge_state`.** The weak correlation bases
  (`identity_adjudication.WEAK_CORRELATION_BASES`) and the `entity_resolution.v1` forbidden
  reason codes give at most CANDIDATE. A shared external identifier gives COMPUTED, which is
  still not identity. A relationship asserted by a producer is DOCUMENTED only when its source
  is SOURCE_BOUND.

## Invariants

`validate_evidence_object` and `validate_edge` enforce these rules.

**Observation**
- NOT_OBSERVED never becomes OBSERVED_ABSENT.
- OBSERVED_ABSENT requires a declared `observation_absence_basis`.

**Time**
- A value at DATE_ONLY, MONTH_YEAR or YEAR_ONLY precision never carries a time.

**Geometry**
- REPRESENTATIVE_POINT and INTERPRETED_POINT are never promoted.
- A producer that declares OBSERVED_POINT alongside a representative method is refused.
- Repeated coordinates do not change precision.

**Classification**
- INTERPRETIVE requires an interpretation basis.
- `epistemic_class_basis` is NONE exactly when the class is UNCLASSIFIED.

**Lineage**
- A missing source ends the lineage at a SOURCE_MISSING node. No source is invented.
- A DOCUMENTED or COMPUTED edge cannot rest solely on proximity, timing or name similarity.

**Contradictions and data**
- A contradiction keeps both original claims.
- A malformed contradiction is reported, not repaired.
- Synthetic rows stay flagged.
- `confidence` is carried as its own field and never folded into another axis.

## Producer declaration

Producers may attach an additive `evidence_state` object to any row of a federation stream. The
stream schemas already allow additional properties. Every key is optional:

```json
{"evidence_state": {
  "contract": "federation-evidence-state-v1",
  "epistemic_class": "CURATED",
  "observation_state": "OBSERVED_PRESENT",
  "geometry_precision": "AREA_REFERENCE",
  "temporal_precision": "YEAR_ONLY"
}}
```

If a value is invalid or contradicts another value, the Hub ignores it, lists it in
`declaration_errors`, and shows it in the inspector under "Rejected producer declarations".

## Surfaces

- **API:** `GET /api/evidence/{collection}/{record_id}`. `collection` is a Hub store
  collection: `Sources`, `Entities`, `Relationships`, `Observations`, `Alerts` or
  `Correlations`. A record the Hub does not hold returns 404.
- **GUI:** the route `/evidence/:collection/:id`. It is linked from four places, but only
  for rows projected from a canonical producer stream:
  - the producer-workspace Evidence inspector;
  - record sheets;
  - every search result;
  - the entity page ([`SEARCH_AND_ENTITY_V1.md`](SEARCH_AND_ENTITY_V1.md)).

  An entity's Evidence Object links on to its composition at `/entity/:id`.

## Tests

| Test file | Covers |
|---|---|
| `tests/test_epistemic_state.py` | Each axis, positive and negative cases, and schema ↔ Python enum parity |
| `tests/test_evidence_object.py` | All 2258 committed aggregate rows projecting to valid objects, plus negative fixtures |
| `tests/test_evidence_api.py` | The API against a real ingested store, and route ordering |
| `server/frontend/src/lib/evidenceState.test.js` | Frontend evidence-state logic |
| `server/frontend/src/components/evidence/ProvenanceInspector.test.jsx` | Inspector rendering, including axe accessibility checks |
| `server/frontend/tests/visual/gui-parity.spec.js` | Reachability from a producer record, and not-found handling |

## Twin traceability

This contract implements these observed Twin elements:

- TWIN-018: no-fake-data rule
- TWIN-019: the four-class taxonomy
- TWIN-020: colour-coded classes, always shown with text
- TWIN-023: real vs modelled
- TWIN-074: explicit interpretive class

It also implements these Federation-derived extensions: FDX-001–006, FDX-009, FDX-010, FDX-026
(partial) and FDX-074.
