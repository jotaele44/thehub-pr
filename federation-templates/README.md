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

Cross-repo auto-propagation (opening the per-repo PRs automatically on a template
change) is the operator-gated hop in `.github/workflows/mcp-cross-repo-sync.yml`
(`SYNC_PAT`); until run, drift-check simply turns those repos red until they are
re-rendered.

## Scope note

`desktop-build.yml` / `maintenance.yml` are intentionally **not** templated: they
carry per-repo variance (cron, paths, and spiderweb's different desktop model) and
were recently hand-tuned. Low ROI, higher risk — revisit only if they start
drifting in practice.
