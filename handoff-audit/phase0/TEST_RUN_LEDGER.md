# Test / Lint / Typecheck Ledger (T004 + T005)

Pinned commit `70765a2c4bd67470ee6b9892023f3ff4c80913b8` · Python 3.11.15 · pytest 9.1.1 · ruff 0.16.0 · mypy 2.3.0

## Results

| Suite | Command | Passed | Failed | Skipped | Result |
|---|---|---:|---:|---:|---|
| root (`tests/`) | `pytest -q` | 386 | 0 | 1 | **PASS** |
| `packages/prii_maintenance` | `pytest -q packages/prii_maintenance/tests` | 28 | 0 | 0 | **PASS** |
| `packages/prii_export_utils` | `pytest -q packages/prii_export_utils/tests` | 7 | 0 | 0 | **PASS** |
| `packages/prii_desktop` | `pytest -q packages/prii_desktop/tests` | 24 | 0 | 0 | **PASS** |
| **Total** | | **445** | **0** | **1** | **PASS** |
| schemas well-formed | `python -c "import json,glob;[json.load(open(f)) for f in glob.glob('schemas/*.json')]"` | — | — | — | **PASS** |
| lint | `ruff check src/hub tests` | — | — | — | **PASS** (All checks passed) |
| typecheck | `mypy src/hub` | — | — | — | **PASS** (40 files, no issues) |
| lockfile | `uv lock --check` | — | — | — | **PASS** |

## The single skip (not a failure, not a defect)

`tests/test_status_consistency.py:110` — *"no producer checkouts available for manifest cross-check."*
The test cross-checks the registry against sibling producer repos that are not present in this isolated
audit container. It skips cleanly by design. To exercise it, the 6 producer repos would need to be
checked out alongside the Hub.

## Warnings

- `tests/test_desktop_app_server.py:21` — StarletteDeprecationWarning about `httpx` + `starlette.testclient`.
  Upstream dependency deprecation only; non-blocking, no behavior impact.

## CI parity

CI `test` job runs the same `pytest -q` across Python 3.9/3.10/3.11/3.12; this audit reproduced 3.11 only.
The installed toolchain is newer than the pyproject floors (pytest 9 vs `>=7`, ruff 0.16 vs `>=0.4`,
mypy 2.3 vs `>=1.10`) and the suite is still fully green — strong forward-compatibility evidence, though
it does not replace the full CI matrix. The separate `server/frontend` JS suite (vitest + playwright
visual) is out of scope for this Python baseline.
