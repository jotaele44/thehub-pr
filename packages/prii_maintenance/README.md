# prii-maintenance

Shared deterministic, audit-first maintenance core for PRII producer repos
(ADR 0001, Phase 3). Extracted from the near-identical `maintenance/` package
that `moneysweep-pr`, `spiderweb-pr`, `ovnis-pr`, and `skywatcher-pr` each
vendored independently.

## What moved here vs. what stays in each producer

`models.py`, `state.py`, `detect.py`, `corrections.py`, `quarantine.py`,
`report.py`, and a generalized `runner.py` — the generic, repo-agnostic
detection/report/correction logic.

Each producer's `maintenance/adapters/local.py` — its own repo-specific checks
— stays vendored in that producer's repo. This package has no adapters of its
own; a producer's CLI shim passes its adapter in explicitly:

```python
from prii_maintenance import run_maintenance
from maintenance.adapters import local

report = run_maintenance(
    root=REPO_ROOT,
    mode=args.mode,
    write=not args.no_write,
    program_id="spiderweb-pr",
    local_checks=local.run_checks,
)
```

## Installing (git URL, no package index required)

```
pip install "prii-maintenance @ git+https://github.com/jotaele44/thehub-pr.git@3c9e51e3de406f8455605a06fabd4823452d9b63#subdirectory=packages/prii_maintenance"
```

## Pinning policy

Producers pin to the exact commit SHA (`3c9e51e…` is the v1 extraction
commit, the current release), or to a release tag (`prii-maintenance-vN`)
once a maintainer cuts one at that SHA — never to `@main`. **Never force-move
an existing tag** — cut `vN+1` on a new commit and let each producer bump
deliberately: edit one dependency line, open one PR, re-run that producer's
test suite.

## Where the pin lives (federation convention)

Each producer declares the pin in exactly one place — its **primary install
manifest**: `[project.dependencies]` in `pyproject.toml` where the repo has
one, else the runtime `requirements.txt`. The repo's `federation.json`
`hub_callable_commands.setup` and its CI workflows install **from that
manifest** (`pip install -e .[dev]` / `pip install -r requirements.txt`)
rather than repeating the git+https string, so the pinned SHA cannot drift
between files. `setup` must install everything the repo's other hub-callable
commands import.
