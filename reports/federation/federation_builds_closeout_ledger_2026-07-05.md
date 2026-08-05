# Federation Builds Closeout Ledger — 2026-07-05

Vector: `FEDERATION_BUILDS_CLOSEOUT_PASS`

Scope: `thehub-pr`, `skywatcher-pr`, `moneysweep-pr`, `aguayluz-pr`, `centinelas-pr`, `ovnis-pr`, `spiderweb-pr`.

This ledger records the GitHub-visible closeout state after the P0 pass. It is intentionally conservative: a repo is not marked 100% live unless the blocking input is present, the native producer gate has run, and the Hub can validate the resulting package.

## Executive status

| Repo | Hub role | Closeout status | Completion | Blocking condition |
|---|---|---:|---:|---|
| `thehub-pr` | Hub/control plane | operational | 92% | final all-producer validation depends on missing producer exports |
| `aguayluz-pr` | water/grid producer | live-ready | 96% | only outage-feed granularity caveat remains |
| `ovnis-pr` | anomaly case producer | live-ready | 97% | optional hardening: make full jsonschema validation mandatory |
| `spiderweb-pr` | spatial/operational producer | live-ready | 94% | corpus expansion remains, not a live blocker |
| `centinelas-pr` | pre-officialization signal producer | live-ready | 93% | source-family expansion/classifier improvement remains, not a live blocker |
| `moneysweep-pr` | public-money producer | discovery-ready | 72% | required-source materialization not complete |
| `skywatcher-pr` | airspace producer | discovery-ready | 78% | real FR24 capture/export missing |

Federation live-execution state: **4/6 producers live-ready**. The Hub is operational but cannot honestly emit a final 100% Federation ledger until `moneysweep-pr` and `skywatcher-pr` clear their named P0 gates.

## Actions completed in this closeout pass

1. Confirmed current Hub registry/status split from `main`:
   - `ready_for_live`: `spiderweb-pr`, `aguayluz-pr`, `ovnis-pr`, `centinelas-pr`
   - `ready_for_discovery`: `moneysweep-pr`, `skywatcher-pr`
2. Reviewed active MoneySweep open PR surface.
3. Closed stale/non-mergeable `moneysweep-pr` PR #332 unmerged.
   - Reason: validation was not run; PR body documented connector-blocked writes for `tests/test_watch_sources.py` and `reports/weekly_watch_update_plan.md`.
   - Disposition: salvage only through a fresh branch after P0 live-source blockers are closed.
4. Identified newer MoneySweep candidate work:
   - PR #348: draft, mergeable, OCPR contracts scraper. Useful for reducing manual surface, but still a draft and not a full P0 closeout by itself.
   - PR #331: draft, non-mergeable, UEI via USASpending. Useful for SAM-rate-limit mitigation, but not merge-ready.
5. Identified Skywatcher open PR surface:
   - PR #46: offline operator scaffold.
   - PR #43/#34/#22/#12: SATIM/FR24 support vectors.
   - None supplies the actual real FR24 production capture required for live execution.

## P0 remaining work to reach 100%

### P0-A — `skywatcher-pr`: real FR24 capture/export

Required closure sequence:

```bash
cd ~/Developer/skywatcher-pr
git checkout main
git pull --ff-only

# Operator supplies real FR24 capture DB / packet according to the current runbook.
# Then run the producer package builder and native gate.
python -m pytest -q
python scripts/export_canonical.py --mode production

cd ~/Developer/thehub-pr
PYTHONPATH=src python3 -m hub validate-package --path ../skywatcher-pr/exports/federation
PYTHONPATH=src python3 -m hub validate-federation --root ~/Developer
```

Acceptance criteria:

- production export contains real, non-synthetic FR24 observations;
- `ready_for_hub_live_execution=true` is justified by runtime evidence;
- Hub validates package;
- Hub registry can flip `skywatcher-pr` from `ready_for_discovery` to `ready_for_live`.

### P0-B — `moneysweep-pr`: required-source materialization

Required sources/input family still blocking live status:

| Source/input | Required action | Closeout gate |
|---|---|---|
| `hud_drgr` / Tranche-B | operator export or validated public fallback | nonempty canonical materialization |
| `prasa` | operator export or validated public fallback | nonempty canonical materialization |
| `pr_cabilderos` | operator export or validated public fallback | nonempty canonical materialization |
| `cor3` | manual CSV/export fallback because portal is JS/operator-gated | nonempty canonical materialization |
| `PROPUBLICA_API_KEY` | provide runtime key and run source | source nonempty + gate passes |
| SAM enrichment | prefer bulk extract / USASpending UEI path over per-vendor API name matching | no rate-limit-dependent blocker for base UEI coverage |

Acceptance criteria:

```bash
cd ~/Developer/moneysweep-pr
git checkout main
git pull --ff-only

# After operator-provided exports/keys are present:
python -m pytest tests/ -q
python scripts/run_automatable_sources.py --strict
python scripts/validate_required_sources.py --strict
python scripts/export_canonical.py --mode production

cd ~/Developer/thehub-pr
PYTHONPATH=src python3 -m hub validate-package --path ../moneysweep-pr/data/exports/canonical_v1_federation
PYTHONPATH=src python3 -m hub validate-federation --root ~/Developer
```

Live flip criteria:

- required source count is either fully green or formally re-scoped in the registry with evidence;
- no source is promoted from T4/social/media alone;
- source lineage and manual-export evidence are recorded;
- Hub validates the package;
- `moneysweep-pr` registry status can move to `ready_for_live`.

## P1 remaining work

| Repo | Work | Disposition |
|---|---|---|
| `moneysweep-pr` PR #348 | OCPR contracts scraper | keep draft until review/gates complete; likely useful after P0 triage |
| `moneysweep-pr` PR #331 | UEI via USASpending | rebase or rebuild; non-mergeable draft |
| `moneysweep-pr` PR #346 | offline operator scaffold | validate separately; should not mask live-source blockers |
| `skywatcher-pr` PR #46 | offline operator scaffold | validate separately; should not mask FR24 live blocker |
| `skywatcher-pr` SATIM PRs | SATIM route/parser support | merge only if clean; not sufficient for live flip without FR24 data |

## Final Hub validation command block

Run only after P0-A and P0-B are satisfied:

```bash
cd ~/Developer/thehub-pr
git checkout main
git pull --ff-only

PYTHONPATH=src python3 -m hub fetch --run --root /tmp/prii_ws
PYTHONPATH=src python3 -m hub aggregate --root /tmp/prii_ws --out /tmp/prii_agg
PYTHONPATH=src python3 -m hub validate-federation --root /tmp/prii_ws
make test
```

Final 100% promotion gate:

- all producer manifests present;
- all production exports reproducible;
- all packages validate through Hub;
- Hub registry has no stale `ready_for_discovery` entries for production-target producers;
- final evidence ledger records runtime gate outputs for all six producers.

## Closeout conclusion

Current Federation completion remains **86% overall** by evidence. The closeout pass completed branch hygiene for `moneysweep-pr` PR #332 and produced this Hub-side ledger, but it did not and should not claim 100% until real FR24 capture and MoneySweep required-source materialization are completed.
