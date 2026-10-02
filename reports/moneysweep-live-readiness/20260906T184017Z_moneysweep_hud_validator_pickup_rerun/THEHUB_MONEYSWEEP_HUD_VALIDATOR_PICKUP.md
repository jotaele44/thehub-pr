# TheHub MoneySweep HUD Validator Pickup

- Run: `20260906T184017Z_moneysweep_hud_validator_pickup_rerun`
- Scope: `MoneySweep HUD DRGR pursuit + legacy validator drift pickup`
- MoneySweep head: `fca326476f9811553888c4cc02a1fff20cc303fe`
- MoneySweep origin/main: `fca326476f9811553888c4cc02a1fff20cc303fe`
- TheHub head at gate: `94e000b5e0f21a5d1acaed42e79e73523c86ab56`
- Result: `PROVISIONAL_PICKUP_PASS_WITH_DECLARED_BLOCKERS`

## Passed Gates

- `hub validate-package ../moneysweep-pr/data/exports/canonical_v1_federation`: `PASS`
- `hub aggregate --root ..`: `PASS`, aggregate contributed `2` producers locally and preserved missing-package warnings for the other producers
- `hub validate-federation --root .. --json`: `PASS_EXECUTION`, `ready_count=0`
- TheHub focused tests: `PASS`, `19 passed`

## Blocker Arithmetic

```json
{
  "declared_not_live": 2,
  "missing_export_package": 4
}
```

## Certification Boundary

This is not all-seven certification. MoneySweep remains `declared_not_live` because `hud_drgr_authorized` remains `PARTIAL_UNRESOLVED`; Skywatcher remains `declared_not_live`; AguaYLuz, Centinelas, OVNIS, and SpiderWeb are present but missing local export packages in this TheHub aggregate path.
