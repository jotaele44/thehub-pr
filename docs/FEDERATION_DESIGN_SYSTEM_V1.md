# Federation Design System v1

## Mission
Normalize visual style, formatting, interaction semantics, and accessibility across the seven federation repositories without erasing domain identity.

## Authoritative artifacts

- `federation-design/tokens/federation.tokens.json`
- `federation-design/styles/federation.css`
- This rollout contract

## Component contract

The shared package must expose stable primitives for:

- Button, IconButton, LinkButton
- Card, Panel, MetricCard
- DataTable, TableToolbar, Pagination
- Dialog, Drawer, Popover, Tooltip
- TextField, Select, Checkbox, Radio, Switch, DateRange
- StatusBadge, SourceBadge, ConfidenceBadge
- EmptyState, Skeleton, ErrorState, Toast
- ChartFrame, Legend, TooltipContent
- MapToolbar, LayerControl, CoordinateReadout, TimelineControl
- AppShell, ModuleNav, InspectorPanel, StatusBar

Components must consume semantic tokens only. Hard-coded repository colors are prohibited outside token definitions.

## Accessibility gates

- WCAG 2.2 AA contrast for normal and large text
- Full keyboard reachability
- Visible focus state
- Semantic landmarks and form labels
- Dialog focus trapping and escape behavior
- Reduced-motion support
- Screen-reader names for icon-only controls

## Repository migration order

1. `thehub-pr`: reference implementation and integration contract
2. `spiderweb-pr`: shared shell and map-control normalization
3. `skywatcher-pr`: dense operational panels, tables, map timeline
4. `moneysweep-pr`: tables, status semantics, forms, reports
5. `centinelas-pr`: alerts, source cards, monitoring states
6. `aguayluz-pr`: environmental layers and observation panels
7. `ovnis-pr`: case records, evidence badges, map and timeline

## Required migration procedure per repository

1. Create branch `gpt/federation-design-system-v1` from current `main`.
2. Inventory frontend roots, frameworks, CSS systems, icon libraries, chart libraries, map libraries, and duplicated primitives.
3. Add the token adapter without changing data contracts.
4. Migrate shell, typography, status colors, focus states, loading states, and empty states.
5. Migrate shared components incrementally; preserve existing behavior.
6. Add visual-regression fixtures for primary operational pages.
7. Run repository-native lint, typecheck, tests, build, responsive smoke, and accessibility checks.
8. Open a repository-specific PR with before/after evidence and remaining exceptions.

## Verification matrix

| Gate | Required |
|---|---|
| Existing API contracts unchanged | Yes |
| Existing route coverage preserved | 100% |
| Hard-coded semantic status colors removed | 100% |
| Keyboard-critical workflows passing | 100% |
| WCAG AA automated violations | 0 critical/serious |
| Lint | Pass |
| Typecheck where configured | Pass |
| Unit/integration tests | Pass |
| Production build | Pass |
| Desktop widths 1280/1440/1920 | Pass |
| Tablet width 768 | Pass or documented unsupported |
| Visual regression | Approved baseline |

## Governance

Token and component changes require:

- semantic-version impact classification
- changelog entry
- migration note for breaking changes
- visual-regression update rationale
- validation against at least `thehub-pr` and one map-heavy repository

## Current limitation

The GitHub connector can modify existing repositories but cannot create the requested standalone `federation-design` repository. This branch therefore establishes the authoritative seed inside `thehub-pr`. The directory can be extracted into a dedicated repository without changing its contract once the repository is created through GitHub UI or CLI.
