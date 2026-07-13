import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useEntityData } from "@/hooks/useEntityData";
import PageHeader from "@/components/shared/PageHeader";
import StatCard from "@/components/shared/StatCard";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import EmptyState from "@/components/shared/EmptyState";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SEVERITY, REVIEW_STATUS, GENERIC_STATUS } from "@/lib/chips";
import { domainAccent, MODULES } from "@/lib/federation";
import { cn } from "@/lib/utils";
import { Activity, ShieldAlert, Droplets, Banknote, ScrollText, AlertTriangle, ArrowRight } from "lucide-react";

// Recent Activity — the app's landing page. Surfaces recent risk activity across the
// federation, grouped by the program (module) each signal belongs to. Merges the three
// risk-bearing entities into one normalized, newest-first stream:
//   ContinuityRisks (AguaYLuz) · AnomalyFlags (MoneySweep) · GovernanceAlerts (audit).
// The backend returns the most-recently-written page (ordered by updated_at) per entity;
// we still sort client-side to interleave the three streams. Light polling keeps it live.

const POLL_MS = 30000;
const MAX_PER_GROUP = 8;
const DAY_MS = 24 * 60 * 60 * 1000;

const SEVERITIES = ["Critical", "High", "Medium", "Low"];
// Time windows for the feed. value = max age in ms (null = no bound).
const WINDOWS = [
  { value: "all", label: "All time", ms: null },
  { value: "7d", label: "Last 7 days", ms: 7 * DAY_MS },
  { value: "30d", label: "Last 30 days", ms: 30 * DAY_MS },
];

// Per-kind rendering config + the program a signal defaults to when it carries no explicit
// program_id / module. The default label doubles as the matcher key against Programs rows.
// "Closedness" mirrors the conventions already used elsewhere so the Open KPI stays consistent:
// ContinuityRisk/AnomalyFlag carry closed-lists (from RiskHeatmap.jsx); GovernanceAlert instead
// defines its OPEN states (from GovernanceAlertsPanel.jsx) and treats everything else as closed.
const KINDS = {
  ContinuityRisk: { label: "Continuity Risk", icon: Droplets, statusMap: GENERIC_STATUS, defaultProgram: "AguaYLuz-PR", closed: ["Mitigated", "Archived"] },
  AnomalyFlag: { label: "Anomaly Flag", icon: Banknote, statusMap: REVIEW_STATUS, defaultProgram: "MoneySweep-PR", closed: ["Rejected", "FalsePositive"] },
  GovernanceAlert: { label: "Governance Alert", icon: ScrollText, statusMap: REVIEW_STATUS, defaultProgram: "Federation / Control", open: ["Open", "Acknowledged"] },
};

// A signal is closed when its kind lists the status as closed, or (for kinds that instead
// declare their open states) when the status is not among them.
function isClosed(cfg, status) {
  if (cfg.open) return !cfg.open.includes(status);
  return cfg.closed.includes(status);
}

const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
const toTime = (v) => { const t = v ? new Date(v).getTime() : NaN; return Number.isNaN(t) ? 0 : t; };
const fmt = (v) => { const t = toTime(v); return t ? new Date(t).toLocaleString() : "—"; };

// Relative "updated Xs ago" for the freshness badge.
function ago(ts) {
  if (!ts) return "never";
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

// Resolve a group (its program name / domain) to a producer module route, if one exists,
// so the section can link to that module's page. Fuzzy-match on name then domain.
function modulePathFor(group) {
  const nName = norm(group.name);
  const byName = nName
    ? MODULES.find((m) => { const nm = norm(m.name); return nm && (nm.includes(nName) || nName.includes(nm)); })
    : null;
  const mod = byName || (group.domain ? MODULES.find((m) => norm(m.domain) === norm(group.domain)) : null);
  return mod ? mod.path : null;
}

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
    closed: isClosed(cfg, status),
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
  const { rows: risks, isLoading: lr, dataUpdatedAt: ur } = useEntityData("ContinuityRisks", "-updated_date", { refetchInterval: POLL_MS });
  const { rows: anomalies, isLoading: la, dataUpdatedAt: ua } = useEntityData("AnomalyFlags", "-updated_date", { refetchInterval: POLL_MS });
  const { rows: alerts, isLoading: lg, dataUpdatedAt: ug } = useEntityData("GovernanceAlerts", "-updated_date", { refetchInterval: POLL_MS });
  const { rows: programs } = useEntityData("Programs");

  const [severity, setSeverity] = useState("all");
  const [timeWindow, setTimeWindow] = useState("all");

  const loading = lr || la || lg;
  const updatedAt = Math.max(ur || 0, ua || 0, ug || 0);

  const groups = useMemo(() => {
    const windowMs = WINDOWS.find((w) => w.value === timeWindow)?.ms ?? null;
    const cutoff = windowMs ? Date.now() - windowMs : null;

    const items = [
      ...risks.map((r) => normalize("ContinuityRisk", r)),
      ...anomalies.map((a) => normalize("AnomalyFlag", a)),
      ...alerts.map((g) => normalize("GovernanceAlert", g)),
    ].filter((it) => (severity === "all" || it.severity === severity)
                  && (cutoff === null || it.ts >= cutoff));

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
  }, [risks, anomalies, alerts, programs, severity, timeWindow]);

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
        actions={
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className={cn("h-2 w-2 rounded-full", loading ? "bg-status-warning animate-pulse" : "bg-status-success")} />
            <span>updated {ago(updatedAt)}</span>
            <span className="hidden sm:inline">· auto every {Math.round(POLL_MS / 1000)}s</span>
          </div>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <StatCard label="Risk Signals" value={totals.total} icon={Activity} />
        <StatCard label="Open" value={totals.open} icon={ShieldAlert} />
        <StatCard label="Critical / High" value={totals.critHigh} icon={AlertTriangle} accent="text-status-danger-fg" alert={totals.critHigh > 0} />
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-8">
        <Select value={severity} onValueChange={setSeverity}>
          <SelectTrigger className="w-40 h-9"><SelectValue placeholder="Severity" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All severities</SelectItem>
            {SEVERITIES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={timeWindow} onValueChange={setTimeWindow}>
          <SelectTrigger className="w-40 h-9"><SelectValue placeholder="Window" /></SelectTrigger>
          <SelectContent>
            {WINDOWS.map((w) => <SelectItem key={w.value} value={w.value}>{w.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {loading && !groups.length ? (
        <p className="text-xs text-muted-foreground">Aggregating risk activity…</p>
      ) : !groups.length ? (
        (risks.length || anomalies.length || alerts.length) ? (
          <EmptyState icon={Activity} title="No matching activity" description="No risk activity matches the current severity / time-window filters." />
        ) : (
          <EmptyState icon={Activity} title="No risk activity" description="No continuity risks, anomaly flags, or governance alerts have been recorded yet." />
        )
      ) : (
        <div className="space-y-6">
          {groups.map((g) => {
            const accent = g.domain ? domainAccent(g.domain) : null;
            const shown = g.items.slice(0, MAX_PER_GROUP);
            const modulePath = modulePathFor(g);
            return (
              <div key={g.id} className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center gap-2 mb-4">
                  <span className={cn("h-2.5 w-2.5 rounded-full shrink-0", accent ? accent.dot : "bg-muted-foreground/50")} />
                  {modulePath ? (
                    <Link to={modulePath} className="group inline-flex items-center gap-1.5">
                      <h3 className="text-sm font-semibold group-hover:underline">{g.name}</h3>
                      <ArrowRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    </Link>
                  ) : (
                    <h3 className="text-sm font-semibold">{g.name}</h3>
                  )}
                  {g.domain && <span className="text-xs text-muted-foreground">· {g.domain}</span>}
                  <span className="ml-auto inline-flex items-center gap-2">
                    {g.open > 0 && (
                      <span className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-status-danger/20 text-status-danger-fg text-xs font-mono-id" title={`${g.open} open`}>
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
