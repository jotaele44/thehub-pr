import React from "react";
import CrossoverCard from "@/components/crossover/CrossoverCard";
import EmptyState from "@/components/shared/EmptyState";
import { Layers } from "lucide-react";

const CONVERGENCE_TYPES = [
  "Geography", "Agency", "Vendor", "InfrastructureAdjacency", "LandDevelopment",
  "SourceEvidence", "Anomaly", "Temporal", "Contradiction",
];

// Crossovers touching 3+ modules. Grouped by convergence type.
export default function ConvergenceView({ crossovers }) {
  const multi = crossovers.filter((c) => (c.related_modules?.length || 2) >= 3);

  if (multi.length === 0) {
    return (
      <EmptyState
        icon={Layers}
        title="No multi-module convergence yet"
        description="Three-or-more-module convergence appears here once crossover records link records across 3+ modules (e.g. a contract + infrastructure asset + airspace event sharing a municipality). These remain candidates until review-verified."
      />
    );
  }

  return (
    <div className="space-y-5">
      <p className="text-xs text-muted-foreground">
        Convergence indicates where 3+ modules overlap on a shared attribute. Convergence is structural signal requiring source-backed review — not a conclusion.
      </p>
      {CONVERGENCE_TYPES.map((t) => {
        const rows = multi.filter((c) => c.correlation_type === t);
        if (!rows.length) return null;
        return (
          <div key={t}>
            <h4 className="text-sm font-medium mb-2">{t} convergence <span className="text-muted-foreground">({rows.length})</span></h4>
            <div className="grid md:grid-cols-2 gap-3">
              {rows.map((c) => <CrossoverCard key={c.crossover_id} c={c} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}