import { expect, test } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";

const findings: unknown[] = [];

test.beforeEach(async ({ context, page }) => {
  await context.routeWebSocket("**/*", ws => ws.close());
  await context.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.origin === "http://127.0.0.1:4173") {
      if (url.pathname === "/api/export" && route.request().method() === "POST") {
        return route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({accepted: true}) });
      }
      if (url.pathname.startsWith("/api/")) return route.fulfill({ status: 404, body: "blocked/missing" });
      return route.continue();
    }
    return route.abort("blockedbyclient");
  });
  await page.goto("/");
});

test.afterAll(async () => {
  await mkdir("artifacts", { recursive: true });
  await writeFile("artifacts/executability-ledger.json", JSON.stringify({schema_version: "0.1.0", findings}, null, 2));
});

test("canonical six-classification fixture", async ({ page }) => {
  const noOp = page.getByRole("button", { name: "No Op" });
  await noOp.click();
  findings.push({surface: "no-op", classification: "UI_NO_OP", evidence: "no event, request, state, or navigation"});

  await page.getByRole("button", { name: "Partial" }).click();
  await expect(page.locator("#status")).toHaveText("loading");
  findings.push({surface: "partial", classification: "PARTIALLY_WIRED", evidence: "handler entered; no terminal state"});

  const missingRequest = page.waitForRequest(r => new URL(r.url()).pathname === "/api/missing");
  await page.getByRole("button", { name: "Missing Target" }).click();
  await missingRequest;
  findings.push({surface: "missing", classification: "TARGET_MISSING", evidence: "intercepted target returned 404"});

  const mismatchRequest = page.waitForRequest(r => new URL(r.url()).pathname === "/api/export" && r.method() === "GET");
  await page.getByRole("button", { name: "Contract Mismatch" }).click();
  await mismatchRequest;
  findings.push({surface: "mismatch", classification: "CONTRACT_MISMATCH", evidence: "GET does not match declared POST"});

  await expect(page.getByRole("button", { name: "Blocked" })).toBeDisabled();
  findings.push({surface: "blocked", classification: "WIRED_BUT_BLOCKED", evidence: "declared AUDIT_TOKEN precondition"});

  const contractRequest = page.waitForRequest(r => new URL(r.url()).pathname === "/api/export" && r.method() === "POST");
  await page.getByRole("button", { name: "Executable By Contract" }).click();
  await contractRequest;
  await expect(page.locator("#status")).toHaveText("accepted");
  findings.push({surface: "contract", classification: "EXECUTABLE_BY_CONTRACT", evidence: "matching request intercepted; 202 terminal UI state"});
});
