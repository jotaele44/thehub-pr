import React from "react";
import { Link } from "react-router-dom";
import Dashboard from "@/pages/Dashboard";
import { GitCompareArrows, Layers, Share2, Sparkles, Boxes, ArrowRight } from "lucide-react";

// The Hub is the parent control-plane overview: it renders the Command Dashboard
// and links out to the federation workspaces. Each of those surfaces owns a single
// canonical route (also in the sidebar's Federation group) — the Hub links to them
// rather than re-embedding them, so there is exactly one URL per surface.
const LAUNCHERS = [
  { label: "Crossover Workspace", path: "/crossover", icon: GitCompareArrows, blurb: "Cross-producer correlation & convergence" },
  { label: "Anomaly Overlap", path: "/anomaly-overlap", icon: Layers, blurb: "Spatial / temporal anomaly overlap" },
  { label: "Transition Audit", path: "/transition", icon: Share2, blurb: "Producer transition & parity audit" },
  { label: "Research Assistant", path: "/research", icon: Sparkles, blurb: "Operator research & memory" },
  { label: "Control Ledgers", path: "/control", icon: Boxes, blurb: "Federation governance ledgers" },
];

function LauncherCard({ item }) {
  const Icon = item.icon;
  return (
    <Link
      to={item.path}
      className="group flex items-start gap-3 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-secondary/40"
    >
      <div className="mt-0.5 h-9 w-9 rounded-lg bg-secondary border border-border flex items-center justify-center shrink-0">
        <Icon className="h-4 w-4 text-foreground" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium">{item.label}</span>
          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">{item.blurb}</p>
      </div>
    </Link>
  );
}

export default function Hub() {
  return (
    <div>
      <Dashboard />
      <div className="mt-8">
        <div className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Federation workspaces</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {LAUNCHERS.map((item) => <LauncherCard key={item.path} item={item} />)}
        </div>
      </div>
    </div>
  );
}
