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

## Installing (git URL, no package index required)

```
pip install "prii-export-utils @ git+https://github.com/jotaele44/thehub-pr.git@<commit-sha>#subdirectory=packages/prii_export_utils"
```

## Pinning policy

Pin to a commit SHA, never to `@main`. Bump = one line, one PR, per producer,
on their own schedule — same convention as `prii_maintenance`.
