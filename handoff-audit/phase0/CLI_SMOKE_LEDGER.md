# CLI Smoke Ledger (T006)

Pinned commit `70765a2c4bd67470ee6b9892023f3ff4c80913b8`. **Read-only invocations only** — no
state-writing subcommand was run (no fetch / aggregate / correlate / ingest / analytics-v2 /
consume-sensor-fusion / wrap-bridge / `maintenance --write-report`).

| Invocation | Type | Result |
|---|---|---|
| `hub --help` | help | **OK** — lists all 13 subcommands |
| `hub <sub> --help` × 13 | help | **OK** for every subcommand (list, validate-manifest, validate-package, validate-federation, fetch, aggregate, wrap-bridge, correlate, ingest, graph-report, analytics-v2, consume-sensor-fusion, maintenance) |
| `hub list --registry registry/producers.yaml` | read-only | **OK** — prints 6 producers with status/role/repo |
| `hub validate-federation --root . --json` | read-only rollup | **OK** — exits 1 (not all ready), reports `producer_count=6`, all 6 `blocker_class=missing_checkout` |
| `hub maintenance --root . --json` | read-only rollup | **OK** — exits 0, `promotion_blocked=true`, blocker "6 producer maintenance report(s) missing" |

## Interpretation

The two rollups report blockers because the 6 sibling **producer repositories are not checked out**
in this isolated Hub-only audit container (`missing_checkout` / "maintenance report missing"). This is
the **correct, expected** behavior for a standalone Hub tree — the CLI degrades gracefully and reports
the missing inputs rather than crashing. It is **not** a Hub defect. Exercising the full readiness path
would require the 6 producer repos checked out alongside the Hub (see T008 note and the single test skip
in `TEST_RUN_LEDGER.md`).
