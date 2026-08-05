# Federation Frontend Stack Audit v1

## Coverage

This audit is based on repository-default-branch package manifests and indexed frontend entry points available through the GitHub connector on 2026-07-10.

## Stack compatibility matrix

| Repository | Frontend root | Framework/tooling | UI primitives | Data/visualization | Compatibility | Confidence |
|---|---|---|---|---|---|---|
| thehub-pr | `server/frontend` | React 18, Vite 6, Tailwind 3, TypeScript checks | Radix, Lucide, CVA | Recharts, Leaflet, Three | Direct adapter; reference implementation | High |
| spiderweb-pr | `server/frontend` | React 18, Vite 4, TypeScript | Local primitives | TanStack Table, MapLibre | Token/CSS adapter compatible; package must support Vite 4 | High |
| skywatcher-pr | `frontend` | React 18, Vite 6, Tailwind 3, TypeScript checks | Radix, Lucide, CVA | Recharts, React-Leaflet, Three | Near-identical to thehub; high reuse | High |
| moneysweep-pr | `dashboard` | React 18, Vite 6, Tailwind 3 | Radix, Lucide, CVA | Recharts | High reuse; finance-specific tables/forms remain domain adapters | High |
| centinelas-pr | unresolved | No indexed React/package manifest located | Unknown | Unknown | Blocked pending local tree inventory | Low |
| aguayluz-pr | `dashboard` | React 18, Vite 6, Tailwind 3 | Radix, Lucide, CVA | Recharts, MapLibre | High reuse; environmental map adapters required | High |
| ovnis-pr | `dashboard` | React 18, Vite 6, Tailwind 3 | Radix, Lucide, CVA | Recharts, MapLibre | High reuse; evidence/case semantics required | High |

## Duplicated component inventory

The package manifests show repeated adoption of the same component substrate across five applications: Radix UI primitives, Lucide icons, class-variance-authority, clsx, Tailwind Merge, React Hook Form, date-fns, Sonner, Recharts, and React Router. This indicates duplicated wrappers are likely for buttons, badges, dialogs, drawers, tabs, forms, tooltips, toasts, cards, tables, empty states, and navigation.

Map-heavy repositories split between Leaflet/React-Leaflet and MapLibre. Shared map controls must therefore be renderer-neutral interfaces with Leaflet and MapLibre adapters; the federation package must not force one map engine.

## Package architecture

```text
federation-design/
├── packages/
│   ├── tokens/                 # JSON and generated CSS variables
│   ├── react/                  # renderer-neutral React primitives
│   ├── react-tailwind/         # Tailwind/Radix adapters
│   ├── map-contracts/          # toolbar/layer/timeline interfaces
│   ├── map-leaflet/            # Leaflet implementation
│   ├── map-maplibre/           # MapLibre implementation
│   └── test-harness/           # Storybook/Playwright/axe fixtures
├── themes/                     # seven repository accents
├── scripts/                    # token build and contrast validation
└── docs/                       # governance and migration notes
```

### Compatibility policy

- React peer range: `>=18 <20`.
- Vite is not a runtime dependency.
- CSS distribution must work through direct import and copied offline builds.
- Tailwind adapter is optional; core tokens and primitives remain plain CSS/React.
- Map packages depend only on their specific renderer adapter.
- No backend, API, route, or data-contract assumptions.

## Migration patch plan

1. **thehub-pr reference:** import token adapter, declare repository identity, normalize global focus and reduced motion, then migrate status badges and shell primitives.
2. **spiderweb-pr:** consume core tokens without requiring Tailwind; implement MapLibre control adapters.
3. **skywatcher-pr:** reuse thehub Tailwind/Radix layer; implement Leaflet timeline and map controls.
4. **moneysweep-pr:** migrate table, report, form, and operational-status surfaces.
5. **centinelas-pr:** complete frontend root inventory before branch creation; do not assume React.
6. **aguayluz-pr:** reuse Tailwind/Radix layer and MapLibre adapters.
7. **ovnis-pr:** reuse Tailwind/Radix layer, MapLibre adapters, and evidence/confidence badges.

## Verification contract

Each repository migration must produce lint, typecheck where configured, unit/integration test, production build, axe scan, keyboard smoke, responsive screenshots at 768/1280/1440/1920, and approved visual-regression baselines. GitHub file operations alone cannot execute these runtime gates; results must come from repository CI or a local runner and be attached to each migration PR.

## Current reference migration scope

The thehub reference branch adds the federation CSS adapter and activates `data-repo="thehub-pr"` and dark-theme identity at the root. It deliberately does not replace existing Tailwind tokens or application components in this first integration patch.
