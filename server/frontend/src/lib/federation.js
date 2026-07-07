// Federation domain + module configuration and shared label maps.

export const DOMAIN_ACCENT = {
  ControlPlane: { text: "text-slate-300", bg: "bg-slate-500/15", border: "border-slate-500/30", dot: "bg-slate-400", ring: "ring-slate-500/30" },
  NetworkGraph: { text: "text-indigo-300", bg: "bg-indigo-500/15", border: "border-indigo-500/30", dot: "bg-indigo-400", ring: "ring-indigo-500/30" },
  UAP: { text: "text-violet-300", bg: "bg-violet-500/15", border: "border-violet-500/30", dot: "bg-violet-400", ring: "ring-violet-500/30" },
  Infrastructure: { text: "text-teal-300", bg: "bg-teal-500/15", border: "border-teal-500/30", dot: "bg-teal-400", ring: "ring-teal-500/30" },
  Contracts: { text: "text-amber-300", bg: "bg-amber-500/15", border: "border-amber-500/30", dot: "bg-amber-400", ring: "ring-amber-500/30" },
  Airspace: { text: "text-sky-300", bg: "bg-sky-500/15", border: "border-sky-500/30", dot: "bg-sky-400", ring: "ring-sky-500/30" },
};

// Module name -> domain mapping for the 5 child modules.
// repo_name = active Federation repo (used for GitHub readiness routing).
// legacy_repo / oldName = source-repo lineage (thehub-pr transition root).
export const MODULES = [
  { name: "Spiderweb-PR", domain: "NetworkGraph", path: "/spiderweb", repo_name: "spiderweb-pr", legacy_repo: "spiderweb-pr", oldName: "spiderweb-pr", blurb: "Network relationship graph" },
  { name: "Ovnis-PR", domain: "UAP", path: "/ovnis", repo_name: "ovnis-pr", legacy_repo: "PRUFON", oldName: "PRUFON", blurb: "UAP pattern & witness review" },
  { name: "AguaYLuz-PR", domain: "Infrastructure", path: "/aguayluz", repo_name: "aguayluz-pr", legacy_repo: "Aguayluz-pr", oldName: "Aguayluz-pr", blurb: "Water & power continuity" },
  { name: "MoneySweep-PR", domain: "Contracts", path: "/moneysweep", repo_name: "moneysweep-pr", legacy_repo: "Contract-Sweeper", oldName: "Contract-Sweeper", blurb: "Contract anomaly triage" },
  { name: "Skywatcher-PR", domain: "Airspace", path: "/skywatcher", repo_name: "skywatcher-pr", legacy_repo: "Aerospace-Intelligence-Tool", oldName: "Aerospace-Intelligence-Tool", blurb: "Airspace correlation" },
];

// Active Federation repo lineage. Hub is the transition root.
export const HUB_REPO = "thehub-pr";

export const REGIONS = ["North", "South", "East", "West", "Central", "Metro", "Offshore", "IslandWide", "Unknown"];

export const GATE_NAMES = [
  "HUB01_SOURCE_REPO_METADATA_PARITY",
  "HUB02_MODULE_PARITY",
  "HUB03_WORKFLOW_PARITY",
  "HUB04_DATA_LEDGER_PARITY",
  "HUB06_CRUD_RELIABILITY",
  "HUB07_EVIDENCE_STANDARDS_READINESS",
  "HUB08_EXPORT_READINESS",
  "HUB09_GITHUB_SYNC_READINESS",
  "HUB10_ACCESS_CONTROL_READINESS",
];

export const domainAccent = (domain) => DOMAIN_ACCENT[domain] || DOMAIN_ACCENT.ControlPlane;