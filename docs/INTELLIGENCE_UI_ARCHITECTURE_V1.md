# PRII Intelligence UI Architecture v1

## Decision

Use the bounded Monitor the Situation reference as an **interaction-class control**, not as a visual or semantic template. The canonical implementation surface is `thehub-pr/server/frontend`. Producer repositories remain independent engines with independent ontologies and diagnostic-only dashboards, consistent with ADR 0001.

This increment wires Spiderweb, Skywatcher and AguaYLuz through one Hub-side workspace component and three explicit domain adapters. It does not alter producer schemas, producer exports, federation identity authority, or producer runtime behavior.

## Pattern-set computation

### INTERSECTION

Patterns independently justified by both the external reference and PRII requirements:

- left-side feed / result queue;
- central geospatial workspace;
- selected-record inspector;
- global text search over the current domain collection;
- category/layer filtering;
- bounded temporal views;
- explicit status/freshness presentation;
- map-marker ↔ selected-record binding;
- evidence/source context adjacent to the selected record;
- compact cards for scanning many spatial records.

### OUR_ONLY

PRII requirements that must remain stronger than the external reference:

- separate `IDENTITY`, `CERTIFICATION`, `EPISTEMIC`, `CONFIDENCE`, `PROVENANCE`, and `FRESHNESS` axes;
- fail-closed defaults: missing identity → `UNRESOLVED`, missing certification → `OPEN`, missing epistemic class → `UNKNOWN`;
- contradictions preserved explicitly rather than collapsed;
- source manifestations displayed independently from canonical entity identity;
- query recency never presented as source freshness;
- relation/correlation rows never promoted to identity by proximity, time, name, category or count;
- exact loaded-row denominator accounting (`LOADED = VISIBLE + EXCLUDED`);
- explicit undated handling rather than silent temporal loss;
- producer domain ownership and Hub cross-producer authority remain separate;
- bounded-source claims and frozen reference provenance;
- legacy ledger/map/editor tabs preserved during migration;
- error state explicitly blocks certification.

### MONITOR_ONLY

Observed/reference-specific patterns not imported as PRII semantics:

- LIVE versus REPORTS editorial split;
- S1–S5 event-severity model;
- Watch Zone product behavior;
- 3D Globe and Monitor Mode as product-specific view modes;
- VIP aircraft, ships, markets, live TV and other Monitor-specific overlay inventory;
- Monitor-specific event clustering and confidence behavior;
- branding, exact dark palette, layout dimensions, typography, tutorial copy and interaction styling.

### UNION

`UNION = INTERSECTION ∪ OUR_ONLY ∪ MONITOR_ONLY`.

The union is an inventory only. Membership in the union does not authorize implementation.

### SYMMETRIC_DIFFERENCE

`SYMMETRIC_DIFFERENCE = OUR_ONLY ∪ MONITOR_ONLY`.

The symmetric difference is intentionally large: PRII adds forensic/certification semantics while Monitor has product-specific global-OSINT features. Therefore proposed product equivalence is **rejected**. Only the `INTERSECTION` interaction classes are candidates for shared implementation.

## Shared component contract

`IntelligenceWorkspace` owns presentation and interaction state only:

```text
Toolbar
  Search
  Category
  Time range
  temporal-policy disclosure

Loaded-row denominator
  Loaded
  Visible
  Excluded
  Undated

Workspace
  Feed
  Map
  Evidence inspector

Inspector
  Independent analytical states
  Record fields
  Provenance + explicit freshness
  Contradictions
  Related records + anti-identity disclaimer
```

It receives all domain meaning through an adapter. It must not inspect domain type names to change logic.

## Domain adapters

### Spiderweb

- primary collection: `GraphNodes`
- related collection: `GraphEdges`
- domain meaning: spatial graph/context
- event-time policy: retain undated nodes in bounded windows because the current Hub node contract has no authoritative event-time field
- identity rule: graph edges are relationships, not identity proof

### Skywatcher

- primary collection: `AirspaceEvents`
- related collection: `CorrelationReviews`
- domain meaning: airspace/aircraft events
- event-time policy: bounded windows require explicit `event_date`; undated events are counted and excluded
- identity rule: temporal/spatial/source correlation remains correlation evidence, not identity proof

### AguaYLuz

- primary collection: `InfrastructureAssets`
- related collection: `ContinuityRisks`
- domain meaning: persistent water/power infrastructure
- event-time policy: persistent assets without an authoritative event-time field remain visible in bounded windows
- identity rule: continuity-risk/dependency adjacency does not merge asset manifestations

## State-axis rules

The workspace deliberately does **not** derive forensic axes from existing generic status or confidence fields.

| Axis | Explicit source | Missing-field fallback |
|---|---|---|
| Identity | `identity_state` / `identity_status` / `identity_class` | `UNRESOLVED` |
| Certification | `certification_state` / `certification_status` | `OPEN` |
| Epistemic | `epistemic_class` / `epistemic_state` | `UNKNOWN` |
| Confidence | existing domain `confidence` where present | design-system `unknown` |
| Provenance | explicit provenance state + source manifestations | `missing` |
| Freshness | explicit source freshness only | `unknown` |

The app-local forensic badge is intentionally presentation-neutral while the federation design-system forensic semantic extension remains an independent, unmerged change. When that package contract is stable, the local badge can be replaced without changing adapter semantics.

## Temporal invariants

- `All` never removes a row because of missing time.
- A bounded Skywatcher window excludes undated airspace events and counts the exclusion.
- A bounded Spiderweb/AguaYLuz window retains undated persistent/spatial rows and discloses that policy.
- Future-dated rows are counted; in bounded windows they are excluded rather than interpreted as current observations.
- Unknown time-window identifiers throw instead of silently broadening scope.

## Denominator invariant

For every filter pass:

```text
LOADED_ROWS = VISIBLE_ROWS + EXCLUDED_ROWS
```

`LOADED_ROWS` is explicitly bounded to the Hub entity query and must never be labeled as the complete upstream/source universe. Current `useEntityData` collection reads are capped by the Hub client; therefore workspace arithmetic certifies only the loaded slice.

## Accessibility and responsive gates

New controls must:

- have explicit accessible names;
- maintain at least 44px interactive height;
- wrap rather than force horizontal toolbar overflow;
- keep state meaning in text, never color alone;
- stack feed/map/inspector below the desktop breakpoint;
- keep keyboard-visible focus treatment;
- avoid assuming pointer interaction for selection.

## Regression gates

### Positive

- all three adapters are present and bind unique primary/related collections;
- loaded-row arithmetic closes;
- search/category filters retain whole rows rather than synthesize records;
- map marker selection updates the shared selected record;
- Spiderweb and AguaYLuz retain undated persistent context under bounded windows;
- explicit forensic state survives unchanged.

### Negative / fail-closed

- missing identity cannot display a positive identity claim;
- missing certification cannot display `PASS`;
- missing epistemic class cannot display `FACT`;
- Skywatcher undated rows cannot leak into bounded event-time windows;
- an unknown time-window identifier fails instead of expanding scope;
- query refresh time cannot become source freshness;
- graph edges/correlation reviews/continuity risks cannot establish identity through the UI adapter;
- failed Hub collection reads display an incomplete-data alert and cannot be called certified.

## Migration boundary

Existing domain tabs remain intact. `Workspace` becomes the default tab but legacy ledgers, maps, feeds, alerts and review editors remain available. This makes the increment additive and rollback-safe.

## Known open dependencies

- Monitor tutorial steps 9–11 remain `UNKNOWN` under the bounded external-reference audit. They are not required to justify the implemented intersection patterns.
- The federation forensic semantic-axis package work remains separate until its own branch/CI/merge gates are resolved; this implementation must not silently absorb or supersede that draft.
- The existing federation GIS workspace candidate remains an independent renderer-neutral design vector. This Hub implementation uses the Hub's current Leaflet map surface and does not force Leaflet on producer dashboards.

## Certification state

Implementation presence is not certification. Promotion from `PROVISIONAL` requires frontend lint, typecheck, unit tests, production build and browser regression gates on the exact branch head, followed by review of any CI failures and visual/a11y residue.
