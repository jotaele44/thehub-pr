import { describe, expect, it } from "vitest";
import {
  FRESHNESS_STATES, MONITOR_PRODUCERS, PRODUCER_PAGES, exportAgeDays, freshnessState,
  monitorPath, withFreshness,
} from "./sourceMonitor";

const NOW = Date.parse("2026-11-08T00:00:00Z");
const DAY = 86400;
const daysAgo = (n) => new Date(NOW - n * DAY * 1000).toISOString();

describe("freshnessState (producer-level)", () => {
  const weekly = { cadence: "weekly", cadence_window_seconds: 7 * DAY };

  it("is Fresh within one cadence window", () => {
    expect(freshnessState({ ...weekly, producer_last_package_at: daysAgo(3) }, NOW)).toBe("Fresh");
  });
  it("is Due past one window and Stale past two", () => {
    expect(freshnessState({ ...weekly, producer_last_package_at: daysAgo(10) }, NOW)).toBe("Due");
    expect(freshnessState({ ...weekly, producer_last_package_at: daysAgo(15) }, NOW)).toBe("Stale");
  });
  it("is Unknown without an export timestamp or a cadence window", () => {
    expect(freshnessState({ ...weekly, producer_last_package_at: null }, NOW)).toBe("Unknown");
    expect(freshnessState({ cadence: "event", cadence_window_seconds: null, producer_last_package_at: daysAgo(1) }, NOW)).toBe("Unknown");
    expect(freshnessState({ ...weekly, producer_last_package_at: "not a date" }, NOW)).toBe("Unknown");
  });
  it("is Static for non-recurring sources regardless of export age", () => {
    expect(freshnessState({ cadence: "static", producer_last_package_at: daysAgo(900) }, NOW)).toBe("Static");
  });
});

describe("withFreshness", () => {
  it("adds sortable, filterable derived fields with stale first", () => {
    const map = withFreshness(NOW);
    const stale = map({ cadence: "daily", cadence_window_seconds: DAY, producer_last_package_at: daysAgo(5) });
    const fresh = map({ cadence: "yearly", cadence_window_seconds: 366 * DAY, producer_last_package_at: daysAgo(5) });
    const unknown = map({ cadence: "unknown" });
    expect([stale.freshness, fresh.freshness, unknown.freshness]).toEqual(["Stale", "Fresh", "Unknown"]);
    expect(stale.freshness_rank).toBeLessThan(unknown.freshness_rank);
    expect(unknown.freshness_rank).toBeLessThan(fresh.freshness_rank);
    expect(stale.export_age_days).toBe(5);
    expect(unknown.export_age_days).toBeNull();
  });
  it("covers every freshness state with a rank", () => {
    expect(FRESHNESS_STATES).toHaveLength(5);
  });
});

describe("routing helpers", () => {
  it("encodes monitor ids, which contain a colon", () => {
    expect(monitorPath("ovnis-pr:SRC-0001")).toBe("/source-monitor/ovnis-pr%3ASRC-0001");
  });
  it("maps every producer to its hub page", () => {
    expect(MONITOR_PRODUCERS).toEqual([
      "aguayluz-pr", "centinelas-pr", "moneysweep-pr", "ovnis-pr", "skywatcher-pr", "spiderweb-pr",
    ]);
    expect(PRODUCER_PAGES["moneysweep-pr"]).toBe("/moneysweep");
  });
  it("reports export age in whole days", () => {
    expect(exportAgeDays({ producer_last_package_at: daysAgo(2.5) }, NOW)).toBe(2);
  });
});
