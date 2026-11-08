# ADR 0012 — Source monitor reads producer registries hub-side; a `source_monitors` stream is deferred

- **Status:** Accepted (hub-side adapter); `source_monitors` stream deferred
- **Date:** 2026-11-08
- **Deciders:** PRII federation maintainers
- **Scope:** `thehub-pr` (`src/hub/source_monitor.py`, `hub ingest`, the Source Monitor UI); no producer changes

## Context

The hub needs a read-only view of the sources each producer monitors (about 340
across the six producers): what each source is, how often it should update, and
whether it looks current. Nothing that crosses the federation contract carries
this:

1. **The stream list is closed.** `federation_export_manifest.schema.json`
   enumerates exactly seven `files[].stream` values, and the schema is frozen
   (`schemas/FROZEN.sha256`). A producer cannot ship a monitored-sources file
   inside its export package without a contract change.
2. **`sources` rows are provenance, not monitoring.** `federation_source` has no
   cadence, active flag, pipeline status or poll time. Its `source_ref` does not
   join back to registry ids either: in the committed aggregate sample, 0 of 167
   MoneySweep and 0 of 26 OVNIS registry ids appear as a `source_ref`.
3. **The data exists, but only producer-side.** Each producer keeps its own
   registry, in its own shape (a CSV in moneysweep-pr, centinelas-pr, ovnis-pr and
   spiderweb-pr, YAML in skywatcher-pr and spiderweb-pr, JSON families in
   aguayluz-pr). None records a per-source last-successful-poll time.

ADR 0001 fixes the producer boundary as artifact-based: the hub reads producers
through the frozen `federation.json` and export-package contract. `hub
maintenance` already reads a producer-side file (`reports/maintenance/latest.json`),
but that file is validated against a frozen schema. Reading registries is a new
coupling with no contract behind it.

## Decision

**Read producer registries hub-side, as a scoped exception, until a stream exists.**

`src/hub/source_monitor.py` (CLI: `hub source-monitor --root <workspace>`) parses
each producer's registry from a workspace checkout, using the same `--root`
layout as `hub maintenance` and `hub validate-federation`. It writes
`monitored_sources.jsonl` and `monitored_sources_summary.json` beside the
aggregate, and `hub ingest` loads them into the `MonitoredSources` and
`SourceMonitorSummary` collections.

The exception is bounded:

- **Read-only.** The adapter never writes to a producer and changes no producer
  repository.
- **Hub-derived, not a stream.** The output is not added to
  `STREAM_TO_COLLECTION`, the export manifest or any frozen schema. Ingest replaces
  the collection on every run (canonical streams only upsert), so a source dropped
  from a registry leaves the hub.
- **Fail-soft and visible.** A missing checkout, file or column is recorded per
  producer in the summary and shown on the Source Monitor page. It never raises,
  so one drifted registry cannot hide the others.
- **One edit point.** The producer → registry path → parser map is the single
  constant `REGISTRIES`. Producer vocabularies are normalized through pinned
  tables (`tests/test_source_monitor.py`); an unmapped value becomes `unknown`
  and the raw value is kept.
- **Producer boundaries are respected.** Sources a producer marks as never
  federated (spiderweb-pr `federation_eligible: false`) are counted in the summary
  and not surfaced.
- **No invented taxonomy.** Producer families are kept verbatim; there is no shared
  category list across producers yet.

**Freshness is producer-level.** The only timestamp available is the `created_at`
of each producer's export-package manifest (the field `hub.federation_status`
reads). The UI labels it "Producer export" and compares it with each source's
cadence window. A healthy export can hide a dead feed.

## The deferred `source_monitors` stream

This adapter ends when producers publish monitoring data through the contract.
Following the ADR 0008 table:

| Layer | Change |
|---|---|
| Contract | new `schemas/federation_source_monitor.schema.json`, added to `schemas/FROZEN.sha256`; `source_monitors` added to the export-manifest stream enum (a frozen-schema change) |
| Stream registry | `src/hub/_schemas.py`: `STREAM_SCHEMA`, `STREAM_ID_FIELD` (`monitor_id`) |
| Package adapter | `src/hub/bridge.py::_CANDIDATES`: `("source_monitors.jsonl", "source_monitors")` |
| Aggregation | `src/hub/aggregate.py` picks the stream up from the manifest |
| Store | `src/hub/ingest.py`: `MonitoredSources` fed from the stream instead of the hub-derived file |
| UI | none; it already reads `MonitoredSources` |
| Producers | each export writer emits its registry plus a per-source `last_success_at`, which no registry records today |

Retire `src/hub/source_monitor.py` producer by producer as each one emits the stream.

## Consequences

- Operators and analysts get a read-only Source Monitor now, with no contract change.
- The hub depends on producer-internal file layouts. A producer reshaping its
  registry breaks that producer's rows, visibly, until `REGISTRIES` is updated.
- The monitor is only as current as the workspace `hub source-monitor` last ran
  against. A deployed hub that only runs `hub ingest` shows the last file it was given.
