// Cross-module anomaly overlap comparison.
// "Anomalies" here are anomaly-flagged UnifiedCases (high-confidence / under-review
// records) which carry the geography (municipality + region) needed to compare
// modules side-by-side. Each case_type maps to a federation module.

import { MODULES } from "@/lib/federation";

// case_type -> module name. Multiple case types can route to the same module.
export const CASE_TYPE_MODULE = {
  UAP: "Ovnis-PR",
  Infrastructure: "AguaYLuz-PR",
  Contract: "MoneySweep-PR",
  Airspace: "Skywatcher-PR",
  Network: "Spiderweb-PR",
  Control: "Spiderweb-PR",
  Other: "Spiderweb-PR",
};

export const moduleForCase = (c) => CASE_TYPE_MODULE[c?.case_type] || "Spiderweb-PR";

export const MODULE_OPTIONS = MODULES.map((m) => m.name);

const norm = (v) => (v || "").trim().toLowerCase();

// Cases that read as "anomalies" worth comparing: anything not already Archived.
// We surface review-relevant records (New / Reviewing / Corroborated / Contradicted).
export const isAnomalyCase = (c) => c?.status && c.status !== "Archived";

export function casesForModule(cases, moduleName) {
  return cases.filter((c) => isAnomalyCase(c) && moduleForCase(c) === moduleName);
}

// Build overlap groups: a municipality OR region shared by at least one case
// from module A and one from module B.
export function buildOverlaps(cases, moduleA, moduleB) {
  if (!moduleA || !moduleB || moduleA === moduleB) return [];
  const a = casesForModule(cases, moduleA);
  const b = casesForModule(cases, moduleB);

  const groups = new Map(); // key -> { kind, label, a: [], b: [] }

  const addToGroup = (kind, rawLabel, side, item) => {
    if (!rawLabel) return;
    const key = `${kind}:${norm(rawLabel)}`;
    if (!groups.has(key)) groups.set(key, { kind, label: rawLabel, a: [], b: [] });
    groups.get(key)[side].push(item);
  };

  a.forEach((c) => { addToGroup("Municipality", c.municipality, "a", c); addToGroup("Region", c.region, "a", c); });
  b.forEach((c) => { addToGroup("Municipality", c.municipality, "b", c); addToGroup("Region", c.region, "b", c); });

  // Keep only true overlaps (both sides present).
  return Array.from(groups.values())
    .filter((g) => g.a.length > 0 && g.b.length > 0)
    // Municipality overlaps are more specific — show them first, then by total count.
    .sort((x, y) => {
      if (x.kind !== y.kind) return x.kind === "Municipality" ? -1 : 1;
      return (y.a.length + y.b.length) - (x.a.length + x.b.length);
    });
}