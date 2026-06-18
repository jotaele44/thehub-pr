import React from "react";
import StatCard from "@/components/shared/StatCard";
import { CheckCircle2, Clock, AlertTriangle, Gauge, Network, Layers, FileWarning } from "lucide-react";

export default function CrossoverSummary({ summary }) {
  const cards = [
    { label: "Verified Crossovers", value: summary.verified, icon: CheckCircle2, accent: "text-emerald-300" },
    { label: "Pending Candidates", value: summary.pending, icon: Clock, accent: "text-blue-300" },
    { label: "Contradicted", value: summary.contradicted, icon: AlertTriangle, accent: "text-amber-300", alert: summary.contradicted > 0 },
    { label: "High Confidence", value: summary.highConfidence, icon: Gauge, accent: "text-emerald-300" },
    { label: "Module Pairs w/ Overlap", value: summary.modulePairs, icon: Network },
    { label: "3+ Module Convergence", value: summary.multiModule, icon: Layers, accent: "text-violet-300" },
    { label: "Missing Source/Evidence", value: summary.missingSource, icon: FileWarning, accent: "text-yellow-300", alert: summary.missingSource > 0 },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
      {cards.map((c) => <StatCard key={c.label} {...c} />)}
    </div>
  );
}