# THEHUB Dual-Engine Migration — Phase 0 Baseline Certification

**Vector:** `CLOSE_THEHUB_DUAL_ENGINE_CRITICAL_BASELINE_GAPS_v0_4`
**Pinned Hub commit:** `70765a2c4bd67470ee6b9892023f3ff4c80913b8` (== repo HEAD this session)
**Date:** 2026-07-25

## Opening state report (per 06_SESSION_RESTART_INSTRUCTIONS.md)

```text
MISSION:               Continue the THEHUB dual-engine migration (Control Plane / Evidence Engine /
                       Intelligence Engine) audit-first; certify the baseline before any code movement.
ACTIVE_VECTOR:         CLOSE_THEHUB_DUAL_ENGINE_CRITICAL_BASELINE_GAPS_v0_4
PINNED_INPUTS:         thehub-pr @ 70765a2c (verified) · spatialragv2.zip sha256 cd3b78f… (verified)
CURRENT_GATE_STATUS:   P1-G01 PASS · G02 PASS · G03 DESIGN_READY · G04 DESIGN_READY · G05 DESIGN_READY ·
                       G06 DESIGN_READY · G07 DESIGN_READY · G08 DESIGN_READY · G09 PASS · G10 PASS
AUTHORIZED_SCOPE:      audit · baseline certification · contract design · test design
PROHIBITED_ACTIONS:    code movement · direct ZIP merge · automatic entity merge · canonical mutation ·
                       HyDE default · applying Spatial-RAG SQL to the Hub · Phase-1 implementation
UNRESOLVED_CRITICALS:  none (all 4 critical baseline blockers CLOSED — see FAILURE_LEDGER.md)
READINESS:            Baseline certified. Phase-1 IMPLEMENTATION remains gated on explicit human
                       authorization after review of this evidence. HOLD on code movement retained.
```

## What was done

This session had what the original audit lacked: a **complete pinned checkout** (HEAD == the pinned
commit) and a container able to run PostgreSQL. That let the four critical baseline gaps — previously
BLOCKED only because the author "could not clone GitHub in the isolated container" — be closed directly.

| Task | Description | Result | Artifact |
|---|---|---|---|
| T001/T002 | Pinned tree + exact counts | **DONE** | `PINNED_TREE_INVENTORY.tsv`, `BASELINE_COUNTS.json` |
| T003 | Locked runtime | **DONE** | `RUNTIME_LOCK.json`, `pip_freeze.txt` |
| T004 | Hub unit tests | **445 passed / 1 skipped** | `TEST_RUN_LEDGER.{json,md}` |
| T005 | Lint + typecheck | **ruff + mypy clean** | `LINT_TYPECHECK_LEDGER.md` |
| T006 | CLI smoke (read-only) | **13/13 subcommands OK** | `CLI_SMOKE_LEDGER.md` |
| T007 | Package + schema validators | **VALID / freeze OK** | `VALIDATOR_READINESS_LEDGER.md` |
| T008 | Federation readiness rollup | **runs correctly** | `VALIDATOR_READINESS_LEDGER.md` |
| T009–T012 | Spatial-RAG DB/PostGIS/pgvector reproduction | **149 tests pass on live DB; migrations idempotent ×2** | `SPATIAL_RAG_REPRODUCTION_LEDGER.md` |

Full gate detail: `PHASE_1_ACCEPTANCE_GATES_UPDATED.csv`. Unclosed/residual items: `FAILURE_LEDGER.md`.

## Certified baseline (headline numbers)

460 tracked files · 99 dirs · 134 Python modules · root test suite **445 pass / 1 skip** (346 `test_`
functions, hermetic) · **16** JSON schemas under `schemas/` (17 incl. one templates duplicate) · **0**
SQL migrations (inline `CREATE TABLE IF NOT EXISTS`, no framework) · **13** CLI subcommands · **23** HTTP
route decorators (22 API + SPA fallback) · **31** declared frontend routes / 28 page components · **6**
producers · **8** canonical streams.

## Findings surfaced during certification

1. Spatial-RAG `requirements.txt` omits 3 imported deps (`tenacity`, `geoalchemy2`, `pgvector`).
2. Spatial-RAG migrations reproduce on PostgreSQL **16** (compose pins **15**); `CREATE EXTENSION
   postgis` requires superuser.
3. Handoff **outer**-zip checksum mismatch (`63bf11…` vs uploaded `ac51dc…`) — contents intact, all 32
   inner files verify against the internal manifest.

None of these block baseline certification; all are recorded in `FAILURE_LEDGER.md`.

## Authorization statement

The Spatial-RAG package remains a **capability donor, not a merge unit**. No production code was moved,
merged, refactored, or deleted; no Spatial-RAG SQL was applied to the Hub; HyDE stays disabled; the
existing Hub deterministic correlation remains authoritative. This deliverable **adds only** the
`handoff-audit/` tree.

**HOLD on code movement is retained.** Baseline certification is complete; Phase-1 *implementation*
begins only when a human explicitly authorizes it after reviewing this gate evidence. The Phase-1
**design** artifacts under `../phase1-design/` were produced under the user's explicit in-session
authorization and are documents only.

## Reproducibility

Every produced artifact is hashed in `HASH_MANIFEST.sha256`. Verify with
`sha256sum -c handoff-audit/phase0/HASH_MANIFEST.sha256`.
