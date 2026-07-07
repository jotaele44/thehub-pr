// Federation Crossover Workspace — module pair + label configuration.
// Module ownership boundaries are preserved; the Hub never becomes source-of-truth.

export const CROSSOVER_MODULES = ["Hub", "Spiderweb-PR", "Ovnis-PR", "AguaYLuz-PR", "MoneySweep-PR", "Skywatcher-PR"];

// Short display labels.
export const MODULE_SHORT = {
  "Hub": "Hub",
  "Spiderweb-PR": "Spiderweb",
  "Ovnis-PR": "Ovnis",
  "AguaYLuz-PR": "AguaYLuz",
  "MoneySweep-PR": "MoneySweep",
  "Skywatcher-PR": "Skywatcher",
};

// Module chip colors (reuse federation domain accents loosely).
export const MODULE_CHIP = {
  "Hub": "bg-slate-500/15 text-slate-300 border-slate-500/30",
  "Spiderweb-PR": "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  "Ovnis-PR": "bg-violet-500/15 text-violet-300 border-violet-500/30",
  "AguaYLuz-PR": "bg-teal-500/15 text-teal-300 border-teal-500/30",
  "MoneySweep-PR": "bg-amber-500/15 text-amber-300 border-amber-500/30",
  "Skywatcher-PR": "bg-sky-500/15 text-sky-300 border-sky-500/30",
};

export const CROSSOVER_STATUS_CHIP = {
  Candidate: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  PendingReview: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  Verified: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  Contradicted: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  Rejected: "bg-red-500/15 text-red-300 border-red-500/30",
  NeedsSource: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
};

export const BAND_CHIP = {
  Low: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  Medium: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  High: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
};

export const TYPE_CHIP = {
  Geography: "bg-teal-500/15 text-teal-300 border-teal-500/30",
  Agency: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  Vendor: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  InfrastructureAdjacency: "bg-teal-500/15 text-teal-300 border-teal-500/30",
  LandDevelopment: "bg-lime-500/15 text-lime-300 border-lime-500/30",
  SourceEvidence: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  Anomaly: "bg-red-500/15 text-red-300 border-red-500/30",
  Temporal: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  Contradiction: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  Entity: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  Graph: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  Other: "bg-slate-500/15 text-slate-300 border-slate-500/30",
};

// The 15 federation module pairs (Hub + 5 modules), order-stable.
export const MODULE_PAIRS = (() => {
  const pairs = [];
  for (let i = 0; i < CROSSOVER_MODULES.length; i++) {
    for (let j = i + 1; j < CROSSOVER_MODULES.length; j++) {
      pairs.push([CROSSOVER_MODULES[i], CROSSOVER_MODULES[j]]);
    }
  }
  return pairs;
})();

export const pairKey = (a, b) => [a, b].sort().join(" ↔ ");

// Curated titles for the analytical (non-Hub) pairs. Hub pairs are control-plane links
// (tasks/manifests/gates/integrations) and are generated below so all 15 pairs are covered.
const CURATED_PAIR_TITLES = {
  "Ovnis-PR ↔ Skywatcher-PR": "Skywatcher Airspace ↔ Ovnis Cases",
  "Skywatcher-PR ↔ Spiderweb-PR": "Skywatcher Airspace ↔ Spiderweb Graph",
  "AguaYLuz-PR ↔ Skywatcher-PR": "Skywatcher Airspace ↔ AguaYLuz Infrastructure",
  "MoneySweep-PR ↔ Skywatcher-PR": "Skywatcher Airspace ↔ MoneySweep Financial",
  "Ovnis-PR ↔ Spiderweb-PR": "Ovnis Cases ↔ Spiderweb Graph",
  "AguaYLuz-PR ↔ Ovnis-PR": "Ovnis Cases ↔ AguaYLuz Infrastructure",
  "MoneySweep-PR ↔ Ovnis-PR": "Ovnis Cases ↔ MoneySweep Financial",
  "AguaYLuz-PR ↔ MoneySweep-PR": "AguaYLuz Infrastructure ↔ MoneySweep Financial",
  "AguaYLuz-PR ↔ Spiderweb-PR": "AguaYLuz Infrastructure ↔ Spiderweb Graph",
  "MoneySweep-PR ↔ Spiderweb-PR": "MoneySweep Financial ↔ Spiderweb Graph",
};

// Full 15-pair coverage. Every module pair gets a panel; Hub pairs are labelled as
// control-plane links. IDs are stable letters A.. for readability.
export const PAIR_PANELS = (() => {
  const panels = MODULE_PAIRS.map(([a, b], idx) => {
    const key = pairKey(a, b);
    const isHub = a === "Hub" || b === "Hub";
    const other = a === "Hub" ? b : a;
    const title = CURATED_PAIR_TITLES[key]
      || (isHub ? `Hub Control ↔ ${MODULE_SHORT[other]} (tasks · manifest · gates · integrations)` : `${MODULE_SHORT[a]} ↔ ${MODULE_SHORT[b]}`);
    return { id: String.fromCharCode(65 + idx), title, pair: [a, b], hub: isHub };
  });
  return panels;
})();

// Controlled GraphNode node_type values that represent ILAP candidates / POIs.
export const ILAP_NODE_TYPES = ["ILAP_CANDIDATE", "POI", "LAND_DEVELOPMENT_SITE", "INFRASTRUCTURE_ADJACENT_POI"];

export const bandFromScore = (score) => (score >= 70 ? "High" : score >= 40 ? "Medium" : "Low");