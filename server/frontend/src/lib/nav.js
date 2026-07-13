// Single source of truth for the app's primary navigation. Consumed by both
// layout/Sidebar.jsx (desktop) and layout/MobileNav.jsx so the two never drift.
// Grouping gives every routed page a home — previously only Recent Activity, Hub,
// and the producer modules were reachable from the chrome; the federation/records/
// tools surfaces were URL-only.
import {
  Activity, Hexagon, GitCompareArrows, Layers, Share2, Github, Boxes,
  FolderKanban, FileStack, BookOpen, ListChecks, ShieldCheck, Download,
  BookA, Sparkles, Plug, Network, Radar, Droplets, Banknote, Plane,
} from "lucide-react";
import { MODULES, domainAccent } from "@/lib/federation";

const MODULE_ICONS = {
  "Spiderweb-PR": Network,
  "Ovnis-PR": Radar,
  "AguaYLuz-PR": Droplets,
  "MoneySweep-PR": Banknote,
  "Skywatcher-PR": Plane,
  "Centinelas-PR": Radar,
};

// Producer modules render an accent dot (domain color) instead of an icon, matching
// the prior sidebar treatment; icon is kept as a fallback for consumers that want it.
const producerItems = MODULES.map((m) => ({
  label: m.name,
  path: m.path,
  icon: MODULE_ICONS[m.name],
  accentDot: domainAccent(m.domain).dot,
}));

export const NAV_GROUPS = [
  {
    label: "Overview",
    items: [
      { label: "Recent Activity", path: "/", icon: Activity },
      { label: "Hub", path: "/hub", icon: Hexagon, accentDot: domainAccent("ControlPlane").dot },
    ],
  },
  { label: "Producers", items: producerItems },
  {
    label: "Federation",
    items: [
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
      { label: "Cases", path: "/cases", icon: FileStack },
      { label: "Sources", path: "/sources", icon: BookOpen },
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
      { label: "Research", path: "/research", icon: Sparkles },
      { label: "Integrations", path: "/integrations", icon: Plug },
    ],
  },
];

// Active-route test. "/" is the Recent Activity landing (also served at /activity);
// every other entry matches its exact path or a nested child of it.
export function isNavActive(pathname, path) {
  if (path === "/") return pathname === "/" || pathname.startsWith("/activity");
  return pathname === path || pathname.startsWith(path + "/");
}
