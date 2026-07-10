// Federation topology facts for the INTSYS-PR / thehub-pr control plane.
// The Hub (parent control plane) plus 5 child producer modules. Sourced from
// the repo's registry/producers.yaml and README producer map.

export const HUB_REPO = "thehub-pr";

// Child modules of the federation. The Hub itself (ControlPlane) is modeled
// separately by consumers (Sidebar/MobileNav define their own HUB entry).
export const MODULES = [
  {
    name: "Spiderweb-PR",
    path: "/spiderweb",
    domain: "NetworkGraph",
    repo_name: "spiderweb-pr",
    oldName: "spiderweb-pr",
    blurb: "Spatial / operational evidence, entity & relationship graph",
  },
  {
    name: "Ovnis-PR",
    path: "/ovnis",
    domain: "UAP",
    repo_name: "ovnis-pr",
    oldName: "ovnis-pr",
    blurb: "Puerto Rico historical anomaly case corpus",
  },
  {
    name: "AguaYLuz-PR",
    path: "/aguayluz",
    domain: "Infrastructure",
    repo_name: "aguayluz-pr",
    oldName: "aguayluz-pr",
    blurb: "Water, wastewater, power & outage monitoring",
  },
  {
    name: "MoneySweep-PR",
    path: "/moneysweep",
    domain: "Contracts",
    repo_name: "moneysweep-pr",
    oldName: "moneysweep-pr",
    blurb: "Public money, procurement, grants & influence records",
  },
  {
    name: "Skywatcher-PR",
    path: "/skywatcher",
    domain: "Airspace",
    repo_name: "skywatcher-pr",
    oldName: "skywatcher-pr",
    blurb: "Airspace / aircraft intelligence & FR24 ingestion",
  },
  {
    name: "Centinelas-PR",
    path: "/centinelas",
    domain: "Signals",
    repo_name: "centinelas-pr",
    oldName: "centinelas-pr",
    blurb: "Pre-officialization signal intake, classification & routing",
  },
];

// Controlled region vocabulary for case / event records (Puerto Rico).
export const REGIONS = [
  "Metro",
  "Norte",
  "Sur",
  "Este",
  "Oeste",
  "Centro",
  "Vieques-Culebra",
  "Isla-wide",
  "Offshore",
];

// Validation gate names used by the ValidationGates ledger.
export const GATE_NAMES = [
  "SchemaValidation",
  "ManifestValidation",
  "ExportPackageValidation",
  "EvidenceStandards",
  "ProvenancePreservation",
  "SensitivityReview",
  "SyntheticDataSweep",
  "GitHubSyncApproval",
  "LiveExecutionReadiness",
  "ParityAudit",
];

// Accent palette per federation domain — consumers read .dot / .bg / .text / .border.
const ACCENTS = {
  ControlPlane: {
    dot: "bg-slate-300",
    bg: "bg-slate-500/10",
    text: "text-slate-300",
    border: "border-slate-500/30",
  },
  NetworkGraph: {
    dot: "bg-violet-400",
    bg: "bg-violet-500/10",
    text: "text-violet-300",
    border: "border-violet-500/30",
  },
  UAP: {
    dot: "bg-lime-400",
    bg: "bg-lime-500/10",
    text: "text-lime-300",
    border: "border-lime-500/30",
  },
  Infrastructure: {
    dot: "bg-teal-400",
    bg: "bg-teal-500/10",
    text: "text-teal-300",
    border: "border-teal-500/30",
  },
  Contracts: {
    dot: "bg-emerald-400",
    bg: "bg-emerald-500/10",
    text: "text-emerald-300",
    border: "border-emerald-500/30",
  },
  Airspace: {
    dot: "bg-sky-400",
    bg: "bg-sky-500/10",
    text: "text-sky-300",
    border: "border-sky-500/30",
  },
  Signals: {
    dot: "bg-orange-400",
    bg: "bg-orange-500/10",
    text: "text-orange-300",
    border: "border-orange-500/30",
  },
};

const DEFAULT_ACCENT = {
  dot: "bg-muted-foreground",
  bg: "bg-secondary",
  text: "text-muted-foreground",
  border: "border-border",
};

export function domainAccent(domain) {
  return ACCENTS[domain] || DEFAULT_ACCENT;
}
