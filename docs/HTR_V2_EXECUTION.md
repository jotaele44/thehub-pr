# HTR v2 — frozen road/hydro recurrence contract

HTR v2 is a discovery-only Hydro-Toponym Recurrence layer. It preserves source manifestations and lexical recurrence without promoting name similarity, fuzzy matching, proximity, or clustering into identity or hydraulic/electrical connectivity.

## State semantics

- `CANDIDATE_NOT_IDENTITY`: a recurrence survives source-specific normalization and negative controls, but the candidate pair remains `UNRESOLVED` and `UNBOUND`.
- `UNSUPPORTED`: the source manifestation is retained as a fact, but the candidate lacks sufficient support for the analytical use at issue. `UNSUPPORTED` does **not** mean false, rejected, or proven distinct.
- `CONTRADICTION`: a preserved conflict or spelling disagreement. A contradiction does not itself resolve identity.
- `UNRESOLVED`: no sufficient pair-binding evidence exists.

All HTR v2 discovery rows keep `identity_state=UNRESOLVED`, `pair_binding_state=UNBOUND`, `identity_claim=false`, `connectivity_claim=false`, and `transitive_context_inheritance=false`.

## Frozen road denominator

The supplied Census TIGER/Line 2025 county/municipio road package contains 78 municipio archives, 183,827 road rows, and 69,846 named road rows. `LINEARID` is unique inside each municipio package but is not globally unique across the island, so HTR v2 keys TIGER observations by `municipio GEOID + LINEARID`.

The TIGER source-specific normalizer expands road abbreviations such as `Cll → Calle`, `Carr → Carretera`, `Cam → Camino`, `Ave → Avenida`, and `Sec → Sector` while preserving the original RAW string. RAW, NORMALIZED, SOURCE_NORMALIZED, CORE, and CANONICAL are stored separately.

## Authoritative hydro denominator v2

The immutable 69-manifestation HTR v1 hydro snapshot remains the base. `MAJOR_HYDRO_ASSET_v2` appends 38 source-specific authoritative name manifestations without cross-source identity collapse:

- DRNA Plan de Aguas Table 4.0-2: 15 active major reservoirs, 4 active intermediate reservoirs, 7 sedimented reservoirs, 2 reservoirs under construction in the 2004 source, and 6 reservoirs in planning.
- USGS Water Resources Data 2003: four conveyance-name manifestations used only as source-bound discovery names.

New v2 manifestations have `canonical_entity_id=null` until independently bound. Equal names do not create canonical identity.

## Bounded rederivation

The frozen union is 99,060 SIGE named-road observations plus 69,846 TIGER named-road observations = 168,906 road observations. With 107 hydro-name manifestations, HTR v2 yields 5,569 lexical candidate rows. Negative controls classify 3,831 rows as `UNSUPPORTED`; 1,738 remain `CANDIDATE_NOT_IDENTITY`. Arithmetic closes: `5,569 = 3,831 + 1,738`.

Every row is classified, so unexplained classification residue is zero. The 1,738 surviving relations remain unresolved by design; zero unexplained residue is not equivalent to resolved identity or connectivity.

## Legacy 1,513-row receipt

The earlier locally reported `1,513` supported-row count is retained as historical provenance but is `SUPERSEDED_NONREPRODUCIBLE`. The exact 26-manifestation local extension used for that number was not frozen as a byte-addressable artifact or committed source. A nearest reconstruction produces 1,521 supported rows, an eight-row mismatch. HTR v2 does not synthesize or delete rows to force the legacy count.

## Certification boundary

Certified: frozen denominator counts, composite TIGER observation-key rule, source-specific normalization contract, negative-control classification, row arithmetic, and zero unexplained classification residue.

Not certified: universal Puerto Rico hydro coverage, cross-source canonical identities, eponymy, hydraulic connectivity, electrical connectivity, or any transitive inheritance of context.
