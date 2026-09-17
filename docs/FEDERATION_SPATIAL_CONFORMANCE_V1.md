# Federation Spatial Conformance v1

## Status

`PROVISIONAL / OPEN`

This specification preserves deliberate spatial asymmetry across the PRII federation. It is not a GIS ranking and does not require every repository to implement the same spatial functions.

## Authority boundaries

- `spiderweb-pr` — federation authority for generic geometry semantics and cross-domain spatial evidence relations.
- `thehub-pr` — federation authority for validation, aggregation, and cross-producer correlation.
- `aguayluz-pr` — domain authority for water/power/environmental infrastructure, hydro-network, and hazard geography.
- `skywatcher-pr` — domain authority for aviation, airspace, terrain, and 4D trajectory geography.
- `moneysweep-pr` — domain authority for public-money/project/infrastructure spatial binding.
- `centinelas-pr` — domain authority for pre-officialization signal localization and lifecycle spatial indexing.
- `ovnis-pr` — domain authority for historical case-location provenance and precision semantics.

No authority assignment transfers ownership of another producer's domain truth.

## Shared invariants

1. `Cell_ID` is a spatial address, never identity proof.
2. Spatial proximity defaults to `CANDIDATE_NOT_IDENTITY`.
3. RAW, NORMALIZED, and CANONICAL representations remain separate.
4. WGS84/CRS84 is canonical interchange; projected computation must declare its CRS.
5. Missing coordinates remain missing. Do not fabricate centroids or inferred exact points.
6. Renderer success is not spatial certification.
7. `N/A` is not `LOW` and is not `FAIL`.
8. Producer domain truth stays producer-local; Hub correlation cannot silently promote candidate relations into identity.
9. Geometry/source-manifestation identity, logical identity, and entity identity remain separate claims.
10. Every certification claim requires a frozen fixture denominator and zero unresolved residue within that claim.

## Role matrix

| Capability family | Spiderweb | AguaYLuz | Skywatcher | MoneySweep | Centinelas | OVNIS | TheHub |
|---|---|---|---|---|---|---|---|
| Generic geometry semantics | FEDERATION_AUTHORITY | CONSUMER | CONSUMER | CONSUMER | CONSUMER | CONSUMER | VALIDATOR |
| Typed cross-domain spatial relation | FEDERATION_AUTHORITY | PRODUCER_CANDIDATE | PRODUCER_CANDIDATE | PRODUCER_CANDIDATE | PRODUCER_CANDIDATE | PRODUCER_CANDIDATE | CORRELATOR |
| Utility/hydro network topology | N/A | DOMAIN_AUTHORITY | N/A | CONSUMER | CONSUMER | N/A | CORRELATOR |
| Aviation/4D trajectory | N/A | N/A | DOMAIN_AUTHORITY | CONSUMER | CONSUMER | CONSUMER | CORRELATOR |
| Public-money/project spatial binding | CONSUMER | CONSUMER | CONSUMER | DOMAIN_AUTHORITY | CONSUMER | N/A | CORRELATOR |
| Early-signal localization | CONSUMER | CONSUMER | CONSUMER | CONSUMER | DOMAIN_AUTHORITY | N/A | CORRELATOR |
| Historical case-location provenance | CONSUMER | CONSUMER | CONSUMER | N/A | CONSUMER | DOMAIN_AUTHORITY | CORRELATOR |
| Cross-producer package validation | PRODUCER | PRODUCER | PRODUCER | PRODUCER | PRODUCER | PRODUCER | FEDERATION_AUTHORITY |

The machine-readable canonical matrix is `registry/spatial/federation_spatial_capability_matrix_v1.json`.

## Fixture denominator

The fixture denominator is role-specific. Each fixture must terminate in exactly one certification state and may not silently disappear from arithmetic.

### Spiderweb

Minimum cases: point, line, polygon, multipolygon, NULL geometry, empty geometry, touch-only, partial overlap, fully within, outside, invalid geometry, CRS mismatch, candidate-not-identity.

### AguaYLuz

Minimum cases: asset point, network line, service polygon, upstream/downstream trace, hazard intersection, broken network, NULL asset geometry.

### Skywatcher

Minimum cases: observed position, ordered 4D trajectory, altitude present, altitude missing, terrain relationship, track endpoint that must not become airport identity, synthetic observation excluded from live certification.

### MoneySweep

Minimum cases: municipio binding, corridor binding, facility binding, project-area binding, exact point, missing-coordinate no-fabrication, one-to-many project geography.

### Centinelas

Minimum cases: exact Cell_ID binding, approximate location, multi-cell signal, unknown location, Centinelas→MoneySweep lifecycle spatial handoff, same-cell nonidentity.

### OVNIS

Minimum cases: `OBSERVED_POINT`, `INTERPRETED_POINT`, `AREA_REFERENCE`, `REPRESENTATIVE_POINT`, `UNKNOWN`, offshore approximation, same-place-name nonidentity.

### TheHub

Minimum cases: valid package, invalid schema, count mismatch, duplicate record, M:N correlation, candidate-not-identity preservation, uncertainty round-trip, zero unexplained record loss.

## Mandatory evidence fields

Where applicable, producer fixtures should expose:

- stable record/case/asset/observation identifier;
- raw geometry or explicit `NULL`;
- declared CRS;
- geometry source reference;
- source manifestation hash when available;
- precision class;
- horizontal uncertainty;
- vertical uncertainty for 3D/4D observations when meaningful;
- temporal uncertainty when meaningful;
- identity state;
- certification state;
- derivation method/version;
- source and retained record counts.

Unsupported dimensions remain `NULL`; they are not synthesized.

## Positive regression gates

A repository passes a positive gate only when its required role behavior is reproduced deterministically from frozen fixtures. Examples:

- Spiderweb returns the expected topological relation without converting proximity into identity.
- AguaYLuz preserves network direction/topology and hazard intersection outputs.
- Skywatcher preserves observation ordering and 4D semantics.
- MoneySweep preserves declared granularity and does not upgrade municipio/corridor records into exact points.
- Centinelas preserves uncertainty across a later lifecycle match.
- OVNIS preserves precision class and source-to-location lineage.
- TheHub ingests and correlates without record loss, duplication, or identity promotion.

## Negative regression gates

The following must fail closed:

- coordinate order inversion;
- undeclared CRS mutation;
- invalid geometry promoted as valid;
- `NULL` geometry converted to zero/centroid;
- proximity-only identity binding;
- same `Cell_ID` treated as same entity;
- same place name treated as same case/site;
- track endpoint treated as takeoff/landing identity;
- M:N join multiplication without explicit cardinality accounting;
- duplicate source manifestation counted as independent corroboration;
- source/retained/excluded arithmetic mismatch;
- uncertainty dropped during Hub round-trip;
- repository marked failed because an explicitly `N/A` capability is absent.

## Certification algorithm

For each repository:

1. Freeze the repository commit and fixture bytes.
2. Hash every fixture source manifestation.
3. Validate schema and required fields before parsing domain semantics.
4. Execute only capabilities declared `required_capabilities` for that role.
5. Execute shared invariants.
6. Classify every fixture: `PASS | FAIL | OPEN | BLOCKED | PROVISIONAL | AUDIT_ONLY | NONCANONICAL | CANDIDATE_NOT_IDENTITY | UNRESOLVED | SUPERSEDED`.
7. Assert source = retained + excluded and close all derived-count arithmetic.
8. Assert no unintended row loss, duplication, or M:N multiplication.
9. Assert no `not_required` capability is used as a negative criterion.
10. Emit a compatibility receipt binding the tested commit, fixture hashes, contract generation, and result.

Federation certification closes only when all six producer receipts cover the active spatial generation, TheHub validates all receipts/packages, and no unresolved residue remains within the declared certification scope.

## Current blocker

`thehub-pr/scripts/federation_spatial_contract.py` defines spatial generation `federation-spatial-index/1` with four affected contracts:

- `federation_cell_index@1`
- `cell_domain_summary@1`
- `record_cell_binding@1`
- `cell_profile@1`

Existing producer compatibility receipts predate those four spatial contracts. Therefore current spatial generation remains `OPEN` until each affected producer advances or explicitly attests compatibility through evidence-backed testing. Do not add the contract names to receipts merely to make the gate green.

## Completion criteria

`FEDERATION_SPATIAL_CERTIFIED_V1` requires all of the following:

- seven-repository role matrix specification passes;
- six producer fixture denominators are frozen and fully classified;
- Spiderweb generic geometry semantics pass;
- producer domain-specific gates pass only for their declared roles;
- all four active spatial-generation contracts are attested by every affected producer;
- TheHub package/round-trip fixtures pass;
- identity defaults remain fail-closed;
- all source/retained/excluded and join cardinality arithmetic closes;
- zero unexplained record or geometry loss;
- zero unresolved residue inside the claimed scope;
- frozen commit SHAs and fixture hashes are recorded in the final certificate.

Until then the proper terminal state is `OPEN` or `BLOCKED`, not `CERTIFIED`.
