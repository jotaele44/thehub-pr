// Side-by-side geographic overlap of cases from two federation modules.
// Cases map to modules through their case_type; overlaps are grouped by shared
// municipality first, then by shared region for cases without municipality.

export const MODULE_OPTIONS = [
  "Spiderweb-PR",
  "Ovnis-PR",
  "AguaYLuz-PR",
  "MoneySweep-PR",
  "Skywatcher-PR",
  "Hub",
];

const MODULE_CASE_TYPE = {
  "Spiderweb-PR": "Network",
  "Ovnis-PR": "UAP",
  "AguaYLuz-PR": "Infrastructure",
  "MoneySweep-PR": "Contract",
  "Skywatcher-PR": "Airspace",
  Hub: "Control",
};

const unwrap = (row) => (row && row.data ? { ...row.data, id: row.id ?? row.data.id } : row);

const casesForModule = (cases, module) => {
  const type = MODULE_CASE_TYPE[module];
  return cases.filter((c) => c.case_type === type || c.module === module);
};

// Returns [{ kind: "Municipality"|"Region", label, a: [...cases], b: [...cases] }].
export function buildOverlaps(cases = [], moduleA, moduleB) {
  if (!moduleA || !moduleB || moduleA === moduleB) return [];
  const rows = cases.map(unwrap).filter(Boolean);
  const aCases = casesForModule(rows, moduleA);
  const bCases = casesForModule(rows, moduleB);
  if (!aCases.length || !bCases.length) return [];

  const groups = [];

  const groupBy = (kind, field) => {
    const index = new Map();
    const add = (side, c) => {
      const raw = c[field];
      if (!raw) return;
      const label = String(raw).trim();
      if (!label) return;
      if (!index.has(label)) index.set(label, { kind, label, a: [], b: [] });
      index.get(label)[side].push(c);
    };
    aCases.forEach((c) => add("a", c));
    bCases.forEach((c) => add("b", c));
    for (const group of index.values()) {
      if (group.a.length && group.b.length) groups.push(group);
    }
  };

  groupBy("Municipality", "municipality");
  groupBy("Region", "region");

  // A region group is redundant if every case in it already overlaps by municipality.
  const seen = new Set();
  const deduped = groups.filter((g) => {
    if (g.kind !== "Region") {
      g.a.concat(g.b).forEach((c) => seen.add(c.id));
      return true;
    }
    const fresh = g.a.some((c) => !seen.has(c.id)) || g.b.some((c) => !seen.has(c.id));
    return fresh;
  });

  return deduped.sort((x, y) => (y.a.length + y.b.length) - (x.a.length + x.b.length));
}
