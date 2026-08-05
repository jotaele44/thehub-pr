# Failure Ledger (Phase 0)

Per `07_CLAUDE_MASTER_PROMPT.md`: *"If any critical gap cannot be closed, produce a failure ledger and
retain HOLD."*

## Critical baseline gaps — closure status

| # | Critical blocker (00_EXECUTIVE_OVERVIEW) | Status | Evidence |
|---|---|---|---|
| 1 | Complete recursive pinned `thehub-pr` tree not independently certified | **CLOSED** | `PINNED_TREE_INVENTORY.tsv` (460 blobs+SHA at HEAD==pinned), `BASELINE_COUNTS.json` |
| 2 | Exact baseline counts incomplete | **CLOSED** | `BASELINE_COUNTS.json` (all 6 previously "counts_not_verified" now certified) |
| 3 | Pinned Hub test suite not executed in audit env | **CLOSED** | `TEST_RUN_LEDGER.*` — 445 passed / 1 skipped; ruff+mypy clean |
| 4 | Spatial-RAG PostgreSQL/PostGIS/pgvector integration not reproduced | **CLOSED** | `SPATIAL_RAG_REPRODUCTION_LEDGER.md` — 149 tests pass on live DB; migrations idempotent x2 |

**No critical baseline gap remains open.** HOLD on code movement is retained **by policy**, not by an
unclosed gap.

## Residual items (non-blocking; not critical baseline gaps)

These do not block baseline certification but are recorded for the next authorization decision:

1. **CI matrix parity partial** — reproduced on Python 3.11 only; CI runs 3.9/3.10/3.11/3.12. The
   installed toolchain exceeds pyproject floors and is green (forward-compat signal), but full-matrix
   confirmation is outstanding.
2. **One environmental test skip** — `tests/test_status_consistency.py:110` (no producer checkouts).
   Full federation readiness (T008 end-to-end) needs the 6 producer repos checked out.
3. **Spatial-RAG dependency gaps** — `requirements.txt` omits 3 imported deps (`tenacity`,
   `geoalchemy2`, `pgvector`); reproduced on PostgreSQL 16 vs compose's pinned 15; `CREATE EXTENSION
   postgis` needs superuser. Details in `SPATIAL_RAG_REPRODUCTION_LEDGER.md`. Relevant only if/when the
   package is adopted as a capability donor — it is **not** a merge unit.
4. **Handoff outer-zip checksum mismatch** — the outer `.zip.sha256` (`63bf11…`) does not match the
   uploaded archive (`ac51dc…`); all 32 inner files verify against the internal manifest, so contents
   are intact (re-compression only).

## Authorization outcome

Baseline certification is **COMPLETE**. Per the handoff, Phase-1 **implementation** remains gated on an
explicit human authorization change after review of this gate evidence. Phase-1 **design** artifacts
(`../phase1-design/`) were produced under the user's explicit in-session authorization and contain no
implementation or code movement.
