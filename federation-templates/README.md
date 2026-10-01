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
where lives in `targets.yaml`.

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
`template-drift.yml` keeps them honest).

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
waive it), then mark `docs-sync` as a required status check for `main`. Repository settings
are outside what a template can set, so until that last step the gate is `PROVISIONAL`.

## Scope note

`desktop-build.yml` / `maintenance.yml` are intentionally **not** templated: they
carry per-repo variance (cron, paths, and spiderweb's different desktop model) and
were recently hand-tuned. Low ROI, higher risk — revisit only if they start
drifting in practice.
