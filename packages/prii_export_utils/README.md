# prii-export-utils

Shared envelope-id/hash helpers used by each PRII producer's
`scripts/federation_export.py` (ADR 0001, Phase 3 follow-up). Extracted from
the near-identical `_fid`/`_norm`/`_sha256` helpers duplicated across
`aguayluz-pr`, `spiderweb-pr`, `ovnis-pr`, `skywatcher-pr`, and
`centinelas-pr`.

## What moved here vs. what stays in each producer

`fid(prefix, *parts)`, `norm(name)`, and `sha256(path)` only — confirmed
byte-identical (`norm`/`sha256`) or behaviorally identical (`fid`; the
algorithm was already the same everywhere, just written as a one-liner in
some repos and a two-liner in others) across all five target repos.

Everything else in `federation_export.py` — `_lineage`, `write_package`,
`build_streams`, `STREAM_SCHEMA`, `PRODUCER`, `CONTRACT_VERSION` — stays
vendored per-producer. `_lineage` has two incompatible call signatures across
repos today, and `write_package` has real per-repo differences (defensive
`.get()` vs. direct indexing, differing stream tuples); both are deliberately
out of scope for this extraction.

Each producer imports these aliased to their existing private names, so no
call site elsewhere in `federation_export.py` needs to change:

```python
from prii_export_utils import fid as _fid, norm as _norm, sha256 as _sha256
```

`moneysweep-pr`'s `federation_export.py` is not a consumer — it is an
architecturally different bridge/wrapper around
`moneysweep.federation.canonical_v1_bridge` with an intentionally different
serialization contract, independently unit-tested for byte-reproducibility.

## `source_monitors` helpers (0.2.0, ADR 0013)

Producers that emit the `source_monitors` federation stream
(`schemas/federation_source_monitor.schema.json`) build each row with
`source_monitor_row(...)`, which checks the vocabularies and the rule that
`last_success_at` is null exactly when `last_success_basis` is `NOT_RECORDED`, and
derives `monitor_id` as `fid("mon", producer, source_ref)`.

When a source last succeeded comes from one of two places, combined by
`resolve_last_success(state_row, derived_at)` (the more recent wins; a tie goes to
the run receipt):

- **Run receipts:** fetch scripts call `record_run(path, source_id, "success" |
  "failure" | "partial")`, which overwrites that source's row in the producer's
  committed `data/source_run_state.json` (`SourceRunState`; atomic write, sorted
  keys, so a run makes a small, stable diff).
- **Output-derived:** a timestamp the producer reads from its own outputs, such as
  the latest retrieval of a source.

Neither is ever inferred from file modification times or git history.

These helpers need a pin at or after the thehub-pr commit that adds them.

## Installing (git URL, no package index required)

```
pip install "prii-export-utils @ git+https://github.com/jotaele44/thehub-pr.git@f2b81769924689b4d959554928810b1d7b7ef3d6#subdirectory=packages/prii_export_utils"
```

## Pinning policy

Pin to the exact commit SHA (`f2b81769…` is the current pin, per ADR 0007),
or to a release tag (`prii-export-utils-vN`) once a
maintainer cuts one at that SHA — never to `@main`. Bump = one line, one PR,
per producer, on their own schedule — same convention as `prii_maintenance`.

## Where the pin lives (federation convention)

Same rule as `prii_maintenance`: the pin lives in the producer's primary
install manifest (`pyproject.toml` `[project.dependencies]` if the repo has
one, else the runtime `requirements.txt`), and `federation.json`'s `setup`
command plus CI install from that manifest instead of repeating the git+https
string. `setup` must install everything the repo's other hub-callable
commands import.
