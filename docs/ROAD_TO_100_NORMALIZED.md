# TheHub-PR — Normalized Road to 100 Status

**Governance version:** `road_to_100_normalization_v0_3`
**Audit date:** 2026-07-27
**Evidence boundary:** repository `main`, producer registry, canonical federation documents, `docs/ROAD_TO_100.md`, `docs/MATURITY_AUDIT.md`, and recorded executed baselines.
**Status mutation:** none. This document does not change producer readiness, Hub status, or any federation gate.

## Normalized scorecard

| Metric | Value | Interpretation |
|---|---:|---|
| Implemented scope | **90% — local Hub code only** | The control-plane, validation, aggregation, correlation, ingestion, MCP, API, and UI surfaces are largely implemented locally. This is not an end-to-end federation completion percentage. |
| CI-enforced maturity | **64%** | Derived from the 20-criterion professional maturity audit. |
| Operational data readiness | **15%** | Audit estimate reflecting that the last documented federation validation did not complete a representative six-producer live `fetch --run → aggregate → correlate → ingest → graph-report` cycle. |
| Live-gate evidence depth | **D0 — no certified full-federation live cycle** | The Hub can validate local contracts and packages, but a recurrent intended-scope producer cycle populating the product surfaces is not evidenced. |
| Current producer-gate state | **not modified** | Producer manifests remain authoritative; this document does not flip any producer flag. |

## Verification anchor

- **Last verified `main` commit:** `f00f2da0e6abcc885a8133e5c8b7aeb9756f5df8`
- **Last executed test baseline:** `388 passed` Python tests plus `16` frontend tests in the federation maturity audit.
- **Evidence confidence:** high for local implementation and CI maturity; medium-high for operational readiness because it depends on six independently changing producer nodes.

## Local implementation versus end-to-end federation

The legacy `~90%` figure is retained only as **local Hub implementation completeness**. It must not be presented as overall federation readiness.

The end-to-end product remains incomplete until:

1. Every required producer checkout is reachable and its own live gate is valid.
2. Producer packages pass `hub validate-package` at their current verified commits.
3. The complete `fetch --run → aggregate → correlate → ingest → graph-report` sequence runs successfully.
4. The resulting entity store contains representative real data for the domain pages.
5. The cycle is repeatable in CI or a controlled production certification workflow.
6. Diagnostic stubs are either bound to real backends or explicitly excluded from the intended production scope.
7. Frontend type checking is made actionable and enforced, and lint/type coverage includes the server surface.

A local code-complete Hub can still be operationally data-empty. The normalized scores preserve that distinction.

## Evidence-depth scale

- **D0:** synthetic, absent, or incomplete end-to-end production cycle.
- **D1:** one bounded real producer package or seeded aggregate reaches the Hub; recurrent full-cycle evidence is absent.
- **D2:** multiple real producers and bounded full-cycle runs exist; important producer or freshness gaps remain.
- **D3:** recurring real federation cycles populate the entity store with material caveats.
- **D4:** recurring intended-scope live producer cycles, freshness controls, consumer validation, and product-surface coverage.

The detailed implementation narrative remains in [`ROAD_TO_100.md`](ROAD_TO_100.md). This normalized companion controls cross-repository comparisons.
