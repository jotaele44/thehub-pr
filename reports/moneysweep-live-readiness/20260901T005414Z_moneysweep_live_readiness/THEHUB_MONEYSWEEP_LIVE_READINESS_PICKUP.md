# TheHub MoneySweep Live-Readiness Pickup Receipt

- Run: `20260901T005414Z_moneysweep_live_readiness`
- Result: `HUB_AGGREGATE_PASS_FEDERATION_LIVE_READINESS_PROVISIONAL`
- MoneySweep package: `pkg_9208fb0b7dc71cd0b24a44ac5a126e46`
- Aggregate streams: `{'alerts': 4338, 'entities': 47484, 'observations': 574, 'relationships': 66037, 'sources': 43953}`
- Federation status: `4/6` live-ready; blockers `{'declared_not_live': 2, 'ready': 4}`
- MoneySweep blocker class: `declared_not_live`
- Skywatcher blocker class: `declared_not_live`

FACT: MoneySweep package validation and TheHub aggregate passed.

BINDING: Federation live-readiness is still provisional because MoneySweep and Skywatcher remain `declared_not_live`; package validity does not override producer readiness gates.
