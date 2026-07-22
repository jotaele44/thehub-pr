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
// Colors are defined once in tailwind.config.js as semantic `fed-*` tokens (the exact
// Tailwind palette shades these accents always used: 500 base, 400 dot, 300 fg), so
// this map carries no raw palette classes — satisfying the design-system's
// "semantic tokens only" rule (docs/FEDERATION_DESIGN_SYSTEM_V1.md).
const ACCENTS = {
  ControlPlane: {
    dot: "bg-fed-controlplane-dot",
    bg: "bg-fed-controlplane/10",
    text: "text-fed-controlplane-fg",
    border: "border-fed-controlplane/30",
  },
  NetworkGraph: {
    dot: "bg-fed-networkgraph-dot",
    bg: "bg-fed-networkgraph/10",
    text: "text-fed-networkgraph-fg",
    border: "border-fed-networkgraph/30",
  },
  UAP: {
    dot: "bg-fed-uap-dot",
    bg: "bg-fed-uap/10",
    text: "text-fed-uap-fg",
    border: "border-fed-uap/30",
  },
  Infrastructure: {
    dot: "bg-fed-infrastructure-dot",
    bg: "bg-fed-infrastructure/10",
    text: "text-fed-infrastructure-fg",
    border: "border-fed-infrastructure/30",
  },
  Contracts: {
    dot: "bg-fed-contracts-dot",
    bg: "bg-fed-contracts/10",
    text: "text-fed-contracts-fg",
    border: "border-fed-contracts/30",
  },
  Airspace: {
    dot: "bg-fed-airspace-dot",
    bg: "bg-fed-airspace/10",
    text: "text-fed-airspace-fg",
    border: "border-fed-airspace/30",
  },
  Signals: {
    dot: "bg-fed-signals-dot",
    bg: "bg-fed-signals/10",
    text: "text-fed-signals-fg",
    border: "border-fed-signals/30",
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
