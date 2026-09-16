# prii-doctor

Shared, manifest-driven diagnostics engine for PRII federation producers.

## Why this exists

A large share of what actually breaks in a PRII producer repo is external
and adversarial by nature: WAF-blocked APIs, JS-rendered government portals,
ToS-gated scrapes, manual operator file-drops, credentials whose *presence*
is checkable but whose *validity* is not. A naive health check either skips
these silently or, worse, reports a green PASS it cannot actually back up.

`prii-doctor` exists to make that failure mode structurally impossible. Every
check a producer declares carries an explicit `DiagnosabilityClass`
(`local-deterministic`, `presence-only`, `live-probe-best-effort`,
`not-automatable`) that bounds which statuses it is even allowed to report --
enforced by `CheckResult` itself at construction time, not left to convention.
A `not-automatable` check (a manual file-drop pipeline, a scrape the source's
own ToS discourages) can only ever report `INFO` with a recorded
last-known-state; it can never claim to have verified anything.

## Public API

```python
from pathlib import Path
from prii_doctor import run, print_table, to_gui_dicts

report = run(Path("/path/to/producer-repo"))
print_table(report)                 # CLI table, same shape as validate_repo.py
gui_rows = to_gui_dicts(report)     # {"label", "status", "detail", "class"} rows
```

`run()` reads `<repo_root>/.federation/doctor-checks.json` (schema:
`schemas/doctor-checks.schema.json`) and `<repo_root>/federation.json`, and
returns a `CheckReport`. A repo with no doctor manifest yet gets an empty
report -- not an error -- so this can be wired into every producer without
any producer regressing until it opts in with its own manifest.

## How it plugs in

- **Types** (`types.py`) generalize the shape of aguayluz-pr's
  `Gate`/`GateResult` pattern (`src/aguayluz/validation.py`) into a
  repo-agnostic form.
- **`delegate_subprocess`** (`runners.py`) is the portability layer: it
  shells out to whatever command a producer already declares in its own
  `federation.json:hub_callable_commands`, keyed by the manifest's
  `validation_entrypoint` field -- so it wraps aguayluz-pr's 8-gate table and
  moneysweep-pr's differently-shaped preflight output identically, without
  either producer changing its existing validation suite.
- **GUI surface**: `prii_desktop.setup_center.diagnostics()` calls
  `prii_doctor.run()` and appends `to_gui_dicts()`'s output to the list it
  already returns, so results appear on the existing native "Setup &
  Diagnostics" screen every desktop producer already ships -- no new GUI
  route, no new GUI-capability-parity surface area.
- **CLI surface**: each producer's own `scripts/doctor.py` is a thin shim
  calling `prii_doctor.run()` + `prii_doctor.print_table()`.

## Adding a check

Add an entry to the producer's `.federation/doctor-checks.json`. See
`schemas/doctor-checks.schema.json` for the full shape, and
`aguayluz-pr/.federation/doctor-checks.json` for a worked example derived
from that repo's real `waf_blocked_sources`/`runtime_required_keys` entries.
