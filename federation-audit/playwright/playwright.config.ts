import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["json", { outputFile: "artifacts/results.json" }]],
  use: {
    baseURL: process.env.AUDIT_BASE_URL ?? "http://127.0.0.1:4173",
    trace: "on",
    screenshot: "on",
    video: "retain-on-failure",
    acceptDownloads: false,
    serviceWorkers: "block",
  },
  webServer: {
    command: "python -m http.server 4173 --directory fixtures >/dev/null 2>&1",
    port: 4173,
    reuseExistingServer: false,
    stdout: "ignore",
    stderr: "ignore",
  },
});
