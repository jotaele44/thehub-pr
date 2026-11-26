# ADR 0017 — Dependabot updates uv.lock with its manifest

- **Status:** Accepted
- **Date:** 2026-11-26
- **Deciders:** PRII federation maintainers
- **Scope:** all seven PRII federation repositories (defined in `thehub-pr`, rendered into each)
- **Builds on:** [ADR 0016](0016-rendered-pip-manifests-land-in-templates-first.md)

## Context

Every repository ran Dependabot's Python updates through `package-ecosystem: "pip"`, rendered from `baseline/dependabot.yml` (and `dependabot.hub.yml` for the hub). Five of the seven repositories lock with uv: thehub-pr, spiderweb-pr, skywatcher-pr, aguayluz-pr and centinelas-pr commit `uv.lock`, and their `lock_cmd` is `uv lock --check`. moneysweep-pr and ovnis-pr compile `requirements.lock` with `uv pip compile` and have no `uv.lock`.

Dependabot's pip updater rewrites `pyproject.toml` and requirement files, but it never touches `uv.lock`. So in a uv-locked repository, every pip bump that raised a floor in `pyproject.toml` left the lock behind:

- In skywatcher-pr, the pip PR `pyarrow-gte-25.0.1` (`e562433`) raised `pyarrow>=14` to `>=25.0.1` in `pyproject.toml` only. Once merged, `uv lock --check` failed on `main` and on every pull request based on it.
- When this ADR was written, eleven more such PRs were open: five in skywatcher-pr and six in spiderweb-pr.
- aguayluz-pr and centinelas-pr run no lock check, so the same drift goes unnoticed there.

Three facts from dependabot-core (`uv/lib/dependabot/uv/`, checked at `0553a691`) shape the fix:

1. **Same files, same reach.** The uv file fetcher subclasses `Python::SharedFileFetcher`, the pip fetcher's base. It reads the same manifests: `*.txt` / `*.in` files at the root and one directory down, `pyproject.toml`, and also `uv.lock`. It honours `exclude-paths` in the same places.
2. **One commit for manifest and lock.** The uv file updater rewrites `pyproject.toml` and `uv.lock` together (`LockFileUpdater`).
3. **Plain requirement files are still bumped.** The uv updater edits them through `RequirementFileUpdater`, which `CompileFileUpdater#update_uncompiled_files` calls. The spec "with no Pipfile or pip-compile files" covers this case. A uv-ecosystem security update in aguayluz-pr (`dependabot/uv/uv-2daf6b219d`) edited the plain `constraints-desktop.txt`.

## Decision

**A repository that commits `uv.lock` runs Dependabot's Python updates as the `uv` ecosystem; every other repository keeps `pip`.**

1. **Per-repository key.** `producers.vars.yaml` gains `python_ecosystem`, set to `uv` or `pip`. Both Dependabot templates write `package-ecosystem: "{{PYTHON_ECOSYSTEM}}"`. The placeholder is quoted, so the templates stay valid YAML for the hub's actions scan (ADR 0015).
2. **Tied to `lock_cmd`.** `python_ecosystem` is `uv` exactly where `lock_cmd` is `uv lock --check`, and a test enforces this. A repository that moves to `uv.lock` changes both keys in one edit.
3. **Everything else unchanged.** Schedule, groups, labels, commit prefix and the `{{RENDERED_PIP_MANIFESTS}}` exclusion stay the same.
   - By fact 1, ADR 0016's mechanism is unchanged: the hub's scan still reaches `federation-templates/requirements-desktop.txt`, and producers still skip their rendered copy.
   - By fact 3, the template's `pywebview` floor is still bumped together with the hub's own `requirements-desktop.txt`.

## Alternatives considered

- **Run pip and uv side by side.** Both would read `pyproject.toml` and open a pull request for the same dependency, and the pip one would still leave the lock stale.
- **Keep pip, and have a CI job re-lock Dependabot branches.** This needs a token with write access to each repository. A commit pushed with `GITHUB_TOKEN` starts no new workflow runs, and Dependabot stops rebasing a branch someone else has pushed to (ADR 0015 rejected a hub job for the same reasons).
- **Keep pip, but ignore the dependencies declared in `pyproject.toml`.** This stops the stale locks by also stopping the updates.
- **Derive the ecosystem from `lock_cmd` inside the renderer.** It would work, but it would bind the renderer to the wording of a command. An explicit key plus the test keeps that rule visible in the vars file.

## Consequences

- In the five uv-locked repositories, a Dependabot Python pull request edits `pyproject.toml` and `uv.lock` together. Its branch is named `dependabot/uv/...` instead of `dependabot/pip/...`.
- Open `dependabot/pip/*` pull requests in those repositories are left over from the old configuration. Close them once the sync PR that switches the ecosystem merges; the next uv run reopens each update with the lock.
- moneysweep-pr and ovnis-pr are unchanged.
- `tests/test_render_federation_templates.py` enforces the rule. The tests check that:
  - every repository declares `pip` or `uv`, consistent with its `lock_cmd`;
  - both templates take the ecosystem from the placeholder;
  - each rendered producer config uses its declared ecosystem;
  - the hub's own config is `uv`.
- aguayluz-pr and centinelas-pr still have no `uv lock --check` in CI. This decision stops Dependabot from producing stale locks there, but nothing yet catches a stale lock from another source.

## Verification

- `python3 -m pytest tests/test_render_federation_templates.py`
- `python3 tools/render_federation_templates.py --repo thehub-pr --check --repo-root .`
- After each producer's sync PR merges, its next Dependabot Python pull request is on a `dependabot/uv/...` branch and changes `uv.lock` alongside `pyproject.toml`.
