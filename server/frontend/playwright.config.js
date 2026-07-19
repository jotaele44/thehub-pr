import { defineConfig, devices } from '@playwright/test';

// Visual-regression harness for the hub frontend. Screenshots are captured against
// a production `vite preview` build with the API mocked to deterministic empty
// responses, so baselines depend only on the app's own CSS/tokens/fonts/layout.
// Chromium build is pinned via @playwright/test@1.56.x (matches the container's
// pre-installed browser); CI installs the same build so rendering matches.
export default defineConfig({
  testDir: './tests/visual',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  snapshotPathTemplate: 'tests/visual/__screenshots__/{testFileName}/{arg}-{projectName}{ext}',
  expect: {
    // Tolerate sub-pixel antialiasing differences between machines/runs.
    toHaveScreenshot: { maxDiffPixelRatio: 0.03, animations: 'disabled', caret: 'hide', scale: 'css' },
  },
  use: {
    baseURL: 'http://localhost:4173',
    reducedMotion: 'reduce',
    colorScheme: 'dark',
    trace: 'off',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } },
    { name: 'tablet', use: { ...devices['Desktop Chrome'], viewport: { width: 768, height: 1024 } } },
  ],
  webServer: {
    command: 'npm run build && npm run preview -- --port 4173 --strictPort',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 180000,
  },
});
