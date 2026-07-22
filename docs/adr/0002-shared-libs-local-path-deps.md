# ADR 0002 — Shared libraries via local path deps (ADR 0001 Phase 3, step 1)

- **Status:** Accepted
- **Date:** 2026-07-21
- **Deciders:** PRII federation maintainers
- **Scope:** `thehub-pr/packages/*` and the six PRII producer repositories
- **Extends:** [ADR 0001 — Federated engines, one hub app](0001-federated-engines-single-hub.md)

## Context

ADR 0001 kept the six producers as independent engines and deferred duplication
reduction to an incremental **Phase 3** — "never a big-bang merge". The most
literal instance of that duplication is the shared-library coupling: every
producer depended on the two hub-hosted packages
(`packages/prii_maintenance`, `packages/prii_export_utils`) via a **pinned git
commit SHA**, e.g.

```
prii-maintenance @ git+https://github.com/jotaele44/thehub-pr.git@<SHA>#subdirectory=packages/prii_maintenance
```

So changing shared code meant: commit to `thehub-pr`, then bump the SHA line in
each of the six producers — "the same edit six times". This ADR removes that
per-repo bump.

## Decision

**Consume the shared federation libraries via a local path to the sibling
`thehub-pr` checkout, with no version/SHA pin.** The federation already assumes
the producers and `thehub-pr` are checked out side by side under a common
parent, so the dependency becomes a relative path to `../thehub-pr/packages/*`.
Editing a shared package is picked up by every producer immediately, with no
dependency edit in any producer.

Two mechanisms, one per producer packaging style — both install the shared libs
as **editable**, pointing at `../thehub-pr/packages/*`:

- **pyproject producers** (`aguayluz-pr`, `centinelas-pr`, `spiderweb-pr`) keep
  bare dep names in `[project.dependencies]` and add a `[tool.uv.sources]` table
  with `{ path = "../thehub-pr/packages/<pkg>", editable = true }`. These
  producers install with **uv** (`uv pip install --system -e .`), which honors
  `[tool.uv.sources]`.
- **run-as-app producers** (`ovnis-pr`, `skywatcher-pr`, `moneysweep-pr`) use a
  plain-pip relative editable line in their requirements file:
  `-e ../thehub-pr/packages/<pkg>`. No uv and no new `pyproject.toml` are
  required. `moneysweep-pr`'s `requirements.lock` is recompiled in place with
  `uv pip compile` (uv emits the editable as a **relative** path, so the lock
  stays machine-independent and the lockfile-drift gate keeps passing).

## Consequences

- **The sibling `thehub-pr` checkout is now a build requirement — locally and in
  CI.** Each producer workflow that installs the package/requirements first
  clones `thehub-pr` to `../thehub-pr` (branch-matched, falling back to the
  default branch) via an idempotent step. This is **not** new access surface:
  the previous git-SHA dependency already required CI to fetch `thehub-pr`.
- No producer runtime, schema, or readiness-gate change is required. Each
  producer's `test_suite` remains independently runnable once `thehub-pr` is a
  sibling.
- Reversible per repo: restore the `@ git+…@<SHA>` line to pin again.
- This is Phase 3 **step 1** (shared libraries). Consolidating the shared
  `desktop/` + `maintenance/` skeleton into path-dep packages, and
  templating the non-Python boilerplate, remain follow-on Phase 3 steps and do
  not merge the repositories.

## Verification

1. In a sibling layout, add a marker to `packages/prii_maintenance` and confirm
   each producer imports it with **no producer edit** (then revert).
2. Each producer's `test_suite` passes with the shared libs resolved editable
   from `../thehub-pr/packages/*`.
3. CI installs succeed after the idempotent `thehub-pr` sibling clone; the
   federation manifest gate stays green; `moneysweep-pr`'s lockfile-drift gate
   passes against the recompiled `requirements.lock`.
