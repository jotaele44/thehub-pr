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
5. Adjudicate independent context separately from evidence that binds the matched pair.
6. Keep contradictory evidence and fail closed to `UNRESOLVED`.
7. Export only `CONTEXT_SUPPORTED` / `ADJUDICATED` rows to downstream consumers.
8. Build a graph whose nodes remain distinct and whose edges carry `identity_claim=false`.

## Context is not pair binding

This distinction prevents a subtle transitive error. If an authoritative source establishes that **Toro Negro I Hydroelectric Power Plant is on Calle Luchetti**, that supports the street's hydro-infrastructure context. It does **not** establish that Calle Luchetti was named after, is identical to, or is physically connected with the separate Lucchetti reservoir/project-name family.

HTR therefore stores third-party context with `contextual=true` and `binds_candidate_pair=false`. A matched source/hydro pair can become `ADJUDICATED` only when evidence explicitly binds that pair. Even then, the entities remain distinct (`identity_state=DISTINCT_ENTITIES`).

## Seed regression: Calle Luchetti

The seed deliberately preserves the screenshot spelling `CALLE LUCHETTI` and the hydro-name-family spelling `Lucchetti`. Their one-character difference creates an `ORTHOGRAPHIC_NEAR_MATCH`, not identity.

Current bounded seed disposition:

- `CALLE LUCHETTI` ↔ `Lucchetti`: `ORTHOGRAPHIC_NEAR_MATCH`, pair `UNBOUND`.
- Independent authoritative hydro context may promote the candidate to `CONTEXT_SUPPORTED` without changing that pair relation.
- A sourced naming/dedication record would be required to promote the pair itself to `NAMED_AFTER`, `PERSON_EPONYM`, `PROJECT_EPONYM`, or another explicit relation.

## Downstream contract

`downstream_context()` emits only rows in `CONTEXT_SUPPORTED` or `ADJUDICATED`, always with:

```json
{"downstream_semantics": "CONTEXT_ONLY_NOT_IDENTITY"}
```

Consumers such as flight, water/power, and infrastructure-graph systems should treat this as environmental context. They must not infer a hidden facility, hydraulic connection, electrical connection, aircraft mission, or canonical feature identity from a toponym recurrence alone.

## Regression gates

Tests cover:
- Luchetti/Lucchetti detection with raw spelling preservation;
- no identity promotion from fuzzy/name-only evidence;
- authoritative third-party context without transitive pair binding;
- authoritative pair relation binding while entities remain distinct;
- contradictory evidence blocking promotion;
- rejected-candidate retention;
- duplicate-ID fail-closed behavior;
- multiplicity preservation;
- cluster member conservation;
- deterministic graph generation with zero identity edges;
- downstream context gating;
- bundle arithmetic closure.
