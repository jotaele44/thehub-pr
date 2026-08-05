# Federation Design System Consumer Pilot Plan v0.1

## Pilot order

1. **MoneySweep** — component and data-state pilot
2. **Centinelas** — multi-route shell/state pilot

## Pilot A: MoneySweep

### Scope

- Pin the immutable v0.4 release tarball after explicit release authorization.
- Replace local QueryBoundary presentation with shared async-state components.
- Adopt Button, Panel, StatCard and semantic badges where behavior is already equivalent.
- Add package unit/a11y/contrast checks and the six-viewport state matrix.

### Exclusions

No dashboard information-architecture redesign, backend change, new routes, or data-contract change.

### Gates

- One-route behavior preserved
- Offline export preserved
- Zero critical/serious axe findings
- Loading, error, empty, filtered-empty, stale and offline states certified
- No hard-coded semantic status colors in migrated components

## Pilot B: Centinelas

Starts only after MoneySweep is green. It validates shared state components across a multi-route application, bilingual copy, localStorage-backed legislative views and FastAPI-backed pipeline views. Shell migration remains a separate reviewed increment.

## Deferred applications

- TheHub application: defer until active shell/App Center/operations PRs are adjudicated
- Skywatcher: defer until console stack and major dependency upgrades are adjudicated
- AguaYLuz: defer until active Mycelial UI work is adjudicated
- Spiderweb: select one canonical frontend before any design-system migration
- OVNIS: split or bound the monolithic dashboard before broad migration
