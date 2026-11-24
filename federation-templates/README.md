# federation-templates — canonical shared boilerplate

Single source of truth for the non-Python boilerplate that every PRII repo used
to copy: the `Fix-Gatekeeper.command` and `PRII-<APP>.{command,bat,sh}` launchers,
`requirements-desktop.txt` (desktop producers), and the shared
`schemas/federation_export_manifest.schema.json` contract. `baseline/` holds the
engineering and governance baseline (CI workflows, pre-commit, contributor docs)
and the docs-sync rule described below.

Placeholders are `{{UPPER_CASE}}` keys taken from each repo's entry in
`producers.vars.yaml` (every key is documented at the top of that file, and the
renderer refuses to write a file with one left unresolved); which template renders
where lives in `targets.yaml`. One placeholder is derived instead of read from the
vars file: `{{RENDERED_WORKFLOWS}}` lists the `.github/workflows/` files
`targets.yaml` renders into the repo (see
[Action pins](#action-pins-dependabot-bumps-the-template-never-a-copy) below).

## Edit once, then re-render

1. Edit the template here (e.g. `PRII-APP.sh`, or the shared schema).
2. Re-render every consumer:
   ```
   python tools/render_federation_templates.py --all      # writes into ../<repo> siblings
   ```
   (or `--repo <program_id>` for one). Commit the regenerated files per repo.
3. Each repo's `template-drift.yml` CI runs
   `render_federation_templates.py --repo <id> --check` and **fails** if a repo's
   committed copy diverges from the template — so hand-editing a rendered file is
   caught, and "edit the template once" is enforced.

### Auto-propagation (optional)

`.github/workflows/federation-template-sync.yml` closes the write side: on a
change to `federation-templates/` (or manual dispatch) it re-renders every
producer, rebinds that producer's drift gate to the exact TheHub commit used for
the render, and **opens a sync PR** on any that drifted. The binding and rendered
payload therefore advance together instead of comparing new files against an
older frozen template snapshot. It's **dry-run by default**
— without an operator-provided `SYNC_PAT` secret (contents + PR write on the
producers) it only renders and prints the drift, opening nothing. Set `SYNC_PAT`
to turn on the automatic per-producer PRs. Until then, edit a template → run
`render_federation_templates.py --all` locally and commit per repo (each repo's
`template-drift.yml` keeps them honest). This is also the route by which action-pin
bumps reach the producers; see the next section.

## Action pins: Dependabot bumps the template, never a copy

The `uses:` pins in a rendered workflow belong to its template. If Dependabot bumps
one in a rendered copy, that repository stops matching the template and its
`template-drift.yml` fails once the bump merges. That happened in spiderweb-pr#410,
and thehub-pr#446 repaired it by hand. Two Dependabot configs keep every action
bump on the template side ([ADR 0015](../docs/adr/0015-action-pins-land-in-templates-first.md)):

| Repository | Config template | Actions ecosystem |
|---|---|---|
| The six producers | `baseline/dependabot.yml` | `directory: "/"` with `exclude-paths: ["{{RENDERED_WORKFLOWS}}"]`. The renderer fills in exactly the `.github/workflows/` files `targets.yaml` renders into that repository, so Dependabot never edits them there. Every other workflow, `template-drift.yml` included, keeps its bumps. |
| `thehub-pr` | `baseline/dependabot.hub.yml` | `directories: ["/", "/federation-templates/baseline", "/federation-templates/gui"]`, so the templates themselves are scanned. One group for version updates and one for security updates, neither limited by `update-types`, so each bump edits a template and the hub's own rendered copy in the same pull request. |

What happens when an action publishes a release:

1. The hub's weekly Dependabot run opens one pull request ("… across 3
   directories") that edits each affected template together with the hub's
   copy. The hub's drift gate stays green. Review and merge it like any other.
2. The merge touches `federation-templates/**`, so `federation-template-sync.yml`
   re-renders every producer and rebinds its `PRII_TEMPLATE_REF` to the merged
   commit. With `SYNC_PAT` set it opens a sync PR on each producer that drifted.
   Without it, it only prints the drift, and someone runs
   `render_federation_templates.py --repo <id> --template-ref <merged sha>` for
   each producer and opens those PRs.
3. Until a producer merges its sync PR, its drift gate keeps checking against its
   old pin, so it stays green on the old action version.

Keeping it working:

- A workflow template added outside `baseline/` and `gui/` needs its directory
  listed in `dependabot.hub.yml`; `tests/test_render_federation_templates.py`
  fails until it is.
- Dependabot parses every `*.yml` / `*.yaml` directly inside a scanned directory
  as a workflow, and one that does not parse fails the whole actions update. Keep
  each template valid YAML before rendering: write a list placeholder inside
  quotes, as `["{{RENDERED_WORKFLOWS}}"]` does.
- Never put a placeholder in a `uses:` line, so that Dependabot's edit to a
  template and to the hub's copy is the same edit.
- `exclude-paths` applies to version updates only. A Dependabot *security* PR in
  a producer can still edit a rendered workflow, and its drift gate will fail.
  Close it and let the bump come from the hub, whose security group edits the
  template and the hub's copy together.

`ignore` entries were the other option considered. They match a dependency by name
across a repository, not by file, and the same actions also run in workflows that
are not rendered (setup-uv in `ci.yml`, for one), so ignoring them would stop
legitimate bumps.

## Documentation stays true (docs-sync)

`baseline/check_docs_sync.py`, `baseline/docs-sync.yml`, `baseline/claude-settings.json`
and `baseline/CLAUDE.md` are one rule shipped as one unit
([ADR 0010](../docs/adr/0010-change-coupled-documentation-gate.md)): a change that makes a
document untrue must update it. The checker is byte-identical in every repo. What varies is
each repo's `.federation/docs-sync.json` — which docs cover which paths — and that file is
deliberately **not** templated. The pre-commit hook, the CONTRIBUTING section and the
PR-template line ride in the existing baseline files; `moneysweep-pr` and `spiderweb-pr` keep
their own copies of those and carry the same additions by hand.

Adding the rule to a repo: render it, write its manifest, seed couplings by replaying the
repo's recent history (a coupling that fires on routine work is noise — remove it, do not
waive it), then mark `docs-sync` as a required status check for `main`
(`tools/require_docs_sync.py --apply`, run by a repository administrator). Repository settings
are outside what a template can set, so until that last step the gate is `PROVISIONAL`.

## GUI rules (gui/)

`gui/` holds the federation GUI rule as rendered files
([ADR 0014](../docs/adr/0014-spoke-guis-are-complete-domain-apps.md),
[`docs/FEDERATION_GUI_STANDARD.md`](../docs/FEDERATION_GUI_STANDARD.md)):

| Template | Renders to | Set |
|---|---|---|
| `gui/check_gui_parity.py` | `scripts/check_gui_parity.py` | `_gui_rules` |
| `gui/test_gui_parity.py` | `tests/test_gui_parity.py` | `_gui_rules` |
| `gui/GUI_CAPABILITY_PARITY.md` | `docs/GUI_CAPABILITY_PARITY.md` | `_gui_rules` |
| `gui/gui-capability-parity.yml` | `.github/workflows/gui-capability-parity.yml` | `_gui_code` |

`gui/core-capabilities.json` is not rendered. It is the hub-owned list of reserved
capability ids, mirrored in the checker and kept in step by
`tests/test_gui_capability_schemas.py`.

Unlike every other target set, `_gui_rules` and `_gui_code` in `targets.yaml` are
**adoption lists**. Each producer already has its own copy of these files, and its
manifest may not yet satisfy the canonical checker, so a repository is added to a
set by the hub change that starts its adoption and not before. A repository that is
not listed is untouched by rendering, by its drift gate and by the sync workflow.

Listed today: `thehub-pr` in `_gui_rules`, and `moneysweep-pr` in both sets. Being
listed does not change a producer by itself: its drift gate renders from the hub
commit it has pinned, so the rendered files reach it only when its own adoption
change moves that pin to a commit that lists it.

The frontend Playwright config and the manifest-driven parity spec are not
templated yet. They differ per repository in ways that need a live backend to
verify (backend module name, seed and teardown scripts, environment, mobile
projects), so they are settled in the first producer's adoption change.

Before changing `gui/check_gui_parity.py`, run it read-only against every producer
checkout and compare with that producer's own result:

```
python3 federation-templates/gui/check_gui_parity.py --repo-root ../<repo>
```

A checker change may reduce a producer's gaps. It may not introduce one.

## Scope note

`desktop-build.yml` / `maintenance.yml` are intentionally **not** templated: they
carry per-repo variance (cron, paths, and spiderweb's different desktop model) and
were recently hand-tuned. Low ROI, higher risk — revisit only if they start
drifting in practice.
