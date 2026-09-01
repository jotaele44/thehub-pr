# Federation snapshot drift adjudication — 2026-08-25

## Scope and decision

This document adjudicates the `Federation pickup bounded MAX` failure observed while certifying PR #210. It is intentionally independent of the intelligence-workspace implementation.

**Decision:** preserve the committed producer snapshot unchanged. Do **not** rewrite mutable producer heads into `registry/development_vectors.yaml` merely to make CI green. Instead, require the bounded-MAX gate to classify producer drift fail-closed and verify that the six frozen producer SHAs remain unchanged.

The governing policy is `federation/control-plane-snapshot-policy.json`:

- `producer_mode = EXACT_FROZEN_SHA`
- `allow_producer_runtime_rebind = false`
- only the control-plane repository may be runtime rebound, because a committed file cannot know its own future merge SHA.

## Frozen snapshot manifestation

Active snapshot source at PR #210 base:

- repository: `jotaele44/thehub-pr`
- base commit: `103e06553270fd690c9c2d9aa5fd7604f3a34617`
- file: `registry/development_vectors.yaml`
- Git blob: `a650351e7ebdcb1cb0ee116948e37c4c8181b93c`
- captured_at_utc: `2026-08-24T20:30:00Z`

The Git commit/blob above is the immutable historical manifestation. No in-place snapshot refresh is performed in this adjudication.

## Failed-run evidence

Exact PR #210 head before remediation:

- head: `33894e147256a1a8554b60afea0acb7e8f45a644`
- workflow: `Federation pickup bounded MAX`
- run: `32800803461`
- job: `97661077440`
- receipt path emitted by `fed max`: `.fed/runs/20260825T021706Z_a653003ff09d.json`
- remote snapshot receipt SHA-256: `8bc8bea7acadf7ea565e7018840ac9e7eef52bf571aac20c944c42a58a5f22bf`
- bounded execution receipt SHA-256: `4738f9805b248d5216955ce7007d7478d37da199b1e6327a90e9398fddbb187d`

The `fed max` execution itself closed its declared denominator and returned `bounded_exhausted=true`, `ready_residue=[]`, and `certification=PROVISIONAL`. The workflow failed afterward because its hand-written assertion block expected the older fixed status distribution rather than the fail-closed distribution produced when frozen producer SHAs drift.

### Run-time producer comparison

| Repository | Frozen expected SHA | Observed SHA in failed run | `sha_match` | Effective consequence |
|---|---|---|---|---|
| `aguayluz-pr` | `0e3987f274a34990efc29d762573cae051e1bf15` | `773e7bd1ede928c19c1c61580cc3c52c5f56e9b3` | false | vector blocked with `stale_or_unverified_sha` |
| `centinelas-pr` | `ac241db7148e811f78960779c042fe4eff3e3038` | `7d9a6fb343bea4d2366dc1a2d07d2a840fef6f53` | false | vector blocked with `stale_or_unverified_sha` |
| `moneysweep-pr` | `80028013ee6cab525428675bc7deb7ca38121bc9` | same | true | no stale-SHA blocker |
| `ovnis-pr` | `588bc121991c529fee136c90063d0d5423f23698` | same | true | no stale-SHA blocker |
| `skywatcher-pr` | `3e11e185681832c883873785a8ec4b66bdf711ef` | `bff35b9ec1cec6a92d5f9d8970dca7c4840d8c46` | false | vector blocked with `stale_or_unverified_sha` |
| `spiderweb-pr` | `d11b74ac5e42812755282356f1d14fffc996809c` | same | true | no stale-SHA blocker |

TheHub was runtime-bound to PR base `103e06553270fd690c9c2d9aa5fd7604f3a34617` and matched by design.

### Status contradiction

The control plane correctly produced the following effective vector distribution:

- PASS: 2
- OPEN: 2
- BLOCKED: 4
- FAIL: 0
- READY: 0
- UNRESOLVED: 0

Arithmetic: `2 + 2 + 4 + 0 + 0 + 0 = 8`.

The workflow assertion still demanded the prior fixed distribution `PASS 2 + OPEN 4 + BLOCKED 2 = 8` and specifically required Centinelas to remain `OPEN`. That expectation contradicted the control-plane rule that any producer with `sha_match=false` becomes `BLOCKED` with `stale_or_unverified_sha`.

Classification: `TIME | SNAPSHOT | CI_ASSERTION` contradiction. The control-plane classification is retained; the stale hand-written assertion is superseded.

## Current-head adjudication after the failed run

The mutable producer heads continued to move after the failed run, which independently demonstrates why rewriting the frozen snapshot to chase `main` would not solve the semantic problem.

### Spiderweb

- frozen: `d11b74ac5e42812755282356f1d14fffc996809c`
- current: same
- classification: `MATCH`

### MoneySweep

- frozen: `80028013ee6cab525428675bc7deb7ca38121bc9`
- current: same
- classification: `MATCH`

### OVNIS

- frozen: `588bc121991c529fee136c90063d0d5423f23698`
- current: same
- classification: `MATCH`

### Centinelas

- frozen: `ac241db7148e811f78960779c042fe4eff3e3038`
- current: `7d9a6fb343bea4d2366dc1a2d07d2a840fef6f53`
- topology: current is 4 commits ahead, 0 behind; frozen SHA is the merge base
- changed payload in the bounded comparison: `docs/UI_CLEANUP_OPTIMIZATION_PLAN.md`
- classification: `FORWARD_DRIFT`, not divergence

The current head therefore preserves the frozen commit in its ancestry. The drift is real but does not authorize identity or readiness promotion.

### Skywatcher

- frozen: `3e11e185681832c883873785a8ec4b66bdf711ef`
- current: `bff35b9ec1cec6a92d5f9d8970dca7c4840d8c46`
- topology: current is 104 commits ahead, 0 behind; frozen SHA is the merge base
- changed scope includes workflow/dependency updates, visual-reasoning baselines, SATIM changes, POI attribution geometry-binding code/tests, and frontend dependency updates
- classification: `FORWARD_DRIFT`, materially nontrivial

No claim is made that the 104-commit delta is semantically equivalent to the frozen snapshot. It is merely descendant lineage.

### AguaYLuz

- frozen: `0e3987f274a34990efc29d762573cae051e1bf15`
- failed-run observed: `773e7bd1ede928c19c1c61580cc3c52c5f56e9b3`
- current observed during adjudication: `d594490d240d3656e824179082b1eb2859882826`
- topology from frozen to current: current is 10 commits ahead, 0 behind; frozen SHA is the merge base
- delta includes an environmental public-service denominator/test and recurring scheduled refresh commits that mutate tracked event/asset JSONL data
- classification: `FORWARD_MUTABLE_DATA_DRIFT`

This is the strongest negative control against opportunistic snapshot refresh: the AguaYLuz head changed multiple times after the failed CI run through scheduled refreshes. A new exact snapshot would become stale again whenever the next legitimate refresh lands.

## Corrected invariant

The bounded-MAX workflow now verifies the following rather than expecting a fixed status count:

1. the six producer expected SHAs remain byte-for-byte the values frozen in the committed ledger;
2. only TheHub is runtime rebound;
3. the snapshot denominator is exactly seven repositories;
4. every drifted producer is classified fail-closed;
5. every vector owned by a drifted producer carries `stale_or_unverified_sha` and has effective status `BLOCKED`;
6. matched producers do not acquire a stale-SHA blocker;
7. no passed vector is re-executed merely because a producer advanced;
8. vector and repository arithmetic close;
9. `READY`, `FAIL`, and `UNRESOLVED` residue remain zero inside this declared bounded gate;
10. universal exhaustion remains explicitly false.

## Certification disposition

- Frozen snapshot identity: `PASS` — preserved, not rewritten.
- Live producer equivalence to snapshot: `FAIL` for drifted producers by design; no equivalence is claimed.
- Drift classification: `PASS` for the bounded observed set.
- Original workflow assertion: `SUPERSEDED` because it encoded fixed counts inconsistent with the control plane's fail-closed stale-SHA semantics.
- New workflow assertion: `PROVISIONAL` until exact-head hosted execution passes.
- Universal federation freshness/exhaustion: not claimed.
