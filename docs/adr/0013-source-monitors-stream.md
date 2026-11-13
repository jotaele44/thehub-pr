# ADR 0013 — Producers report monitored sources in a `source_monitors` stream

- **Status:** Accepted
- **Date:** 2026-11-11
- **Deciders:** PRII federation maintainers
- **Scope:** `thehub-pr` canonical contract (`federation_export_manifest` 1.0.0 → 1.1.0, new `federation_source_monitor` 1.0.0), `packages/prii_export_utils` 0.2.0, Hub ingest and Source Monitor UI; producers adopt one repository at a time, starting with `aguayluz-pr`
- **Supersedes in part:** ADR 0012. Its hub-side registry reader stays for producers that do not emit the stream yet.

## Context

ADR 0012 gave the Hub a read-only Source Monitor by reading each producer's
registry from a workspace checkout. That reader is an exception to ADR 0001's
artifact-only boundary, and its freshness is producer-level: the age of a
producer's last export package, compared with each source's cadence. A healthy
export can hide a dead feed. ADR 0012 named the fix and deferred it: a frozen
`source_monitors` stream carrying a per-source last-success time.

When each source last succeeded is not recorded uniformly today:

| Producer | Per-source success time today |
|---|---|
| aguayluz-pr | committed `data/hydromet_manifestations.jsonl` records each retrieval (`retrieved_at_utc`) for the two hydromet sources |
| centinelas-pr | signals carry `source_id` and `captured_at` (43 of 87 sources) |
| skywatcher-pr | `retrieved_at` in its export |
| moneysweep-pr, ovnis-pr, spiderweb-pr | none per source |

## Decision

**Add an optional `source_monitors` stream to the producer contract.**

- `schemas/federation_source_monitor.schema.json` (1.0.0) defines one row per monitored source:
  - its registry id (`source_ref`), name, declared status and cadence;
  - `last_success_at`, with an explicit `last_success_basis`. `RUN_RECEIPT` means a producer fetch run recorded it; `OUTPUT_DERIVED` means it was read from timestamps in the producer's own outputs; `NOT_RECORDED` means neither exists. The schema forces `last_success_at` to be null exactly when the basis is `NOT_RECORDED`.
  - The time is never inferred from file modification dates or git history.
- `monitor_id` is `fid("mon", producer, source_ref)` (`mon_[a-f0-9]{32}`). Renaming a source in a registry therefore creates a new id.
- `federation_export_manifest` adds `source_monitors` to `files[].stream`.
  - `scripts/federation_contract_guard.py diff` classifies this as **MINOR**, so the version is 1.1.0.
  - The stream is optional: every existing package stays valid.
  - Governance records the bump (`contract_versions`, `contract_fingerprints`, `change_log`). Every repository keeps a compatible disposition.

**Run receipts live in one committed file per producer:**
`data/source_run_state.json`, with one row per source (last attempt, its status, last success).

- Each fetch run overwrites its source's row through `prii_export_utils.record_run`.
- The file is committed because the Hub clones producer repositories fresh. A local-only record would be invisible to it.
- Writes are atomic with sorted keys, so a run makes a small, stable diff.
- A producer's exporter combines the receipt with any output-derived time through `resolve_last_success`: the more recent wins, and a tie goes to the receipt.

**The Hub merges, it does not replace, during the rollout.**

- `hub ingest` loads the stream's canonical rows into `SourceMonitors`.
- It builds `MonitoredSources` from both inputs: a producer that emits any stream rows is read wholly from the stream, and every other producer keeps its ADR 0012 registry-reader rows.
- Every row and summary entry records its `origin`.
- The UI measures freshness from a source's own last success when the producer reports one. Otherwise it falls back to the producer's export-package age, and the page says which.

## Rollout

1. The Hub contract, ingest and UI, plus `prii_export_utils` 0.2.0 (this change).
2. `aguayluz-pr` emits the stream. Its two hydromet sources take their last success from the committed hydromet run receipts (`RUN_RECEIPT`) or, failing that, the committed manifestations (`OUTPUT_DERIVED`).
3. Then one PR per producer: `centinelas-pr` (signals), `skywatcher-pr` (`retrieved_at`), then `moneysweep-pr` (which first adopts `prii_export_utils`), `ovnis-pr` and `spiderweb-pr` (run receipts only).

After each producer emits, move it from `REGISTRIES` to `STREAM_PRODUCERS` in `src/hub/source_monitor.py`. The registry reader then stops reading that producer and marks it `reports_via_stream`; ingest takes its rows from the stream, and flags the producer with an error when an aggregate has no stream rows from it, instead of dropping it silently. When all six emit, delete the registry reader and its CLI, and the ADR 0012 exception ends.

Status:

- `aguayluz-pr` emits the stream (aguayluz-pr#408, merged 2026-11-13). A Hub ingest on `main` loaded all 25 of its `MonitoredSources` rows with `origin: stream`, and it has moved to `STREAM_PRODUCERS`.

## Consequences

- Per-source freshness becomes real wherever a producer records it, and labelled as unknown where it does not. Nothing is guessed.
- Producers gain a committed state file that changes on fetch runs. Branches that both run fetches can conflict on it; one key per source keeps the conflicts local.
- Until all six producers emit, the Hub keeps the ADR 0012 coupling to producer-internal registry layouts for the rest.
