# Federation Code-Setup Completion-Gate Audit

**Vector:** `FEDERATION_CODE_SETUP_AUDIT → 6_PROGRAM_COMPLETION_GATE`
**Date:** 2026-06-28
**Hub:** `thehub-pr`
**Question:** Can Federation code setup be declared *finished* across all six programs?

**Decision: NO — not finished.** The Federation is in a late-stage
controlled-integration state: Hub scaffolding, producer manifests, the maintenance
schema, and PR-head CI are largely in place, but readiness flags are misaligned
across the Hub/producers, open PRs remain, and live-execution gates are still false
for most producers.

---

## How to read this document

Findings are tagged by evidence tier:

- **[VERIFIED]** — re-checked directly against live repo files during this audit
  (file path + field cited).
- **[CONNECTOR]** — carried from the connector-level pass (PR/CI state, other
  producers' declared blockers); not independently re-derived from a local run.
- **[NOT RUN]** — requires local execution (`pytest`, `ruff`, maintenance audit,
  Hub package validation) and was not runnable from the connector.

---

## How the Hub computes "live ready"

The Hub does not take readiness on faith. `src/hub/federation_status.py` assigns
each producer a `blocker_class`, returning `ready` **only** when all of:

1. `checkout_present` — producer workspace is checked out;
2. `manifest_present` — `federation.json` exists;
3. `manifest_valid` — passes `load_and_validate_manifest`;
4. `package_present` — a canonical export package exists at `export_path`
   (defaults to `exports/federation/`);
5. `package_valid` — `src/hub/validate.py::validate_package` returns no errors
   (manifest matches `federation_export_manifest.schema.json`, every file's
   `sha256` matches, **every JSONL row validates against its stream schema**,
   declared `record_count`s match);
6. `live_execution_ready` — the producer's own
   `federation_readiness_gate.ready_for_hub_live_execution == true`;
7. the registry `status:` is not one of `blocked` / `diagnostic` / `synthetic_only`.

The package at step 4 does **not** have to be committed by the producer: the Hub
**materializes it itself** via `hub fetch --run` (`src/hub/fetch.py::fetch_all`),
which clones each producer and runs its `hub_callable_commands.export_canonical`
through an allowlisted subprocess. So readiness is checked end-to-end with
`hub fetch --root ws --run` → `hub validate-federation --root ws --json`.

---

## 1. Scope & coverage

All six installed Federation repos were in scope.

| Program | Repo | Role | Covered |
|---|---|---|---|
| TheHub | `jotaele44/thehub-pr` | federation hub / aggregator | yes |
| MoneySweep | `jotaele44/moneysweep-pr` | public_money_intelligence_node | yes |
| Spiderweb | `jotaele44/spiderweb-pr` | spatial_operational_producer | yes |
| OVNIS / PRUFON | `jotaele44/ovnis-pr` | anomaly_intelligence_node | yes |
| AguaYLuz | `jotaele44/aguayluz-pr` | water_grid_monitoring_node | yes |
| Skywatcher | `jotaele44/skywatcher-pr` | airspace_intelligence_node | yes |

**[VERIFIED]** TheHub exposes `registry/producers.yaml` listing all five producers,
plus `schemas/`, `src/`, `server/`, `docs/`, and `tests/`.

---

## 2. Completion-gate matrix

| Gate | Status | Basis |
|---|---|---|
| 6/6 programs discovered | PASS | [VERIFIED] |
| 5/5 producer manifests present (`federation.json`) | PASS | [VERIFIED] for MoneySweep & OVNIS; [CONNECTOR] for the rest |
| Hub producer registry present | PASS | [VERIFIED] `registry/producers.yaml` |
| Hub maintenance/schema rollup present | PASS | [VERIFIED] `schemas/` + `docs/` present; [CONNECTOR] for rollup logic |
| All readiness flags aligned (Hub ↔ producers) | FAIL | [VERIFIED] OVNIS registry note vs. data (§4.2) |
| Source-of-truth counts aligned | FAIL → being fixed | [VERIFIED] MoneySweep drift (§4.1), resolved on `claude/federation-code-setup-audit-ffkp45` |
| Open PR queue clean | FAIL | [CONNECTOR] open/draft PRs across repos |
| All active CI green | PARTIAL | [CONNECTOR] MoneySweep PR #332 lint/pre-commit failing |
| Local gates executed | NOT RUN | [NOT RUN] |
| All live-execution gates true | FAIL | [VERIFIED]/[CONNECTOR] most producers `ready_for_hub_live_execution=false` |

---

## 3. Per-program state

| Program | Code setup | Manifest | Live gate | Notes |
|---|---|---|---|---|
| TheHub | partial | n/a (hub) | n/a | [VERIFIED] registry + scaffolding present; [CONNECTOR] draft PRs (#22 alerts, #23 INTSYS P0) open |
| MoneySweep | partial | present | `false` | [VERIFIED] source-count drift (now reconciled on this branch); [CONNECTOR] Tranche-B manual ingest + runtime keys block live exec |
| Spiderweb | partial | present | `false` | [CONNECTOR] discovery-ready; production export needs non-synthetic rows + Hub validation |
| OVNIS / PRUFON | near-complete | present | producer `true`; data supports it | [VERIFIED] 470 real cases, 0 synthetic; Hub registry note is stale; real gap is `export_canonical` still `--mode test` on main (§4.2) |
| AguaYLuz | near-complete | present | `true` (caveated) | [CONNECTOR] live-ready; outage granularity snapshot-grade; alert-stream split across paired PRs |
| Skywatcher | partial | present | `false` | [CONNECTOR] discovery-ready; live blocked on real FR24 capture + runtime proof |

---

## 4. Verified contradictions

### 4.1 MoneySweep source-count drift — [VERIFIED] (resolved on this branch)

`federation.json` (`source_truth`) and `reports/federation_source_status_reconciliation.json`
both declared **136 total / 90 automatable / 90 ready**, while the file both name as
ground truth — `reports/materialization_readiness.json` — declares **141 / 95 / 95**.
MoneySweep's own `federation_readiness_gate` lists *"source-count wording must stay
reconciled to reports/materialization_readiness.json truth"* as a blocking condition,
so the stale values were self-violating.

**Resolution:** reconciled to `141 / 95 / 95` on branch
`claude/federation-code-setup-audit-ffkp45` (both files), with a `historical_drift_notes`
entry recording the 136→141 change. No readiness flag changed
(`ready_for_hub_live_execution` remains `false`).

### 4.2 OVNIS readiness: data is real; the Hub registry note is stale — [VERIFIED]

The original "OVNIS↔Hub contradiction" was investigated in depth. The producer
manifest and the registry disagree:

- `ovnis-pr/federation.json`: `production_status: PRODUCTION`,
  `ready_for_hub_live_execution: true`, `blocking_conditions: []`.
- `thehub-pr/registry/producers.yaml`: OVNIS `status: ready_for_discovery`,
  comment *"live exec blocked: needs real case records in
  data/master/master_cases.jsonl (placeholder row only)"*.

**Evidence resolves it in the producer's favor — the registry note is wrong:**

- **[VERIFIED]** `data/master/master_cases.jsonl` holds **470 master records with
  zero `source_family == "placeholder"` (synthetic) rows** — real agency sourcing
  (U.S. Navy ×37, USAF, FAA, NASA, AARO, PR Police/FURA), evidence tiers T1–T4.
  The "placeholder row only" claim is stale.
- **[VERIFIED]** The registry comment also has **no effect in code**:
  `_blocker_class` only special-cases `status ∈ {blocked, diagnostic,
  synthetic_only}`, and OVNIS's value is `ready_for_discovery`. The comment is
  misleading documentation, not an enforced gate.
- **[VERIFIED]** `scripts/federation_export.py --mode production` fails if any row
  is synthetic; with 0 placeholder rows it would pass.

**The real remaining gap (code-only):** on `main`, OVNIS's
`hub_callable_commands.export_canonical` is still
`python3 scripts/federation_export.py --mode test`. When the Hub runs
`hub fetch --run`, it would therefore materialize a **test-mode** package that
bypasses the synthetic-row guard — so OVNIS would not legitimately clear the live
gate. **OVNIS PR #12** flips this single line to `--mode production` (verified in
its diff), which is exactly the fix — but #12 is `draft` and `mergeable_state:
dirty` (merge conflicts) and otherwise only touches dashboard shaping.

**Conclusion:** not a flag flip in either direction. To make OVNIS genuinely
live-ready and remove the contradiction: (a) land the `export_canonical` →
`--mode production` change (OVNIS PR #12, after resolving conflicts), and
(b) correct/refresh the stale Hub registry note. Then confirm with
`hub fetch --run` + `hub validate-federation` reporting `blocker_class: ready`.

### 4.3 AguaYLuz alert-stream split — [CONNECTOR]

The producer-side alert capability (AguaYLuz PR #14) depends on the Hub-side alert
schema/stream (TheHub PR #22). Both are draft. They should be resolved as a paired
migration to avoid a producer/Hub schema split.

### 4.4 Spiderweb / Skywatcher: CI green ≠ live-ready — [CONNECTOR]

Both have green PR-head CI but `ready_for_hub_live_execution: false`. The remaining
blockers are real-data/runtime proof (non-synthetic spatial rows for Spiderweb; real
FR24 capture and runtime intake proof for Skywatcher), not code defects. CI success
must not be read as live-execution readiness.

---

## 5. Required closeout order

Ordered, with risk class and whether each is code-only or live-data/operational.

| # | Action | Repo(s) | Class | Risk |
|---|---|---|---|---|
| 1 | Reconcile MoneySweep source counts (136→141, 90→95) | moneysweep-pr | code-only | low — **done on this branch** |
| 2 | Land OVNIS `export_canonical` → `--mode production` (PR #12, resolve conflicts) and refresh the stale Hub registry note for `ovnis-pr` | ovnis-pr + thehub-pr | code-only | medium — data already supports live; verify via `hub validate-federation` |
| 3 | Fix MoneySweep PR #332 lint / pre-commit failure | moneysweep-pr | code-only | low |
| 4 | Resolve TheHub #22 + AguaYLuz #14 as a paired alert-stream migration | thehub-pr + aguayluz-pr | code-only | medium — schema coupling |
| 5 | Review/merge TheHub #23 (INTSYS P0 frontend) if required for setup-complete | thehub-pr | code-only | medium |
| 6 | Split or deeply validate MoneySweep #331 before merge | moneysweep-pr | code-only | high — very large diff |
| 7 | Triage Skywatcher PR queue: #20 → #18 → #12 → #22 (#22 has explicit no-merge stop) | skywatcher-pr | mixed | medium |
| 8 | Validate Spiderweb #116 dataset or mark explicitly post-setup | spiderweb-pr | code-only | low |
| 9 | Run local maintenance audits + Hub package validation across all producers | all | live/operational | required for certification |

---

## 6. Verification still required — [NOT RUN]

The following were not runnable from the connector and remain prerequisites before a
final completion certificate:

```
python -m pytest -q
ruff check .
python scripts/run_maintenance.py --repo <repo> --mode audit --fail-on-blocker
hub fetch --root ws --run          # materialize producer packages
hub validate-federation --root ws --json   # blocker_class per producer
hub validate-package <producer-export>
hub aggregate
```

TheHub expects producer maintenance reports at `reports/maintenance/latest.json`,
validated against the maintenance report schema (requires `repo`,
`maintenance_version`, `findings_count`, `critical_count`, `promotion_blocked`).

---

## 7. Conclusion

Code setup is **not finished** at the federation level. One P0 (MoneySweep
source-count drift) is resolved on this branch; the OVNIS export-mode gap + stale
registry note, the open PR queue, the MoneySweep #332 CI failure, and the remaining
producers' live-execution gates remain. Do not declare completion until connector
state, manifest truth, PR state, and local gate execution all align.
