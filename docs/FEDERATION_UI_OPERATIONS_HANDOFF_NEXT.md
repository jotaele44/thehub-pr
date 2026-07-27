# Handoff — Federation UI-Only Operations, next session

The trust core is built and certified for TheHub's 12 enabled operations. This
document is what the next session needs to extend it to the 55 producer
operations, written from findings verified against the producer repositories
rather than from the design catalog.

Read `docs/FEDERATION_UI_OPERATIONS_CERTIFICATION.md` for what is already
certified and `docs/FEDERATION_UI_OPERATIONS_FAILURE_LEDGER.csv` for every open
item.

## What exists and can be reused

| Concern | Module | Notes |
|---|---|---|
| Signed policy, typed parameters, argv | `server/backend/federation_manager_operations.py` | Add a producer operation by giving it a `target`, `parameters`, and an `argv` list, then flipping `enablement` |
| Process supervision | `federation_manager_process.py` | Already handles all five execution kinds |
| Secrets, no readback | `federation_manager_secrets.py` | `inject_into_env` is the only value-moving path |
| File tokens, staging, preflight | `federation_manager_files.py` | Shapefile sets already modelled in `FILE_SET_FAMILIES` |
| Transactions and rollback | `federation_manager_transactions.py` | Six strategies built; three missing (below) |
| Receipts and gates | `federation_manager_receipts.py` | Chain and evaluator are producer-agnostic |
| Run orchestration | `federation_manager_runner.py` | Nothing in it is Hub-specific |
| UI | `src/pages/Operations.jsx` | Already lists all 68 and renders forms from the policy |

Regenerate the policy after editing `tools/build_operations_policy.py`:

```
python3 tools/build_operations_policy.py
python3 tools/evaluate_federation_gates.py --receipts <dir> --public-key <pem>
```

## Producer changes strictly required

Each needs a **draft** pull request on its own repository. Verified against the
current checkouts, not inferred.

1. **spiderweb-pr — `validate_schemas` (F019, confirmed and worse than stated).**
   `federation.json` declares `make validate-schemas`. The Makefile target is a
   backslash-continued inline `python -c` importing
   `integration/schema_validation.py:SchemaValidator` and asserting
   `len(schemas) >= 11`. It needs *both* `make` and inline code execution;
   neither is representable. Add `scripts/validate_schemas.py` with `--json`
   wrapping `SchemaValidator` (class at `integration/schema_validation.py:80`,
   `available_schemas()` at `:197`). The `make test-schemas` body is a usable
   interim: `pytest tests/test_schema_validation.py tests/test_new_schemas.py
   tests/test_satellite_source_manifest_schema.py`.

2. **aguayluz-pr — four manifest values are not commands at all.**
   `fetch_luma_live` carries trailing prose (`"(LIVE MiLUMA API; ToS-gated, see
   script header)"`), and `ingest_aee`, `build_municipios_geo`,
   `build_geo_boundaries` carry literal `<placeholder>` tokens. An adapter has
   nothing valid to parse. These must be corrected in the manifest before the
   operations can be decomposed.

3. **aguayluz-pr — `scripts/validate_repo.py` has no argparse at all.** Add
   argparse plus `--json`, or move `validation_gates` onto `aguayluz validate
   --json`; the console entry point already exists (`aguayluz = aguayluz.cli:app`).

4. **moneysweep-pr — `scripts/build_source_recovery_matrix.py` has no argparse**
   and hardcodes `reports/source_recovery_matrix.{csv,md}` and
   `reports/materialization_readiness.json`. Add `--root`/`--out`/`--check` to
   match its sibling builders.

5. **All six `setup` values are shell composites** (`[ -d ../thehub-pr ] || git
   clone ...; pip install ...`). They cannot be represented in any permitted
   execution form and are recorded as `composite_unresolved`, which the schema
   forbids on an enabled operation. They must be decomposed into declarative
   steps — acquire (pinned, checksummed), then install into a versioned
   directory, then promote by pointer swap.

Optional but cheap: add `--json` to the four text-only validators (ovnis
`validate_case_ledgers`, centinelas `validate_pr_grid`, skywatcher
`validate_airspace_export`, aguayluz `validate_repo`), and stop spiderweb's
`validate_export.py` writing `validation_report.json` *into the package it is
validating* — add `--report-out`.

## Handled centrally — no producer change needed

- **argv tokenization** for every `python3 scripts/X.py --flag value` form.
  All are already metacharacter-free and map directly onto `python_script`.
- **cwd pinning to the app root**, which is the correct fix for the surviving
  half of F020 (F026). `BuiltCommand.cwd` is already the app root.
- **Console-script routing** for centinelas (`centinelas ingest|classify|route|
  run|status`) and aguayluz (`aguayluz maintenance --mode audit`) — the only two
  producers with `[project.scripts]`.
- **Uniform `--json` injection** for the five `run_maintenance.py`, which all
  already accept `--json --no-write --fail-on-blocker`.
- **moneysweep's `.env`**: set all ten keys in the child environment.
  `scripts/config.py:561` consults `.env` only *after* `os.environ`, so
  injection wins without touching the file.
- **Packaging is not a blocker.** ovnis-pr has no `pyproject.toml` at all, and
  moneysweep-pr/skywatcher-pr have no `[project]` table, but every one of their
  commands is a script-path form covered by `python_script`.

## Rollback strategies still to build

Three, all named in `UNIMPLEMENTED_STRATEGIES`, which raises rather than
silently no-opping. G13 stays deferred until they exist:

- `dispatch_receipt_compensating_remove` — centinelas cross-repo routing.
  Compensation may remove only rows carrying the failed run's ID and must never
  touch pre-existing target data.
- `transactional_run_partition_restore` — centinelas full pipeline.
- `queue_run_partition_delete` — centinelas ingest queue.

`run_partition_restore` is built and is the right base for all three.

## Open questions to settle

- **`repo_federation_manifest_v2`.** The current schema declares
  `additionalProperties: {"type": "string"}` and describes the field as "Shell
  commands the Hub may invoke". A typed command form needs a schema bump plus
  matching updates to `federation-templates/` and
  `test_render_federation_templates.py`, which today do not cover
  `federation.json` at all. Deferred here because the signed policy supersedes
  the manifest for execution — decide whether the manifest should follow.
- **Durable receipt signing key** (F022). Currently ephemeral per manager
  process, so receipts stop counting as evidence after a restart. Safe
  direction, but a real deployment needs `ReceiptSigner.from_pem` and a
  persisted key.
- **The second, readable secret provider** at `src/hub/mcp_runtime/secrets.py:46`
  (F025). Predates this vector; decide whether it converges on the no-readback
  interface.
- **Windows credential writes** expose the value in argv (F021).
- **`moneysweep`'s `LDA_API_KEY`** appears in code but not in the manifest's
  `runtime_required_keys`.

## What still needs a macOS host

G07, G15, G16 and G22 cannot be produced anywhere else. They need a real
operator on a supported macOS target exercising the native picker, the Keychain
(including locked and denied-access states), and seven app launches with no
Terminal. Nothing in this repository can substitute for that.
