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
});
