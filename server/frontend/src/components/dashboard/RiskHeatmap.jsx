import React, { useMemo } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import { Flame } from "lucide-react";
import EmptyState from "@/components/shared/EmptyState";

// Municipality concentration heatmap for open anomaly flags + continuity risks.
// AnomalyFlags carry no municipality directly — resolved via linked Contracts.
// ContinuityRisks resolved via linked InfrastructureAssets.
// Severity-weighted so Critical/High items dominate the ranking.

const SEV_WEIGHT = { Critical: 4, High: 3, Medium: 2, Low: 1 };

// Items in these states are no longer "currently reporting" and are excluded.
const ANOMALY_CLOSED = ["Rejected", "FalsePositive"];
const RISK_CLOSED = ["Mitigated", "Archived"];

function heatClass(ratio) {
  if (ratio >= 0.8) return "bg-red-500/80 text-white";
  if (ratio >= 0.55) return "bg-orange-500/70 text-white";
  if (ratio >= 0.3) return "bg-amber-500/60 text-slate-900";
  if (ratio > 0) return "bg-yellow-500/40 text-slate-900";
  return "bg-secondary text-muted-foreground";
}

export default function RiskHeatmap() {
  const { rows: anomalies, isLoading: la } = useEntityData("AnomalyFlags");
  const { rows: risks, isLoading: lr } = useEntityData("ContinuityRisks");
  const { rows: contracts } = useEntityData("Contracts");
  const { rows: assets } = useEntityData("InfrastructureAssets");

  const ranked = useMemo(() => {
    const contractMuni = new Map(contracts.map((c) => [c.contract_id, c.municipality]));
    const assetMuni = new Map(assets.map((a) => [a.asset_id, a.municipality]));
    const byMuni = new Map();

    const bump = (muni, weight, kind) => {
      const key = muni && muni.trim() ? muni.trim() : "Unspecified";
      const e = byMuni.get(key) || { municipality: key, score: 0, anomalies: 0, risks: 0 };
      e.score += weight;
      if (kind === "anomaly") e.anomalies += 1;
      else e.risks += 1;
      byMuni.set(key, e);
    };

    anomalies
      .filter((a) => !ANOMALY_CLOSED.includes(a.review_status))
      .forEach((a) => bump(contractMuni.get(a.contract_id), SEV_WEIGHT[a.severity] || 1, "anomaly"));

    risks
      .filter((r) => !RISK_CLOSED.includes(r.status))
      .forEach((r) => bump(assetMuni.get(r.asset_id), SEV_WEIGHT[r.severity] || 1, "risk"));

    return Array.from(byMuni.values()).sort((x, y) => y.score - x.score);
  }, [anomalies, risks, contracts, assets]);

  const max = ranked.length ? ranked[0].score : 0;
  const loading = la || lr;

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 mb-1">
        <Flame className="h-4 w-4 text-orange-300" />
        <h3 className="text-sm font-semibold">Municipality Risk Heatmap</h3>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Severity-weighted concentration of open anomaly flags and continuity risks by municipality. Higher intensity indicates more / higher-severity unresolved items currently reporting.
      </p>

      {loading ? (
        <p className="text-xs text-muted-foreground">Aggregating signals…</p>
      ) : !ranked.length ? (
        <EmptyState icon={Flame} title="No open signals" description="No unresolved anomaly flags or continuity risks to map." />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {ranked.map((m) => {
            const ratio = max ? m.score / max : 0;
            return (
              <div
                key={m.municipality}
                className={`rounded-lg p-3 transition-colors ${heatClass(ratio)}`}
                title={`${m.anomalies} anomaly flag(s), ${m.risks} continuity risk(s) — weighted score ${m.score}`}
              >
                <div className="text-sm font-medium truncate">{m.municipality}</div>
                <div className="text-lg font-semibold font-mono-id leading-tight">{m.score}</div>
                <div className="text-[11px] opacity-90">
                  {m.anomalies} anomaly · {m.risks} risk
                </div>
              </div>
            );
          })}
        </div>
      )}

      {ranked.length > 0 && (
        <div className="flex items-center gap-3 mt-4 text-[11px] text-muted-foreground">
          <span>Intensity:</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded bg-yellow-500/40" /> low</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-500/60" /> moderate</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-500/70" /> elevated</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500/80" /> high</span>
        </div>
      )}
    </div>
  );
}