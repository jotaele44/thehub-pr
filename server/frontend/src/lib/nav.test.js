import { describe, it, expect } from "vitest";
import { flattenFederationNav, matchFederationNavItem } from "@pr-federation/react/nav";
import capabilities from "../../../../.federation/gui-capabilities.json";
import { NAV_GROUPS } from "./nav";

const items = flattenFederationNav(NAV_GROUPS);
const active = (pathname) => matchFederationNavItem(NAV_GROUPS, pathname)?.path;

describe("navigation registry", () => {
  it("has labelled groups of labelled, absolute, unique entries", () => {
    expect(NAV_GROUPS.length).toBeGreaterThan(0);
    for (const group of NAV_GROUPS) {
      expect(group.label).toBeTruthy();
      expect(group.items.length).toBeGreaterThan(0);
    }
    for (const item of items) {
      expect(item.label).toBeTruthy();
      expect(item.path.startsWith("/")).toBe(true);
    }
    expect(new Set(items.map((item) => item.path)).size).toBe(items.length);
  });

  it("is frozen, so no component can add navigation outside this file", () => {
    expect(Object.isFrozen(NAV_GROUPS)).toBe(true);
    expect(() => NAV_GROUPS[0].items.push({})).toThrow();
  });

  it("keeps the operator settings page reachable", () => {
    expect(items.map((item) => item.path)).toContain("/operator-settings");
  });

  it("names only capabilities that the manifest declares for that route", () => {
    const routesById = new Map(
      capabilities.capabilities.map((capability) => [capability.id, capability.frontend?.routes ?? []]),
    );
    const named = items.filter((item) => item.capabilityId);
    expect(named.length).toBeGreaterThan(0);
    for (const item of named) {
      expect(routesById.has(item.capabilityId), `${item.path}: unknown capability ${item.capabilityId}`).toBe(true);
      expect(routesById.get(item.capabilityId), `${item.capabilityId} does not declare ${item.path}`).toContain(item.path);
    }
  });

  it("marks producers with federation accent tokens, never literal colours", () => {
    const accents = items.map((entry) => entry.item.accent).filter(Boolean);
    expect(accents.length).toBe(7);
    for (const accent of accents) expect(accent).toMatch(/^var\(--fd-repo-accent-[a-z]+-pr\)$/);
  });
});

describe("active entry", () => {
  it("matches the activity feed at both of its paths", () => {
    expect(active("/")).toBe("/");
    expect(active("/activity")).toBe("/");
    expect(active("/activity/today")).toBe("/");
  });

  it("matches a page and its sub-routes, by whole path segments", () => {
    expect(active("/moneysweep")).toBe("/moneysweep");
    expect(active("/moneysweep/contracts")).toBe("/moneysweep");
    expect(active("/source-monitor/abc")).toBe("/source-monitor");
    expect(active("/sources")).toBe("/sources");
    expect(active("/money")).toBeUndefined();
  });

  it("ignores query and hash", () => {
    expect(active("/gis?lat=18.2&lon=-66.5")).toBe("/gis");
    expect(active("/skywatcher?view=sky#chart")).toBe("/skywatcher");
  });

  it("has no entry for routes that are not navigation destinations", () => {
    expect(active("/login")).toBeUndefined();
    expect(active("/entity/ent_1")).toBeUndefined();
  });
});
