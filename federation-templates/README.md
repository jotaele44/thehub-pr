# federation-templates — canonical shared boilerplate

Single source of truth for the non-Python boilerplate that every PRII repo used
to copy: the `Fix-Gatekeeper.command` and `PRII-<APP>.{command,bat,sh}` launchers,
`requirements-desktop.txt` (desktop producers), and the shared
`schemas/federation_export_manifest.schema.json` contract.

`{{APP_SLUG}}` is the only placeholder. Per-repo slugs live in
`producers.vars.yaml`; which template renders where lives in `targets.yaml`.

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
producer and **opens a sync PR** on any that drifted. It's **dry-run by default**
— without an operator-provided `SYNC_PAT` secret (contents + PR write on the
producers) it only renders and prints the drift, opening nothing. Set `SYNC_PAT`
to turn on the automatic per-producer PRs. Until then, edit a template → run
`render_federation_templates.py --all` locally and commit per repo (each repo's
`template-drift.yml` keeps them honest).

## Scope note

`desktop-build.yml` / `maintenance.yml` are intentionally **not** templated: they
carry per-repo variance (cron, paths, and spiderweb's different desktop model) and
were recently hand-tuned. Low ROI, higher risk — revisit only if they start
drifting in practice.
