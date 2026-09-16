# Federation GUI Data-Path Audit — Exact-Head Status Addendum

Date: 2026-08-23

This addendum supersedes only the **implementation-status wording** in `FEDERATION_GUI_DATA_PATH_AUDIT_2026-08-23.md`. It does not replace that document's frozen 44-command denominator, source findings, or per-command audit.

## Denominator

Current five-producer `hub_callable_commands` denominator remains:

- Aguayluz: 12
- Spiderweb: 6
- Skywatcher: 6
- OVNIS/PRUFON: 7
- MoneySweep: 13
- total: **44**
- accounted: **44**
- unexplained command residue: **0**

This is bounded exhaustion of those declared commands only; universal executable exhaustion is not claimed.

## Control-plane implementation state

TheHub draft PR #197 now contains:

- registry + producer-manifest repository identity binding;
- per-repository execution contexts routed from signed `operation.repo`;
- whole-producer-root write auditing for producer runners;
- immutable artifact byte objects;
- separate per-run artifact registration records so BYTE identity is not conflated with SOURCE_MANIFESTATION identity;
- validator-gated artifact registration;
- atomic ACTIVE pointers and registered-object rollback;
- authenticated repository/data-health API;
- GUI repository health cards and Fetch/Export/Audit/Repair shortcuts derived from the signed operation policy rather than command strings;
- positive/negative tests for identity contradiction, workspace escape, failed validation, ACTIVE preservation, rollback, directory member identity, and byte-identical/distinct-run manifestations.

No producer operation is enabled by this vector. That is deliberate: current signed-policy `expected_outputs` entries are semantic labels (for example `test canonical package`), not complete physical output bindings. The runner cannot safely infer activation paths from those labels. Runner→ArtifactStore registration/activation therefore remains **OPEN/BLOCKED pending signed physical-output contracts** rather than being implemented heuristically.

Retry also remains bounded: existing GUI re-run is available, but automatic replay of operations containing one-use file tokens is not safe without a new token/input contract. No generic retry endpoint is promoted.

Zero-terminal certification remains OPEN because the manager host still exposes a browser-console session bootstrap path and browser file-token selection still depends on the native picker integration.

## Producer repair status

### Spiderweb PR #290

The command-representation repair is exact-head green: `validate_schemas` is now represented by a non-shell machine-readable Python script rather than `make` plus inline `python -c` on the repair branch. CI, smoke, template drift, Semgrep, secret scan, and CodeQL passed on the inspected exact head.

Broader Spiderweb GUI-data-path state remains **OPEN** because the PPP geometry lane still documents a conditional sibling MoneySweep checkout read, and producer write outputs are not yet tied to signed physical artifact activation contracts.

### Aguayluz PR #188

The first argparse design was rejected by Aguayluz's GUI-parity ratchet as a new unpaired CLI surface. That result is preserved as SUPERSEDED implementation evidence rather than baseline-normalized away.

The current branch instead extends the existing `scripts/validate_repo.py` executable identity with a strict `--json` mode and no second CLI framework surface. Exact-head revalidation is required before the repair is promoted.

Aguayluz remains **BLOCKED** overall by placeholder-bearing ingest/build declarations, `/tmp` defaults that require managed input/output replacement, the explicit MiLUMA ToS/WAF authorization gate, and missing signed physical output→activation contracts.

### MoneySweep PR #495

The first wrapper design was rejected by MoneySweep's GUI-parity ratchet as a new unpaired analysis/CLI surface and also exposed a formatting failure. Those results are preserved as SUPERSEDED.

The current branch deletes that wrapper and parameterizes the existing `scripts/build_source_recovery_matrix.py` executable identity in place with strict `--root`, `--out`, `--check`, and `--json` handling. The selected root is threaded through registry, preflight, output-presence, and summary reads. `--check` regenerates in an isolated temporary directory and byte-compares expected outputs without overwriting them.

On the current redesigned head, lint, pre-commit, type check, promotion guard, production-status gate, diagnostic smoke, template drift, secret scan, Semgrep, lockfile drift, and top-form reproducibility were green at the latest inspection; broader suites/parity were still running at that point.

MoneySweep remains **BLOCKED** overall by non-production diagnostic status, missing/manual/authorized source bytes and credentials/portal blockers, multi-output activation semantics, and signed physical output contracts.

## Hub exact-head gate adjudication

On Hub PR #197's inspected head, Hub CI, desktop build, CodeQL, Federation Semgrep, Secret scan, and Federation template drift passed.

`Federation pickup bounded MAX` failed in the **current remote SHA preservation assertion**, after the MAX execution itself completed with:

- bounded exhaustion: true;
- ready residue: empty;
- repository arithmetic: `7=7`;
- universal exhaustion claim: false.

The failure is a TIME/SNAPSHOT contradiction: the frozen Aguayluz expected main SHA no longer equals current Aguayluz `main`. As a result, the current bounded classification is `PASS=2, OPEN=3, BLOCKED=3`, while the workflow still asserts the older `PASS=2, OPEN=4, BLOCKED=2` vector count and corresponding repository counts.

The frozen producer snapshot is **not mutated in this vector** merely to make CI green. A new snapshot must be intentionally frozen after current producer heads are adjudicated; otherwise historical evidence would be overwritten by a mutable-source update.

## Current scoped certification

| Scope | State |
|---|---|
| 44-command audit arithmetic | **PASS** |
| Spiderweb command-representation repair | **PASS on inspected exact head; unmerged** |
| Aguayluz validation repair | **PROVISIONAL pending current exact-head completion** |
| MoneySweep matrix repair | **PROVISIONAL pending current exact-head completion** |
| Skywatcher production GUI path | **BLOCKED** |
| OVNIS/PRUFON GUI write/activation path | **OPEN** |
| TheHub repository binding/runtime routing | **PROVISIONAL** |
| TheHub ArtifactStore primitive | **PROVISIONAL** |
| Runner→validated-artifact registration/activation | **BLOCKED by absent signed physical-output contracts** |
| Generic automatic retry | **OPEN; unsafe for one-use file-token operations without new contract** |
| Zero-terminal production path | **OPEN/BLOCKED by native session bootstrap + picker integration** |
| Full Vector A certification | **NOT CERTIFIED** |
| Full Vector B bounded audit | **PASS for accounting; repo-specific remediation states preserved** |
