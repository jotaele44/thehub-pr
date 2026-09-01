# TheHub MoneySweep PRASA Closure Pickup

- Run ID: `20260901T022813Z_moneysweep_prasa_contract_closure`
- Result: `HUB_AGGREGATE_PASS_IOS_SURFACE_UPDATED_LIVE_READINESS_PROVISIONAL`
- MoneySweep SHA: `b5661dd29b5905015016041057136b6c945ddf5a`
- MoneySweep package: `pkg_9642c2a411343e9c0c20891ac84f4f08`
- Federation readiness: `4/6` ready; blockers `{'declared_not_live': 2, 'ready': 4}`

## iOS Surface

- `MoneySweep`: `BLOCKED_BY_DESKTOP_GAP` remains visible.
- `prasa`: displayed as `FOUND_STRUCTURED_FROM_AUTHORITY_TRANSITION_PDF`, not partial.
- `hud_drgr_authorized`: displayed as `PARTIAL_UNRESOLVED`.
- ZIP references remain `NONCANONICAL_REFERENCE`.

## Gates

- TheHub aggregate: `PASS`
- TheHub federation status snapshot: `PASS`
- TheHub backend focused tests: `PASS` (`19 passed`)
- AppCenter UI tests: `PASS` (`6 passed`)

## Bounded Claim

TheHub consumed the pushed MoneySweep PRASA closure receipt and regenerated aggregate/status evidence. The federation is not universally complete because MoneySweep and Skywatcher remain `declared_not_live`.
