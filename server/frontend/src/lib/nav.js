// The Hub's navigation registry (docs/FEDERATION_GUI_STANDARD.md §4): the one
// place a page is added to the navigation. The shared shell renders it as the
// sidebar and, on small screens, the bottom bar; lib/commands.js feeds the
// command palette from it.
import { defineFederationNav } from "@pr-federation/react/nav";
import {
  Activity, Hexagon, GitCompareArrows, Layers, Share2, Github, Boxes,
  FolderKanban, FileStack, BookOpen, ListChecks, ShieldCheck, Download,
  BookA, Sparkles, Plug, Network, Radar, Droplets, Banknote, Plane, Signpost, AppWindow, TerminalSquare, Settings,
  Search, History, Orbit, Gauge,
} from "lucide-react";
import { MODULES } from "@/lib/federation";

const MODULE_ICONS = {
  "Spiderweb-PR": Network,
  "Ovnis-PR": Radar,
  "AguaYLuz-PR": Droplets,
  "MoneySweep-PR": Banknote,
  "Skywatcher-PR": Plane,
  "Centinelas-PR": Radar,
};

// capabilityId names the entry's capability in .federation/gui-capabilities.json.
// Only entries whose page is a declared capability carry one. Most Hub pages
// predate the manifest and have none yet; that debt is listed in the standard
// (§5, "Hub navigation without a capability"), and is why the registry below is
// built with the migration waiver instead of pretending the ids exist.
const PRODUCER_CAPABILITIES = {
  // /moneysweep hosts two leaderboards; the debt leaderboard is the page's lead view.
  "/moneysweep": "moneysweep-certified-debt-leaderboard",
  "/aguayluz": "aguayluz-outdoor-conditions",
  "/skywatcher": "sky-workspace",
};

// Each producer is marked with its own federation accent token. An accent
// replaces the icon, as the dots did before.
const producerItems = MODULES.map((m) => ({
  label: m.name,
  path: m.path,
  icon: MODULE_ICONS[m.name],
  accent: `var(--fd-repo-accent-${m.repo_name})`,
  ...(PRODUCER_CAPABILITIES[m.path] ? { capabilityId: PRODUCER_CAPABILITIES[m.path] } : {}),
}));

export const NAV_GROUPS = defineFederationNav([
  {
    label: "Overview",
    items: [
      // The activity feed is also served at /activity.
      { label: "Recent Activity", path: "/", icon: Activity, match: ["/activity"] },
      { label: "Hub", path: "/hub", icon: Hexagon, accent: "var(--fd-repo-accent-thehub-pr)" },
      { label: "Search", path: "/search", icon: Search, capabilityId: "federated-search" },
      { label: "Timeline", path: "/timeline", icon: History, capabilityId: "ovnis-event-timeline" },
    ],
  },
  { label: "Producers", items: producerItems },
  {
    label: "Federation",
    items: [
      { label: "Constellation", path: "/constellation", icon: Orbit, capabilityId: "federation-constellation" },
      { label: "Crossover", path: "/crossover", icon: GitCompareArrows },
      { label: "Anomaly Overlap", path: "/anomaly-overlap", icon: Layers },
      { label: "Transition Audit", path: "/transition", icon: Share2 },
      { label: "Module Readiness", path: "/readiness", icon: Github },
      { label: "Control Ledgers", path: "/control", icon: Boxes },
    ],
  },
  {
    label: "Records",
    items: [
      { label: "Programs", path: "/programs", icon: FolderKanban },
      { label: "Project Signs", path: "/project-signs", icon: Signpost },
      { label: "App Center", path: "/apps", icon: AppWindow },
      { label: "Operations", path: "/operations", icon: TerminalSquare },
      { label: "Cases", path: "/cases", icon: FileStack },
      { label: "Sources", path: "/sources", icon: BookOpen },
      { label: "Source Monitor", path: "/source-monitor", icon: Gauge, capabilityId: "source-monitor" },
      { label: "Tasks", path: "/tasks", icon: ListChecks },
      { label: "Gates", path: "/gates", icon: ShieldCheck },
      { label: "Exports", path: "/exports", icon: Download },
      { label: "Dictionary", path: "/dictionary", icon: BookA },
      { label: "Manifest", path: "/manifest", icon: Boxes },
    ],
  },
  {
    label: "Tools",
    items: [
      // /gis hosts several map capabilities; the property map is its lead view.
      { label: "GIS Workspace", path: "/gis", icon: Layers, capabilityId: "property-map-location-intel" },
      { label: "Research", path: "/research", icon: Sparkles, capabilityId: "ovnis-research-hub" },
      { label: "Integrations", path: "/integrations", icon: Plug },
      { label: "Operator Settings", path: "/operator-settings", icon: Settings },
    ],
  },
], { requireCapabilityId: false });
