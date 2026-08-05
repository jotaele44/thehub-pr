# handoff-audit — THEHUB Dual-Engine Migration

Audit deliverables for the vector `CLOSE_THEHUB_DUAL_ENGINE_CRITICAL_BASELINE_GAPS_v0_4` from the
Claude Engineering Handoff v2. Produced against the pinned Hub commit
`70765a2c4bd67470ee6b9892023f3ff4c80913b8`.

**This tree adds only audit artifacts. No existing Hub source, test, or schema was modified. HOLD on
code movement is retained.**

## Contents

### `phase0/` — Baseline certification (the authorized immediate task)
Start with **`BASELINE_CERTIFICATION.md`** (opening state report + summary), then:
- `BASELINE_COUNTS.json` + `PINNED_TREE_INVENTORY.tsv` — exact object counts and per-blob SHA inventory (T001/T002)
- `RUNTIME_LOCK.json` + `pip_freeze.txt` — locked runtime (T003)
- `TEST_RUN_LEDGER.{json,md}` + `LINT_TYPECHECK_LEDGER.md` — Hub suite/lint/typecheck (T004/T005)
- `CLI_SMOKE_LEDGER.md` + `VALIDATOR_READINESS_LEDGER.md` — CLI/validators/readiness (T006–T008)
- `SPATIAL_RAG_REPRODUCTION_LEDGER.md` + `spatial_rag_pip_freeze.txt` — DB/PostGIS/pgvector reproduction (T009–T012)
- `PHASE_1_ACCEPTANCE_GATES_UPDATED.csv` — gate status with evidence
- `FAILURE_LEDGER.md` — closure status + residual items
- `HASH_MANIFEST.sha256` — reproducible hashes over every artifact

### `phase1-design/` — Phase-1 contract DESIGN docs (design only, no implementation)
Produced under the user's explicit in-session authorization. **No code, no code movement.**
- `CONTRACTS_DESIGN.md` — index, versioning, component-ledger receipts
- `schemas/*.v1.schema.json` — 9 draft-2020-12 contract schemas (drafts; not installed/frozen)
- `INTERFACES_DESIGN.md`, `SECURITY_CONTRACTS_DESIGN.md`, `TEST_PLAN_DESIGN.md`

### `upgrade-audit/` — Recommendable features, bug fixes, dependency & CI upgrades
Read-only audit findings. **RECOMMENDATIONS ONLY — nothing applied; HOLD retained.**
- `UPGRADE_AUDIT.md` — prioritized (bugs/correctness · security · deps/tooling/CI · features), each
  item with `file:line`, failure scenario, fix, HOLD-safe flag, effort, and Phase-1-enabler tag
- `UPGRADE_FINDINGS.csv` — machine-readable index of every finding

### `architecture/` — Architecture overview + diagrams
- `ARCHITECTURE_OVERVIEW.md` — two GitHub-native Mermaid diagrams (three-layer/two-sided model with the
  certified-snapshot boundary; Spatial-RAG donor → engine-split mapping) + prose tie-in to the baseline

## Verify

```bash
sha256sum -c handoff-audit/phase0/HASH_MANIFEST.sha256
git status --short   # expect only additions under handoff-audit/
```

## Authorization

Audit-first, evidence-bound, non-destructive. The Spatial-RAG package is a **capability donor, not a
merge unit**. Phase-1 *implementation* remains gated on an explicit human authorization change after
review of this evidence.
