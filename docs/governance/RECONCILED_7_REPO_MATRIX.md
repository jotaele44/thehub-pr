# Reconciled Seven-Repository ROAD_TO_100 Matrix

**Audit date:** 2026-07-27  
**Governance version:** `road_to_100_normalization_v0_2`

| Repository | Implemented scope | CI maturity | Operational data readiness | Evidence depth | Live gate | Last verified `main` commit | Last executed baseline |
|---|---:|---:|---:|---|---|---|---|
| `moneysweep-pr` | **75%** | **73%** | **64%** | D2 | false | `cff93fe15502d58978e06d77e7e4b6ebbff911bd` | 2394 passed, 8 skipped; 51.74% coverage; Python 3.11.15 audit run |
| `spiderweb-pr` | **85% core pipeline only** | **56%** | **30%** | D1 | true | `ef2701ee626e538d2c188e4b9e40283d72ae503d` | 989 passed, 31 skipped |
| `aguayluz-pr` | **90%** | **70%** | **78%** | D3 | true | `e3e7e7a931cc3fd5b2fa83b5e49bcba0ae7f4101` | 306 passed |
| `ovnis-pr` | **82%** | **68%** | **65%** | D2 | true | `216cbb01bae9a6d72bcb2ea0f6e701fe3a5c6053` | 72 passed |
| `skywatcher-pr` | **70% provisional** | **61%** | **10%** | D0 | false | `52809c409d95431bf29f8fedc84c900779652ae0` | 807 passed, 13 skipped; PR #100 public workflows green, private gates unverified |
| `centinelas-pr` | **75% intended product** | **69%** | **60%** | D2 | true | `24d0769061c526a5b765ce0fa71dcd037f9a518e` | 139 passed |
| `thehub-pr` | **90% local Hub only** | **64%** | **15%** | D0 | producer-dependent | `f00f2da0e6abcc885a8133e5c8b7aeb9756f5df8` | 388 Python passed + 16 frontend tests |

## Metric interpretation

- **Implemented scope** is tied to the declared product boundary. Qualifiers such as `core pipeline only`, `local Hub only`, and `intended product` are part of the value and must not be omitted.
- **CI maturity** is the shared 20-criterion engineering score.
- **Operational data readiness** is an audit estimate based on real-data coverage, intended-scope coverage, refresh evidence, export validity, freshness/provenance, and consumer validation.
- **Live gate** is copied from authoritative manifests. A true gate is binary and does not imply equal evidence depth across repositories.

## Portfolio findings

1. `moneysweep-pr` is the most accurately calibrated roadmap: 75% implemented scope versus 73% CI maturity.
2. `spiderweb-pr` has the widest discrepancy: 85% core-pipeline scope versus 56% maturity and 30% operational data readiness.
3. `aguayluz-pr` is the strongest operational producer but its electric-outage stream remains stale and T2.
4. `ovnis-pr` has the strongest static reviewed corpus but lacks recurrent live harvesting.
5. `skywatcher-pr` remains non-production and its PR #100 private-fixture gates are not evidenced.
6. `centinelas-pr` has a functioning generic engine, but the Puerto Rico pre-officialization source universe remains incomplete.
7. `thehub-pr` is locally feature-rich but lacks a certified representative full-federation live cycle.

This matrix supersedes unqualified cross-repository comparisons based solely on the legacy ROAD_TO_100 percentages.