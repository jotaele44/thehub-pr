# Lint & Typecheck Ledger (T005)

Pinned commit `70765a2c4bd67470ee6b9892023f3ff4c80913b8`.

| Tool | Version | Command (CI parity) | Config | Result |
|---|---|---|---|---|
| ruff | 0.16.0 | `ruff check src/hub tests` | `[tool.ruff] target-version=py39`, `lint.select=["E4","E7","E9","F"]` | **PASS** — All checks passed! |
| mypy | 2.3.0 | `mypy src/hub` | `python_version=3.10`, `ignore_missing_imports=true`, `disable_error_code=["import-untyped"]` | **PASS** — no issues in 40 source files |

Sub-package CI jobs additionally run `ruff check packages/<name>` and `mypy packages/<name>/src`
(their `pytest` suites are recorded green in `TEST_RUN_LEDGER.md`). The lint selection is intentionally
narrow (pyflakes `F` + a few pycodestyle error classes), matching the repo's committed configuration.
