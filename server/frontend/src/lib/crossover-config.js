// Configuration for the Federation Crossover Workspace: module vocabulary,
// pair enumeration, and chip color maps.

// Modules that can appear on either side of a crossover (Hub + 6 producers).
export const CROSSOVER_MODULES = [
  "Hub",
  "Spiderweb-PR",
  "Ovnis-PR",
  "AguaYLuz-PR",
  "MoneySweep-PR",
  "Skywatcher-PR",
  "Centinelas-PR",
];

export const MODULE_SHORT = {
  Hub: "Hub",
  "Spiderweb-PR": "Spider",
  "Ovnis-PR": "Ovnis",
  "AguaYLuz-PR": "Agua",
  "MoneySweep-PR": "Money",
  "Skywatcher-PR": "Sky",
  "Centinelas-PR": "Cent",
};

// Order-insensitive key for a module pair.
export function pairKey(a, b) {
  return [a || "", b || ""].sort().join("|");
}

// Every unordered module pair (matrix rows + pair filter).
export const MODULE_PAIRS = [];
for (let i = 0; i < CROSSOVER_MODULES.length; i += 1) {
  for (let j = i + 1; j < CROSSOVER_MODULES.length; j += 1) {
    MODULE_PAIRS.push([CROSSOVER_MODULES[i], CROSSOVER_MODULES[j]]);
  }
}

// Expandable pair panels, one per module pair, lettered in order.
const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
export const PAIR_PANELS = MODULE_PAIRS.map(([a, b], i) => ({
  id: LETTERS[i] || String(i + 1),
  title: `${a} ↔ ${b}`,
  pair: [a, b],
}));

// --- Chip maps ---------------------------------------------------------------
const BLUE = "bg-sky-500/15 text-sky-300 border-sky-500/30";
const GREEN = "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
const AMBER = "bg-amber-500/15 text-amber-300 border-amber-500/30";
const RED = "bg-red-500/15 text-red-300 border-red-500/30";
const SLATE = "bg-slate-500/15 text-slate-300 border-slate-500/30";
const VIOLET = "bg-violet-500/15 text-violet-300 border-violet-500/30";
const TEAL = "bg-teal-500/15 text-teal-300 border-teal-500/30";
const LIME = "bg-lime-500/15 text-lime-300 border-lime-500/30";
const YELLOW = "bg-yellow-500/15 text-yellow-300 border-yellow-500/30";
const ORANGE = "bg-orange-500/15 text-orange-300 border-orange-500/30";
const INDIGO = "bg-indigo-500/15 text-indigo-300 border-indigo-500/30";

export const MODULE_CHIP = {
  Hub: SLATE,
  "Spiderweb-PR": VIOLET,
  "Ovnis-PR": LIME,
  "AguaYLuz-PR": TEAL,
  "MoneySweep-PR": GREEN,
  "Skywatcher-PR": BLUE,
  "Centinelas-PR": ORANGE,
};

export const CROSSOVER_STATUS_CHIP = {
  Candidate: BLUE,
  PendingReview: AMBER,
  NeedsSource: YELLOW,
  Verified: GREEN,
  Contradicted: RED,
  Rejected: RED,
};

export const BAND_CHIP = {
  Low: SLATE,
  Medium: AMBER,
  High: GREEN,
};

export const TYPE_CHIP = {
  Geography: TEAL,
  Agency: BLUE,
  Vendor: GREEN,
  InfrastructureAdjacency: ORANGE,
  LandDevelopment: AMBER,
  SourceEvidence: INDIGO,
  Anomaly: LIME,
  Temporal: VIOLET,
  Contradiction: RED,
  Entity: BLUE,
  Graph: VIOLET,
  Other: SLATE,
};
