import React from "react";
import StatCard from "@/components/shared/StatCard";
import { CheckCircle2, Clock, AlertTriangle, Gauge, Network, Layers, FileWarning } from "lucide-react";

export default function CrossoverSummary({ summary }) {
  const cards = [
    { label: "Verified Crossovers", value: summary.verified, icon: CheckCircle2, accent: "text-status-success-fg" },
    { label: "Pending Candidates", value: summary.pending, icon: Clock, accent: "text-status-info-fg" },
    { label: "Contradicted", value: summary.contradicted, icon: AlertTriangle, accent: "text-status-warning-fg", alert: summary.contradicted > 0 },
    { label: "High Confidence", value: summary.highConfidence, icon: Gauge, accent: "text-status-success-fg" },
    { label: "Module Pairs w/ Overlap", value: summary.modulePairs, icon: Network },
    { label: "3+ Module Convergence", value: summary.multiModule, icon: Layers, accent: "text-status-process-fg" },
    { label: "Missing Source/Evidence", value: summary.missingSource, icon: FileWarning, accent: "text-status-caution-fg", alert: summary.missingSource > 0 },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
      {cards.map((c) => <StatCard key={c.label} {...c} />)}
    </div>
  );
}