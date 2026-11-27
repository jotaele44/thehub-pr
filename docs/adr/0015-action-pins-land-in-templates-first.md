# ADR 0015 — Action pins land in the federation templates first

- **Status:** Accepted
- **Date:** 2026-11-24
- **Deciders:** PRII federation maintainers
- **Scope:** all seven PRII federation repositories (defined in `thehub-pr`, rendered into each)
- **Builds on:** the template-drift gate described in [`federation-templates/README.md`](../../federation-templates/README.md)
- **Extended by:** [ADR 0016](0016-rendered-pip-manifests-land-in-templates-first.md), the same rule for rendered pip manifests. It also replaces the renderer's refusal of an empty `{{RENDERED_WORKFLOWS}}` with dropping that line.

## Context

`thehub-pr` renders shared workflows (`codeql.yml`, `pip-audit.yml`, `secret-scan.yml`, `docs-sync.yml` and, for adopters, `gui-capability-parity.yml`) into every repository. Each producer's `template-drift.yml` fails when a rendered file differs from the template at its pinned hub commit, and the hub checks its own copies against its live templates.

Every repository also ran the same Dependabot config, rendered from `baseline/dependabot.yml`, and Dependabot bumps `uses:` pins wherever it finds them. That includes the rendered copies. Merging such a bump turns that repository's drift gate red. It happened in spiderweb-pr#410 and was repaired by hand in thehub-pr#446. By 2026-11-23, Dependabot branches in thehub-pr, centinelas-pr, ovnis-pr and skywatcher-pr carried newer pins in rendered files and would have repeated it.

Three facts about Dependabot (checked against the dependabot-core source, `github_actions/file_fetcher.rb` and `updater/`, and the options reference) shape the fix:

1. For the actions ecosystem, `directory: "/"` scans `.github/workflows/`. Any other directory makes Dependabot read every `*.yml` / `*.yaml` directly in it as a workflow, so it can scan the templates themselves.
2. `exclude-paths` removes files from the scan by path, relative to the repository root when the directory is `/`. It applies to version updates only.
3. A group produces one pull request across all `directories`. Ungrouped updates produce one pull request per directory. Group membership limited by `update-types` is judged per directory against the lowest pin of that action found there. The hub's own workflows still pin older majors than the templates do, so the same release can be "major" in one directory and "minor" in another.

## Decision

**An action pin in a rendered workflow changes only in its template, and the hub's Dependabot is what changes it.**

1. **Producers skip their rendered workflows.** `baseline/dependabot.yml`, rendered into the six producers, sets `exclude-paths: ["{{RENDERED_WORKFLOWS}}"]` on the actions ecosystem.
   - The renderer derives that placeholder from `targets.yaml`: the `.github/workflows/` files it renders into that repository.
   - The list therefore follows adoption on its own; a repository added to `_gui_code` stops bumping `gui-capability-parity.yml` on the same render.
   - `template-drift.yml` is not rendered wholesale, so its actions keep their Dependabot bumps.
2. **The hub bumps the templates.** `baseline/dependabot.hub.yml`, rendered into `thehub-pr` only, scans `/`, `/federation-templates/baseline` and `/federation-templates/gui`.
   - One group covers version updates and another covers security updates. Neither is limited by `update-types`, so every bump edits a template and the hub's rendered copy in the same pull request, and the hub's drift gate stays green.
   - The cost is that action majors in the hub arrive inside the weekly group rather than as their own pull requests.
3. **Propagation is the existing sync.** Merging that pull request changes `federation-templates/**`, which runs `federation-template-sync.yml`. It re-renders each producer and rebinds `PRII_TEMPLATE_REF` to the merged commit. Each producer receives the bump in a sync pull request; until it merges, its gate keeps checking against its old pin.

## Alternatives considered

- **`ignore` entries for actions used in rendered workflows.** `ignore` matches a dependency by name for a whole update entry, not by file. The same actions also run in workflows that are not rendered (setup-uv in the hub's and ovnis-pr's `ci.yml`, centinelas-pr's `validate.yml`), so ignoring them would stop legitimate bumps there and still leave nothing bumping the templates.
- **A hub job that copies a Dependabot bump from a rendered file back into the template.** It would need a token with write access to every repository. A commit pushed with `GITHUB_TOKEN` does not start new workflow runs, so the corrected pull request would carry no fresh checks. And Dependabot stops rebasing a branch someone else has pushed to.
- **Two hub groups split by `update-types`.** Rejected because of fact 3: such a group can split one release into two pull requests, each failing the drift gate.

## Consequences

- No Dependabot version update can edit a rendered copy without its template.
- The fix is enforced by `tests/test_render_federation_templates.py`. The tests check that:
  - each producer excludes exactly its rendered workflows;
  - the hub scans every workflow-template directory;
  - no hub group carries `update-types`;
  - every YAML file in a scanned directory parses;
  - an identical edit to a template and the hub's copy keeps `--check` clean.
- Every template bump needs a sync round to reach the producers it changes. The sync workflow keeps one standing `federation-template-sync` pull request per producer and opens none where only `PRII_TEMPLATE_REF` would move. Without the `SYNC_PAT` secret it is a dry run, and someone has to render and open those pull requests by hand. A `SYNC_PAT` that cannot write to a producer fails that producer's job, before any change when the dry-run push already shows it.
- `exclude-paths` does not cover security updates. A Dependabot security PR in a producer can still edit a rendered workflow; its drift gate fails, and the fix is to close it and let the hub's security group bump the template.
- A workflow template placed outside `baseline/` or `gui/` has to be added to the hub's `directories` (a test fails until it is). Every YAML file in those directories must stay valid YAML before rendering, or the hub's Dependabot update fails.

## Verification

- `python3 -m pytest tests/test_render_federation_templates.py`
- `python3 tools/render_federation_templates.py --repo thehub-pr --check --repo-root .`
- After the first hub Dependabot run under this config, its actions pull request reports "across 3 directories" and edits each template together with the hub's copy.
