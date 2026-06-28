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
| All readiness flags aligned (Hub ↔ producers) | FAIL | [VERIFIED] OVNIS contradiction (§4.2) |
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
| OVNIS / PRUFON | near-complete | present | producer `true` / Hub `discovery` | [VERIFIED] manifest↔registry contradiction (§4.2) |
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

### 4.2 OVNIS ↔ Hub readiness contradiction — [VERIFIED] (open decision)

- `ovnis-pr/federation.json`: `production_status: PRODUCTION`,
  `ready_for_hub_live_execution: true`, `blocking_conditions: []`.
- `thehub-pr/registry/producers.yaml`: OVNIS `status: ready_for_discovery`,
  comment *"live exec blocked: needs real case records in
  data/master/master_cases.jsonl (placeholder row only)"*.

The registry header states each producer's own flag is authoritative, yet the Hub's
status line contradicts it. **This is an open decision** — whether OVNIS is truly
live-ready (then the Hub status is stale) or still scaffold-only (then the producer
manifest overstates readiness). It is **not** resolved by this branch; a human
authority call is required before editing either side.

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
| 2 | Resolve OVNIS live-readiness contradiction (one side becomes authoritative) | ovnis-pr + thehub-pr | code-only + decision | medium — needs human call |
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
hub validate-package <producer-export>
hub aggregate
```

TheHub expects producer maintenance reports at `reports/maintenance/latest.json`,
validated against the maintenance report schema (requires `repo`,
`maintenance_version`, `findings_count`, `critical_count`, `promotion_blocked`).

---

## 7. Conclusion

Code setup is **not finished** at the federation level. One P0 (MoneySweep
source-count drift) is resolved on this branch; the OVNIS↔Hub contradiction, the
open PR queue, the MoneySweep #332 CI failure, and the live-execution gates remain.
Do not declare completion until connector state, manifest truth, PR state, and local
gate execution all align.
