import React, { useMemo } from "react";
import { useEntityData } from "@/hooks/useEntityData";
import PageHeader from "@/components/shared/PageHeader";
import StatCard from "@/components/shared/StatCard";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import EmptyState from "@/components/shared/EmptyState";
import { SEVERITY, REVIEW_STATUS, GENERIC_STATUS } from "@/lib/chips";
import { domainAccent } from "@/lib/federation";
import { cn } from "@/lib/utils";
import { Activity, ShieldAlert, Droplets, Banknote, ScrollText, AlertTriangle } from "lucide-react";

// Recent Activity — the app's landing page. Surfaces recent risk activity across the
// federation, grouped by the program (module) each signal belongs to. Merges the three
// risk-bearing entities into one normalized, newest-first stream:
//   ContinuityRisks (AguaYLuz) · AnomalyFlags (MoneySweep) · GovernanceAlerts (audit).
// The backend stamps created_date/updated_date on every write but ignores the sort param,
// so ordering happens client-side here. Light polling keeps the feed live like useLiveFeed.

const POLL_MS = 30000;
const MAX_PER_GROUP = 8;

// Per-kind rendering config + the program a signal defaults to when it carries no explicit
// program_id / module. The default label doubles as the matcher key against Programs rows.
const KINDS = {
  ContinuityRisk: { label: "Continuity Risk", icon: Droplets, statusMap: GENERIC_STATUS, defaultProgram: "AguaYLuz-PR", closed: ["Mitigated", "Archived"] },
  AnomalyFlag: { label: "Anomaly Flag", icon: Banknote, statusMap: REVIEW_STATUS, defaultProgram: "MoneySweep-PR", closed: ["Rejected", "FalsePositive"] },
  GovernanceAlert: { label: "Governance Alert", icon: ScrollText, statusMap: REVIEW_STATUS, defaultProgram: "Federation / Control", closed: ["Resolved", "Dismissed", "FalsePositive"] },
};

const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
const toTime = (v) => { const t = v ? new Date(v).getTime() : NaN; return Number.isNaN(t) ? 0 : t; };
const fmt = (v) => { const t = toTime(v); return t ? new Date(t).toLocaleString() : "—"; };

// Normalize one raw entity row into the shared activity shape.
function normalize(kind, raw) {
  const cfg = KINDS[kind];
  const programKey = raw.program_id || raw.module || cfg.defaultProgram;
  const status =
    kind === "ContinuityRisk" ? raw.status :
    kind === "AnomalyFlag" ? raw.review_status : raw.review_status;
  const title =
    kind === "ContinuityRisk" ? (raw.summary || raw.risk_type) :
    kind === "AnomalyFlag" ? (raw.rationale || raw.flag_type) : raw.summary;
  const recordId =
    kind === "ContinuityRisk" ? raw.risk_id :
    kind === "AnomalyFlag" ? raw.flag_id : raw.record_id;
  const timestamp =
    kind === "GovernanceAlert" ? (raw.occurred_at || raw.updated_date || raw.created_date)
                               : (raw.updated_date || raw.created_date);
  return {
    id: raw.id || `${kind}:${recordId}`,
    kind,
    severity: raw.severity,
    status,
    statusMap: cfg.statusMap,
    title: title || cfg.label,
    recordId,
    entityName: raw.entity_name,
    actor: raw.actor,
    timestamp,
    ts: toTime(timestamp),
    programKey,
    closed: cfg.closed.includes(status),
  };
}

function RiskActivityRow({ item }) {
  const Icon = KINDS[item.kind].icon;
  return (
    <div className={cn("flex items-start gap-3 rounded-lg border border-border bg-secondary/40 p-3", item.closed && "opacity-60")}>
      <Icon className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-1.5 mb-1">
          <StatusChip map={SEVERITY} value={item.severity} />
          <StatusChip map={item.statusMap} value={item.status} />
          <span className="text-xs text-muted-foreground">{KINDS[item.kind].label}</span>
          {item.entityName && <span className="text-xs text-muted-foreground">· {item.entityName}</span>}
          <IdCode>{item.recordId}</IdCode>
        </div>
        <p className="text-sm text-foreground/90 truncate" title={item.title}>{item.title}</p>
        <div className="text-[11px] text-muted-foreground mt-0.5">
          {item.actor ? `${item.actor} · ` : ""}{fmt(item.timestamp)}
        </div>
      </div>
    </div>
  );
}

export default function RecentActivity() {
  const { rows: risks, isLoading: lr } = useEntityData("ContinuityRisks", "-updated_date", { refetchInterval: POLL_MS });
  const { rows: anomalies, isLoading: la } = useEntityData("AnomalyFlags", "-updated_date", { refetchInterval: POLL_MS });
  const { rows: alerts, isLoading: lg } = useEntityData("GovernanceAlerts", "-updated_date", { refetchInterval: POLL_MS });
  const { rows: programs } = useEntityData("Programs");

  const loading = lr || la || lg;

  const groups = useMemo(() => {
    const items = [
      ...risks.map((r) => normalize("ContinuityRisk", r)),
      ...anomalies.map((a) => normalize("AnomalyFlag", a)),
      ...alerts.map((g) => normalize("GovernanceAlert", g)),
    ];

    // Resolve a program key to a Programs row (by id / name / repo, fuzzy) for a nice header.
    const matchProgram = (key) => {
      const k = norm(key);
      if (!k) return null;
      return programs.find((p) =>
        [p.program_id, p.name, p.repo_name, p.old_name].some((f) => {
          const nf = norm(f);
          return nf && (nf.includes(k) || k.includes(nf));
        })
      ) || null;
    };

    const byGroup = new Map();
    items.forEach((it) => {
      const prog = matchProgram(it.programKey);
      const groupId = prog ? prog.program_id : `raw:${norm(it.programKey)}`;
      let g = byGroup.get(groupId);
      if (!g) {
        g = { id: groupId, name: prog ? prog.name : it.programKey, domain: prog ? prog.domain : null, items: [] };
        byGroup.set(groupId, g);
      }
      g.items.push(it);
    });

    const list = Array.from(byGroup.values());
    list.forEach((g) => {
      g.items.sort((x, y) => y.ts - x.ts);
      g.open = g.items.filter((i) => !i.closed).length;
      g.newest = g.items.length ? g.items[0].ts : 0;
    });
    list.sort((x, y) => y.newest - x.newest);
    return list;
  }, [risks, anomalies, alerts, programs]);

  const totals = useMemo(() => {
    const all = groups.flatMap((g) => g.items);
    const open = all.filter((i) => !i.closed);
    const critHigh = open.filter((i) => i.severity === "Critical" || i.severity === "High");
    return { total: all.length, open: open.length, critHigh: critHigh.length };
  }, [groups]);

  return (
    <div>
      <PageHeader
        icon={Activity}
        title="Recent Activity"
        description="Latest risk activity across the federation, grouped by program. Continuity risks, anomaly flags, and governance alerts — newest first. Leads for review, not conclusions."
      />

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <StatCard label="Risk Signals" value={totals.total} icon={Activity} />
        <StatCard label="Open" value={totals.open} icon={ShieldAlert} />
        <StatCard label="Critical / High" value={totals.critHigh} icon={AlertTriangle} accent="text-red-300" alert={totals.critHigh > 0} />
      </div>

      {loading && !groups.length ? (
        <p className="text-xs text-muted-foreground">Aggregating risk activity…</p>
      ) : !groups.length ? (
        <EmptyState icon={Activity} title="No risk activity" description="No continuity risks, anomaly flags, or governance alerts have been recorded yet." />
      ) : (
        <div className="space-y-6">
          {groups.map((g) => {
            const accent = g.domain ? domainAccent(g.domain) : null;
            const shown = g.items.slice(0, MAX_PER_GROUP);
            return (
              <div key={g.id} className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center gap-2 mb-4">
                  <span className={cn("h-2.5 w-2.5 rounded-full shrink-0", accent ? accent.dot : "bg-muted-foreground/50")} />
                  <h3 className="text-sm font-semibold">{g.name}</h3>
                  {g.domain && <span className="text-xs text-muted-foreground">· {g.domain}</span>}
                  <span className="ml-auto inline-flex items-center gap-2">
                    {g.open > 0 && (
                      <span className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-red-500/20 text-red-300 text-xs font-mono-id" title={`${g.open} open`}>
                        {g.open}
                      </span>
                    )}
                    <span className="text-[11px] text-muted-foreground">{g.items.length} signal{g.items.length === 1 ? "" : "s"}</span>
                  </span>
                </div>
                <div className="space-y-2">
                  {shown.map((it) => <RiskActivityRow key={it.id} item={it} />)}
                </div>
                {g.items.length > MAX_PER_GROUP && (
                  <p className="text-xs text-muted-foreground mt-3">+{g.items.length - MAX_PER_GROUP} older signal(s) in this program.</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
