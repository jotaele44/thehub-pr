# Phased Backlog

Phase 0 audit deliverable. Companion to [ADR 0003](../adr/0003-evidence-intelligence-control-plane.md).

Migration proceeds by extraction (per [`COMPONENT_MIGRATION_MATRIX.md`](COMPONENT_MIGRATION_MATRIX.md)),
never a big-bang merge. Each phase restates its own non-goals explicitly — carrying forward the
mission's non-goals list rather than assuming they apply only to Phase 0.

| Phase | Content | Entry gate | Exit gate |
|---|---|---|---|
| **0 — Audit** (this deliverable) | 13 design docs + ADR 0003 | Package hygiene findings and both codebase inventories gathered (done — see [`READINESS_REPORT.md`](READINESS_REPORT.md)) | All 13 docs + ADR reviewed and merged; `READINESS_REPORT.md`'s go/no-go checklist passes |
| **1 — Contracts** | New frozen schemas added to `schemas/` (`federation_evidence_item`, `federation_claim`, `federation_snapshot`, `federation_retrieval_profile`, `federation_entity_identity_decision`); `pyproject.toml` extras added (`rag`/`intelligence`/`spatial`/`ocr`) — **no runtime code wired to them yet**; `benchmarks/corpus/` populated with real labeled queries per [`EVALUATION_CORPUS_SPEC.md`](EVALUATION_CORPUS_SPEC.md) | Phase 0 exit gate met | New schemas pass `tests/test_schema_freeze.py`; extras install cleanly in CI; corpus has enough labeled queries to make every category in `EVALUATION_CORPUS_SPEC.md` non-empty |
| **2 — Read-only adapter** | Evidence Engine ingestion pipeline + snapshot lifecycle built; read-only Intelligence Engine retrieval against a real `ACTIVE` snapshot; wired in as a new MCP capability behind `PolicyEngine`, per [`API_CONTRACT.md`](API_CONTRACT.md) | Phase 1 exit gate met | [`PARITY_GATES.md`](PARITY_GATES.md) Phase-2 metrics run against the populated corpus and meet threshold; `compute_snapshot_gate()` correctly blocks seeded bad data; HyDE verified off by default in every shipped profile |
| **3 — Dual-run** | Control Plane exercises the abstention contract and access-classification enforcement under realistic query load; soak period for reproducibility | Phase 2 exit gate met | No regression vs. Phase 2 parity numbers over the soak period; [`SECURITY_MODEL.md`](SECURITY_MODEL.md) checklist passes in full |
| **4 — UI parity** | `server/frontend` (React/Vite — not spatial-rag's Next.js) gains evidence-tier, claim-ledger, and abstention-state views | Phase 3 exit gate met | UI renders evidence tiers (visibly distinguishing `machine_provisional`), claim ledger, and abstention states; existing `frontend-visual` Playwright CI job extended to cover the new views and green |
| **5 — Cutover** | `mcp_runtime/adapters/documents.py`'s substring-search capability superseded by Intelligence Engine retrieval (per [`DUPLICATION_REGISTER.md`](DUPLICATION_REGISTER.md) row 1); any exploratory-only paths retired | Phase 4 exit gate met | Full parity + security sign-off; follow-up ADR ratifying general availability |

## Non-goals restated per phase

Phase 1's non-goals include: no live database provisioned, no `docker-compose.yml` service added
(even though the extras split is specified in [`TARGET_REPO_TREE.md`](TARGET_REPO_TREE.md), actually
wiring a multi-service compose file waits for Phase 2). Phase 2's non-goals include: no producer
crawler logic moves into the Hub, no automatic entity merging (only the reversible
`entity_identity_decision` flow), no autonomous conclusions surfaced without a claim ledger entry.
Every phase inherits the full non-goals list from [`READINESS_REPORT.md`](READINESS_REPORT.md) unless
a specific phase entry above narrows it further — none do; the list is a floor, not a per-phase menu.
