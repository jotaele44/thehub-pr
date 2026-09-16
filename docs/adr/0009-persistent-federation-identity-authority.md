# ADR 0009 — Persistent federation identity authority

- **Status:** Proposed
- **Date:** 2026-08-10
- **Deciders:** PRII federation maintainers
- **Scope:** `thehub-pr` federation identity resolution

## Context

TheHub already owns federation discovery, validation, aggregation, and cross-producer correlation. Existing producer rows keep their deterministic `ent_*` identifiers; `src/hub/aggregate.py` deduplicates identical ids and records `_producers`, while `src/hub/correlate.py` emits deterministic relationship candidates between distinct producer ids. `schemas/contracts/entity_resolution.v1.schema.json` freezes reversible, evidence-backed resolution decisions, but the current aggregate/ingest path does not persist a separate federation entity membership registry or merge lineage.

## Decision

TheHub is the **federation authority for cross-producer identity equivalence and its lineage**. Producers remain authoritative for their domain records and producer-native identifiers.

The following semantics are distinct and MUST NOT be conflated:

- `domain_owner`: repository/system authoritative for the underlying domain fact.
- `source_producer`: producer that emitted the member record.
- `local_record_id`: immutable producer-native identifier.
- `federation_authority`: authority that adjudicates cross-producer equivalence; for this federation, `thehub-pr`.
- `federation_entity_id`: stable Hub identity assigned to an adjudicated equivalence class. It never replaces a producer id.

The persistent registry is append/audit preserving. A merge, rejection, supersession, or tombstone never deletes historical decisions or producer identifiers.

## Identity resolution policy

Automatic merge is permitted only when a deterministic rule has an explicit reviewable basis. Allowed match classes are:

1. `EXACT_IDENTIFIER` — same authoritative namespace + identifier value.
2. `EXPLICIT_CROSSWALK` — an authoritative or maintainer-approved producer-to-federation crosswalk.
3. `PROVEN_RELATIONSHIP` — evidence explicitly establishes identity equivalence, not merely association.
4. `REVIEWED_MATCH` — a human adjudicator accepts a candidate with evidence and reason code.

`normalized_name`, shared address, shared coordinates, co-occurrence, spatial proximity, temporal proximity, embedding similarity, and other similarity signals MAY create candidates but MUST NOT auto-merge entities by themselves.

## Persistence contract

The registry consists of five versioned contracts:

- `federation_entity.v1`
- `federation_entity_member.v1`
- `federation_relationship.v1`
- `federation_provenance.v1`
- `federation_event.v1`

The implementation MUST enforce:

- stable `federation_entity_id` and `federation_relationship_id` values;
- uniqueness of `(source_producer, local_record_id)` membership;
- immutable producer ids and source revisions;
- explicit provenance and payload hashes;
- validity intervals where known;
- reversible merge/supersession lineage;
- idempotent UPSERT/MERGE/SUPERSEDE/TOMBSTONE replay;
- stale revisions cannot mutate current state;
- unknown schema versions fail closed.

## Existing identifiers

Existing `ent_*` ids remain valid canonical stream identifiers. They are not retroactively redefined as federation-global identity ids. A producer/aggregate row becomes a member of a federation identity through a membership record.

## Evidence separation

TheHub may correlate and resolve identities, but does not become the owner of MoneySweep procurement facts, SpiderWeb spatial facts, SkyWatcher airspace observations, AguaYLuz utility facts, OVNIS case facts, or Centinelas public-matter facts. Federation projections carry references and provenance; they do not duplicate raw producer evidence unnecessarily.

## Consequences

- No producer needs to mutate its primary keys.
- Existing correlation relationships remain candidate/evidence surfaces and can coexist with adjudicated identity membership.
- Consumers such as SkyWatcher may persist a read-only contextual projection keyed by `federation_entity_id` while retaining links to producer evidence.
- A future identity merge can be reversed without rewriting source history.

## Certification gates

Certification requires a frozen denominator and at least two complete replays with:

- zero new entities on second replay;
- zero duplicate members, aliases, identifiers, or relationships;
- zero orphan relationships;
- zero invalid provenance or payload hashes;
- zero authority collisions;
- zero producer-id mutations;
- zero federation-id drift.

Until those gates execute successfully, this ADR freezes authority and invariants but does not constitute runtime certification.
