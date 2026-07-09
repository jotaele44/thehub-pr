# MCP Registry Release Checklist
## Purpose
This checklist governs release readiness for TheHub MCP registry changes.
## Pre-Merge Checks
- [ ] All MCP manifests validate.
- [ ] External MCP candidate matrix validates.
- [ ] Pytest MCP registry tests pass.
- [ ] CI passes on pull request.
- [ ] No secrets are committed.
- [ ] No raw sensitive data is present.
- [ ] No confirmed anomaly language is present.
- [ ] All project manifests use `read_only` default.
- [ ] All global capabilities have `version_pin`.
- [ ] All external MCPs remain adapters, not authorities.
## Version Pin Review
- [ ] Each active capability has a pinned version.
- [ ] `pending-evaluation` is allowed only for pilot or conditional adapters.
- [ ] Deprecated adapters are not referenced by active project manifests.
- [ ] Version changes are documented in PR body.
## Secret Scan
Search for:
- `api_key`
- `token`
- `password`
- `secret`
- `bearer`
- `.env`
- private key material
No live credentials may be committed.
## Provenance Review
- [ ] Source lineage is required for all adapter outputs.
- [ ] Candidate matrix identifies authority level.
- [ ] Candidate matrix identifies provenance support.
- [ ] External MCP outputs must be reproducible or downgraded.
## Project Manifest Sync
Verify manifests exist for:
- [ ] Skywatcher
- [ ] Ovnis
- [ ] Spiderweb
- [ ] Centinelas
- [ ] MoneySweep
- [ ] AguaYLuz
## Policy Gate Review
Confirm:
- [ ] TheHub remains the control plane.
- [ ] Project repos declare capabilities only.
- [ ] Write actions are explicitly listed.
- [ ] Default policy remains read-only.
- [ ] Confirmed anomaly language remains blocked.
## Rollback Plan
If CI fails after merge:
1. Revert the merge commit.
2. Restore the last passing `capability_registry.yaml`.
3. Restore last passing project manifests.
4. Re-run MCP validation CI.
5. Open follow-up issue documenting failure mode.
## Post-Merge Checks
- [ ] Confirm workflow runs on `main`.
- [ ] Confirm registry files are visible in repo.
- [ ] Confirm future PRs touching `mcp/**` trigger validation.
- [ ] Update any downstream project documentation if capability names changed.
