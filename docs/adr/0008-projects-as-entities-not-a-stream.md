# ADR 0008 — Projects ride the entity stream; a first-class projects stream is deferred

- **Status:** Accepted (entity form); `projects` stream deferred
- **Date:** 2026-08-09
- **Deciders:** PRII federation maintainers
- **Scope:** `thehub-pr` canonical contract, `moneysweep-pr`, `spiderweb-pr`

## Context

A project — an infrastructure programme, a recovery effort, a public-private
partnership concession — is a first-class thing in the PRII domain. It has a
lead agency, a value, a status, a location, and money flowing to it. The
canonical contract has no row type for it.

`moneysweep-pr` models projects properly in its own tables
(`data/canonical_v1/projects.csv`) and, at the federation boundary, promotes them
into `entities.jsonl` with `entity_type=project`
(`moneysweep/federation/canonical_v1_bridge.py::_NODE_TABLES`). The same is done
for municipalities, properties, funding sources, contracts, and debt
instruments. Every edge federates and nothing is lost, but the Hub receives a
project as a generic entity that happens to be labelled one.

This surfaced while wiring the PPP location chain (moneysweep resolves a
concession's municipality → spiderweb resolves it to a point → the Hub renders a
consolidated sign). Three things had to be worked around because a project is
not a first-class row:

1. **Location.** `federation_entity.schema.json` required `lat`+`lon` whenever
   `location` was present, so a producer that knows a municipality and no
   coordinates could not express that. Relaxed to
   `anyOf [lat+lon] | [municipality]`.
2. **Geometry attribution.** A spatial producer cannot write a location onto
   another producer's entity, so spiderweb-pr publishes resolved geometry as an
   `observations` row naming the project it is for, and consumers read it back.
   With a project stream, the Hub could hold one project row that both producers
   contribute fields to.
3. **Rendering.** `src/hub/project_signs.py` inferred a project from a group of
   funding awards, because that was the only project-shaped thing in the
   contract. It now also reads `entity_type=project` entities.

Each workaround is defensible on its own. Together they are the cost of not
having the row type.

## Decision

**Keep projects on the entity stream for now.** It is the form already in
production, it needs no new contract, and the three workarounds above make the
end-to-end chain work today.

**Record the first-class `projects` stream as the intended model, deferred.**
Not rejected — deferred, because it is a breaking contract change that touches
every layer of the Hub and both producers' export writers, and the location
chain did not need to wait for it.

## What the deferred change would take

The wiring is mechanical, which is part of why deferring is safe:

| Layer | Change |
|---|---|
| Contract | new `schemas/federation_project.schema.json`, added to `schemas/FROZEN.sha256` |
| Stream registry | `src/hub/_schemas.py` — `STREAM_SCHEMA`, `STREAM_ID_FIELD` (`project_id`) |
| Package adapter | `src/hub/bridge.py::_CANDIDATES` — `("projects.jsonl", "projects")` |
| Aggregation | `src/hub/aggregate.py` — picks the stream up from the manifest |
| Store | `src/hub/ingest.py::STREAM_TO_COLLECTION` — a `Projects` collection |
| UI | a per-domain collection, and `ProjectSigns.jsx` reading projects directly |
| Producers | `moneysweep-pr/scripts/federation_export.py` emits the stream instead of promoting to entities; `spiderweb-pr` attaches geometry to project rows rather than to observations |

Two things to settle when it is picked up:

- **Migration.** Projects would exist as both entities and project rows during a
  transition, and correlation edges already point at the entity ids. Either
  dual-emit for one cycle, or accept that existing edges rebuild.
- **Who owns which field.** A project row would be written by more than one
  producer (money facts from moneysweep, geometry from spiderweb). The current
  entity+observation split sidesteps that by giving each producer only its own
  rows; a shared row needs a per-field ownership rule.

## Consequences

- The location chain ships now, with a schema relaxation instead of a new stream.
- Projects stay queryable only as entities filtered by `entity_type`, and a
  consumer must know that convention.
- `_NODE_TABLES` keeps promoting municipalities, properties, funding sources,
  contracts, and debt instruments the same way. This ADR is about projects
  because that is what the PPP work exercised; the same argument applies to the
  others and they should move together if the stream is built.
