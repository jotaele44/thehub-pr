# Hydro-Toponym Recurrence (HTR)

HTR is a **discovery and contextual-adjudication layer** for repeated hydro/infrastructure names in roads, barrios, sectors, facilities, bridges, parks and other named features.

## Core invariant

A name recurrence is **not identity**. Exact names, normalized names, fuzzy matches, nearest-neighbour results, proximity and clusters may create candidates; none may create a `SAME_AS` relationship.

HTR always preserves `RAW`, `NORMALIZED`, and source/canonical identities separately. Candidate multiplicity, contradictions, rejected matches and unresolved rows are retained.

## Pipeline

1. Freeze the hydro/infrastructure name registry and source manifests.
2. Ingest toponym observations with stable observation IDs and raw labels.
3. Run deterministic exact/orthographic/fuzzy discovery.
4. Preserve all candidates as `CANDIDATE_NOT_IDENTITY`.
5. Adjudicate with independent documentary, authoritative address, historical, hydraulic or electrical evidence.
6. Keep contradictory evidence and fail closed to `UNRESOLVED`.
7. Export only `CONTEXT_SUPPORTED` / `ADJUDICATED` rows to downstream consumers.
8. Build a graph whose nodes remain distinct and whose edges carry `identity_claim=false`.

## Seed regression: Calle Luchetti

The seed deliberately preserves the screenshot spelling `CALLE LUCHETTI` and the hydro-name-family spelling `Lucchetti`. Their one-character difference creates an `ORTHOGRAPHIC_NEAR_MATCH`, not identity. The seed remains `CANDIDATE_NOT_IDENTITY` until independent evidence supports a specific relation.

Potential supported relations include `ADDRESS_OF`, `PERSON_EPONYM`, `PROJECT_EPONYM`, `NAMED_AFTER`, or a sourced administrative/historical relation. Each is distinct from canonical feature identity.

## Downstream contract

`downstream_context()` emits only rows in `CONTEXT_SUPPORTED` or `ADJUDICATED`, always with:

```json
{"downstream_semantics": "CONTEXT_ONLY_NOT_IDENTITY"}
```

Consumers such as flight, water/power, and infrastructure-graph systems should treat this as environmental context. They must not infer a hidden facility, hydraulic connection, electrical connection, or aircraft mission from a toponym recurrence alone.

## Regression gates

Tests cover:
- Luchetti/Lucchetti detection with raw spelling preservation;
- no identity promotion from fuzzy/name-only evidence;
- authoritative contextual promotion while keeping entities distinct;
- contradictory evidence blocking promotion;
- rejected-candidate retention;
- duplicate-ID fail-closed behavior;
- multiplicity preservation;
- cluster member conservation;
- deterministic graph generation with zero identity edges;
- downstream context gating;
- bundle arithmetic closure.
