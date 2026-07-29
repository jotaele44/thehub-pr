# Validator & Federation Readiness Ledger (T007 + T008)

Pinned commit `70765a2c4bd67470ee6b9892023f3ff4c80913b8`.

## T007 — Package & schema validators

| Check | Command | Result |
|---|---|---|
| Schema JSON well-formedness (CI parity) | `python -c "import json,glob;[json.load(open(f)) for f in glob.glob('schemas/*.json')]"` | **PASS** |
| Contract schema freeze | `python tests/test_schema_freeze.py` | **PASS** (no unauthorized schema drift vs `schemas/FROZEN.sha256`, 16 frozen schemas) |
| Package validator | `hub validate-package <built pkg>` on a package built by the `conftest.build_package` factory (entities/relationships/sources JSONL + manifest.json with honest sha256/record_count) | **VALID package** (exit 0) |
| Manifest validator | `hub validate-manifest` (producer `federation.json` → `repo_federation_manifest.schema.json`) | Covered by the green `tests/test_manifest.py` + `tests/test_validate.py` (11) suites; not re-fabricated here to avoid inventing a producer manifest. |

## T008 — Federation readiness rollup

`hub validate-federation --root . --json`:

- `hub`: thehub-pr · `producer_count`: **6** · `ready_count`: **0** (in this container)
- `by_blocker`: `{ "missing_checkout": 6 }`
- Exit code **1** (correct: not all producers ready).

All 6 producers report `checkout_present=false` / `manifest_present=false` because their repositories
are not cloned into this isolated Hub-only audit environment. The readiness engine
(`src/hub/federation_status.py`) classifies each correctly as `missing_checkout` and rolls up cleanly.

## Verdict

The validators and readiness rollup are **functionally correct** at the pinned commit. The zero
ready-count reflects the absent producer checkouts (an environment condition), not a Hub regression.
Full end-to-end readiness certification (producers present, packages materialized) is out of scope for
this Hub-only baseline and is tracked as a downstream item requiring the 6 producer repos.
