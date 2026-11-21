# Audits

## 2026-11-21 — Can the hub keep developing the federation? And the Launch Pad

**Scope:** the hub's write side toward producers (shared templates, pinned runtimes,
sync automation) and the Launch Pad in `packages/prii_desktop`.

### Hub → producer development path

| Mechanism | State | Finding |
|---|---|---|
| Template source and renderer (`federation-templates/`, `tools/render_federation_templates.py`) | Works | `thehub-pr` matches its templates; docs-sync is clean. |
| Producer drift gates (`template-drift.yml`) | Works, but blind to lag | Each producer compares itself with the hub commit *it* pinned (`PRII_TEMPLATE_REF`), so a gate stays green however old the pin is. |
| Propagation (`federation-template-sync.yml`) | **Dry run in practice** | Without `SYNC_PAT` every run succeeds and opens no PR. The Launch Pad pin move (10bca45) reached no producer. |
| Shared desktop runtime pin | **Lagging** | All five templated desktop producers ran prii-desktop `1313c77`, from before the Launch Pad; `PRII_TEMPLATE_REF`s were 38–114 hub commits behind `main`. `spiderweb-pr` manages its pin by hand (`git+…@dc79dc0`). |
| `prii_desktop` quality gates | Partial | Tests ran only in the path-filtered `desktop-build.yml`; no ruff/mypy, unlike the other packages. |

Changes made:

- `tools/federation_pin_report.py` reports each producer's prii-desktop pin, `PRII_TEMPLATE_REF`
  lag and Launch Pad adoption. The weekly `maintenance.yml` publishes it as a warning and an
  artifact.
- A dry-run sync that finds drift now emits a warning and a job-summary entry listing the
  files and the manual re-render command, instead of a quiet notice.
- `ci.yml` gains a `desktop-package` job (ruff, mypy, tests, and the hub's own
  `python -m prii_desktop launchpad --check`).
- prii-export-utils pins are unified on `0f62e4b`; the package is byte-identical at the old
  `7b9759f` pin.

Still the operator's decision: adding `SYNC_PAT` turns propagation on. Until then producer
updates are opened by hand, and the pin report shows what is outstanding.

### Launch Pad (prii-desktop 0.3.0 → 0.4.0)

Sound as designed: stdlib-only, strict declaration validation, secrets never written to disk,
constant-time passphrase check, write token removed from the URL by the frontend, and honest
about Guest not being a security boundary.

Defects found and fixed in 0.4.0:

1. **Session state leaked across Launch Pad restarts.** Restarts use `exec`, which inherits the
   environment. An Operator session's minted `PRII_WRITE_TOKEN`, a typed secret (for example
   spiderweb's `HF_TOKEN`) and option values survived into the next session, including a Guest
   one. The token was reused rather than minted afresh, and a secret left empty stayed set.
   Now `apply_session` keeps a ledger (`PRII_LAUNCHPAD_MANAGED` / `PRII_LAUNCHPAD_ORIGINAL`),
   `scrub_managed_environment` restores the shell's environment before every session and
   restart, and Guest withholds operator-only variables even when the shell exported them.
2. **An invalid `LAUNCHPAD` was reported as "pywebview unavailable".** The launcher then fell
   back to the browser and crashed there. It now shows an error screen in the window, logs to
   `launcher.log`, and exits with a clear message on headless starts.
3. **A second start did not say what it attached to.** The lock now records the access mode,
   and an Operator instance warns that writes from the browser are refused.
4. **There was no offline check.** `python -m prii_desktop launchpad --check` validates a
   declaration and its status provider. The rendered `tests/test_launchpad_declaration.py`
   runs it in every repo's test suite.

Rollout: each desktop producer moves to the 0.4.0 pin and declares its own `LAUNCHPAD`, with a
guest allowlist audited against its backend's non-GET routes, in one PR per producer.

---

## 2026-09-21 — Fed Repos: Backend & Frontend Completion Audit

**Date:** 2026-09-21  
**Branch:** `claude/completion-audit-fed-repos-3gkse9`  
**Scope:** All 7 federated repositories under `jotaele44`

---

## Summary

| Metric | Value |
|---|---|
| Repos audited | 7 |
| Backend complete (substantial) | 5 (moneysweep, aguayluz, skywatcher, thehub + partial spiderweb) |
| Frontend complete (rich) | 4 (centinelas, skywatcher, spiderweb, thehub) |
| Critical gaps | 4 items (centinelas BE, ovnis BE, spiderweb production.py, aguayluz generated/) |
| Moneysweep test suite | 2394 passing · 51.7% coverage (gate: 44%) |

---

## This Repo: thehub-pr

**Backend: Most complete** — 20+ modules, full federation orchestration, MCP API, Docker deployment.

Files: `main_core.py` (28KB), `federation_manager_operations.py` (27KB), `federation_manager_receipts.py` (27KB), `federation_manager_transactions.py` (24KB), `federation_manager_runner.py` (22KB), `federation_manager_api.py` (21KB), `seed_federation.py` (20KB), `federation_manager_secrets.py` (17KB), `federation_manager_files.py` (17KB), `notifications.py` (15KB), `federation_manager_artifacts.py` (12KB), `federation_manager.py` (11KB), `gis_proxy.py` (7.8KB), `mcp_api.py` (4.9KB), `admin_control_plane.py` (1.9KB).

Capabilities: Docker (Dockerfile + docker-compose.yml), MCP API integration, federation seeding, repository registry/runner, secret management.

**Frontend: Most comprehensive** — 35 pages (aggregates all 6 spoke repos), 15+ component subdirectories.

Pages include: AguaYLuz, Centinelas, MoneySweep, Ovnis, Skywatcher, Spiderweb (hub views for each repo), Dashboard, Operations, OperatorSettings, ResearchAssistant, GISWorkspace, FederationCrossoverWorkspace, Cases, Tasks, Gates, Sources, AppCenter, ModuleReadiness.

Component dirs: audit/, cases/, crossover/, dashboard/, exports/, feed/, github/, intelligence/, layout/, manager/, notifications/, overlap/, research/, shared/, tasks/, ui/.

**Note:** Gaps in centinelas and ovnis backends will surface as incomplete data in hub's Centinelas.jsx and Ovnis.jsx pages.

---

## Fleet-Wide Priority Actions

Since thehub aggregates all spoke repos, these fleet gaps affect hub views:

1. **HIGH** — centinelas: implement Entities/Matters/Pipeline/Signals/Sources backends
2. **HIGH** — ovnis: implement domain API modules; migrate to uv
3. **HIGH** — spiderweb: implement production.py entry point
4. **MEDIUM** — aguayluz: run code generation (generated/ is empty)
5. **MEDIUM** — moneysweep: complete production rebuild; merge PR3

---

See full fleet audit: https://claude.ai/artifact/G8dsMnxcTN8ouJaaQrULF2

*Audit date: 2026-09-21*
