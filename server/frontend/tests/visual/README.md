# Visual regression baselines

Playwright screenshot baselines for the hub frontend, covering the design system
(shell/nav, page headers + domain badges, tabs, filter bars, tables, empty states,
status tokens, self-hosted fonts) at desktop (1280) and tablet (768) widths.

Screenshots are captured against a production `vite preview` build with the API
mocked to deterministic empty responses (see `pages.spec.js`), and the clock is
frozen — so a baseline only changes when the app's own CSS/layout/tokens/fonts do.

## Run

```bash
# compare against committed baselines
npm run test:visual

# regenerate baselines after an intentional UI change (review the diff before committing)
npm run test:visual:update
```

Baselines live in `__screenshots__/` and are committed. `test-results/` and
`playwright-report/` are git-ignored.

## Environment

The Chromium build is pinned through `@playwright/test` (1.56.x → Chromium 1194),
the same build CI installs via `npx playwright install --with-deps chromium`, so
rendering matches. `maxDiffPixelRatio: 0.03` absorbs minor cross-machine
antialiasing. If a legitimate rendering difference trips CI, regenerate the
baselines with `test:visual:update` and commit the updated PNGs.

## CI

The `frontend-visual` job in `.github/workflows/ci.yml` runs these tests on every
PR and uploads a diff report artifact on failure.
