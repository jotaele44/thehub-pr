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

The Chromium build is whatever the installed `@playwright/test` pins (see
`package-lock.json`), the same build CI installs via
`npx playwright install --with-deps chromium`, so rendering matches.

`maxDiffPixelRatio: 0.03` absorbs cross-machine antialiasing. It also absorbs
small real changes: a page can gain a tab or a navigation entry and still pass.
`test:visual:update` rewrites only the baselines that fail, so after an
intentional change to the shell, the palette or the fonts, regenerate all of
them (`npx playwright test tests/visual/pages.spec.js --update-snapshots=all`)
and review every image before committing. Never regenerate a baseline to get a
red build green without looking at what changed.

## CI

The `frontend-visual` job in `.github/workflows/ci.yml` runs these tests on every
PR and uploads a diff report artifact on failure.
