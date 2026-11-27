# ADR 0016 — Rendered pip manifests land in the federation templates first

- **Status:** Accepted
- **Date:** 2026-11-24
- **Deciders:** PRII federation maintainers
- **Scope:** all seven PRII federation repositories (defined in `thehub-pr`, rendered into each)
- **Builds on:** [ADR 0015](0015-action-pins-land-in-templates-first.md)
- **Extended by:** [ADR 0017](0017-dependabot-updates-uv-lock-with-its-manifest.md), which runs this entry as the `uv` ecosystem in repositories that commit `uv.lock`. Everything said here of "the pip ecosystem" holds for it too: the two share the file fetcher.

## Context

ADR 0015 kept Dependabot off the workflows `thehub-pr` renders into the producers. The same failure exists for Python. `federation-templates/requirements-desktop.txt` renders into `requirements-desktop.txt` in the five desktop producers (`_desktop` in `targets.yaml`). Each producer's `.github/dependabot.yml` scans `/` for pip, so a `pywebview` release lets Dependabot raise that floor in the rendered copy, and the producer's `template-drift.yml` fails once the bump merges. The producers already receive pip bumps of the same kind (for example `dependabot/pip/fastapi-gte-0.141.1` in ovnis-pr).

Four facts about Dependabot's pip ecosystem shape the fix. They are taken from dependabot-core (`python/lib/dependabot/python/shared_file_fetcher.rb`, `python/file_fetcher.rb`, `common/lib/dependabot/file_fetchers/base.rb`) and from this repository's history:

1. With `directory: "/"`, it reads every `*.txt` / `*.in` file at the root **and one directory below**, keeping those named like requirements or whose lines all parse as requirements (`req_txt_and_in_files`, `req_files_for_dir`). It also reads `pyproject.toml`, `setup.py`, `setup.cfg`, `Pipfile`, `Pipfile.lock`, `poetry.lock` and `pdm.lock` at the root.
2. `exclude-paths` is honoured when listing the repository and again on the final file set.
3. If a scanned requirements file uses `-r` or `-c` to reference an excluded file, the fetch raises `DependencyFileNotEvaluatable` and the repository's whole pip update fails.
4. Because of fact 1, the hub's own pip scan already reaches `federation-templates/requirements-desktop.txt`. In `f1cfad5` (2026-08-10) Dependabot raised `pywebview` from `>=5.0` to `>=6.2.1` in that template and in the hub's `requirements-desktop.txt` in one pull request. The `{{DESKTOP_EXTRA_REQUIREMENTS}}` placeholder was already in the template, trailing a direct-reference line that Dependabot parses but never bumps.

## Decision

**A requirement in a rendered pip manifest changes only in its template, and the hub's Dependabot is what changes it.**

1. **Producers skip their rendered pip manifests.** `baseline/dependabot.yml` sets `exclude-paths: ["{{RENDERED_PIP_MANIFESTS}}"]` on the pip ecosystem.
   - The renderer derives that placeholder from `targets.yaml`, the same way as `{{RENDERED_WORKFLOWS}}`. It lists the rendered outputs that fact 1 says the pip ecosystem would read. Today that is `requirements-desktop.txt` in the desktop producers.
   - The rule follows Dependabot's reach rather than the narrower `requirements*.txt` at the root, so a constraints file or a manifest one directory down is covered the day it is templated.
2. **An empty derived list drops its line.** spiderweb-pr receives `baseline/dependabot.yml` but no pip manifest.
   - Where a derived list is empty for a repository, the renderer removes the whole template line `<key>: ["{{PLACEHOLDER}}"]`, so that repository's pip entry has no `exclude-paths` at all.
   - A placeholder in any other position is still refused.
   - The template stays valid YAML before rendering, which the hub's actions scan of `federation-templates/baseline` requires (ADR 0015).
   - The same rule replaces the earlier refusal of an empty `{{RENDERED_WORKFLOWS}}`. That case does not occur today, because every repository renders `codeql.yml`.
3. **The hub bumps the template.** `baseline/dependabot.hub.yml` keeps pip at `directory: "/"` with no `exclude-paths`.
   - By fact 4, one hub pull request edits the template and the hub's own `requirements-desktop.txt` together. The hub renders no copy of this template, so its drift gate is unaffected.
   - Tests require the template's `pywebview` line to equal the hub's, so the hub keeps testing the floor that producers ship, and a hand edit to only one of the two fails CI.
4. **Propagation is the existing sync**, exactly as in ADR 0015.

## Alternatives considered

- **A separate Dependabot template for repositories without a pip manifest.** This would be a third Dependabot variant, plus a second list of repositories to keep in step with `_desktop`. The derived placeholder exists to avoid exactly that.
- **Rendering `exclude-paths: []` for spiderweb-pr.** Whether Dependabot's config schema accepts an empty list was not verified, and a config it rejects stops every ecosystem in that repository. An omitted key has an unambiguous meaning.
- **`ignore: pywebview` in the producers.** `ignore` matches a dependency by name across the whole ecosystem rather than by file, and it would leave the other lines of a rendered manifest exposed.
- **A second hub pip directory, `/federation-templates`.** The template is already in scope. A second entry would scan it twice, and an ungrouped (major) bump would be split into one pull request per directory (ADR 0015, fact 3).
- **A documented manual bump only.** Unnecessary given fact 4. It remains the fallback if the hub's pip run stops producing pull requests.

## Consequences

- No Dependabot version update in a producer can edit a rendered pip manifest.
- The fix is enforced by `tests/test_render_federation_templates.py`. The tests check that:
  - the derived list matches Dependabot's reach and is exactly `requirements-desktop.txt` in each desktop producer and empty elsewhere;
  - each producer's pip entry excludes exactly that list, and spiderweb-pr's has no `exclude-paths`;
  - an empty list drops only its line, and a misplaced placeholder is refused;
  - the hub's pip scan is `/` with no exclusions and reaches every pip-manifest template;
  - no placeholder sits on a registry requirement line;
  - the template's `pywebview` line equals the hub's.
- Pip-manifest templates must stay directly in `federation-templates/`. One directory deeper is out of the hub's scan.
- A producer file must never `-r` or `-c` a rendered manifest, or that producer's pip updates fail (fact 3). None does today; the hub's tests cannot see producer files, so this is a documented rule.
- `exclude-paths` covers version updates only, as ADR 0015 notes for actions. A security PR that edits a rendered manifest should be closed in favour of a template bump.
- Every template bump needs a sync round to reach the producers, as in ADR 0015.

## Verification

- `python3 -m pytest tests/test_render_federation_templates.py`
- `python3 tools/render_federation_templates.py --repo thehub-pr --check --repo-root .`
- After the producers' sync PRs merge, each desktop producer's `.github/dependabot.yml` has `exclude-paths: ["requirements-desktop.txt"]` on its pip entry, and spiderweb-pr's pip entry has none.
