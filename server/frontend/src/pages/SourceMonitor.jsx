import React from "react";
import { Link } from "react-router-dom";
import { Gauge, AlertTriangle, Clock, Layers } from "lucide-react";
import PageHeader from "@/components/shared/PageHeader";
import StatCard from "@/components/shared/StatCard";
import SourceMonitorLedger from "@/components/sources/SourceMonitorLedger";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useEntityData } from "@/hooks/useEntityData";
import {
  MONITOR_LIST_LIMIT, MONITOR_SUMMARY_COLLECTION, MONITOR_SUMMARY_ID, PRODUCER_PAGES,
} from "@/lib/sourceMonitor";

// Federation-wide, read-only Source Monitor (ADR 0012): the operator view. Each
// producer page carries the same table scoped to that producer as a Sources tab.
export default function SourceMonitor() {
  const { rows: summaries } = useEntityData(MONITOR_SUMMARY_COLLECTION);
  const summary = summaries.find((s) => s.id === MONITOR_SUMMARY_ID) || summaries[0] || null;
  const producers = Object.entries(summary?.producers || {}).sort(([a], [b]) => a.localeCompare(b));
  const withErrors = producers.filter(([, p]) => (p.errors || []).length).length;
  const withoutExport = producers.filter(([, p]) => !p.package_created_at).length;

  return (
    <div>
      <PageHeader
        icon={Gauge}
        title="Source Monitor"
        description="Read-only view of the sources each producer monitors, normalized from producer registries. Stalest first."
      />

      {summary && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <StatCard label="Monitored sources" value={summary.total ?? 0} icon={Layers} />
            <StatCard label="Producers" value={producers.length} icon={Gauge} />
            <StatCard label="Registry errors" value={summary.error_count ?? 0} icon={AlertTriangle}
              alert={(summary.error_count ?? 0) > 0} sub={`${withErrors} producer(s) affected`} />
            <StatCard label="No export timestamp" value={withoutExport} icon={Clock}
              sub="freshness unknown for these producers" />
          </div>

          {(summary.total ?? 0) > MONITOR_LIST_LIMIT && (
            <div role="alert" className="mb-4 rounded-lg border border-status-warning/30 bg-status-warning/15 px-4 py-2.5 text-xs text-status-warning-fg">
              The hub holds {summary.total} monitored sources but this table loads the first {MONITOR_LIST_LIMIT}.
            </div>
          )}

          <div className="mb-6 rounded-xl border border-border bg-card overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Producer</TableHead>
                    <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Sources</TableHead>
                    <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Last export package</TableHead>
                    <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Registries</TableHead>
                    <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Notes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {producers.map(([pid, p]) => {
                    const excluded = Object.entries(p.excluded || {});
                    return (
                      <TableRow key={pid} className="border-border">
                        <TableCell className="text-sm font-medium">
                          {PRODUCER_PAGES[pid] ? <Link to={PRODUCER_PAGES[pid]} className="hover:underline">{pid}</Link> : pid}
                        </TableCell>
                        <TableCell className="text-sm font-mono-id">{p.count ?? 0}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {p.package_created_at ? new Date(p.package_created_at).toLocaleString() : "none found"}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {(p.registries || []).map((r) => <div key={r}><code>{r}</code></div>)}
                        </TableCell>
                        <TableCell className="text-xs">
                          {(p.errors || []).map((e) => <div key={e} className="text-status-danger-fg">{e}</div>)}
                          {excluded.map(([reason, n]) => (
                            <div key={reason} className="text-muted-foreground">{n} excluded: {reason.replaceAll("_", " ")}</div>
                          ))}
                          {!(p.errors || []).length && !excluded.length && <span className="text-muted-foreground">—</span>}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
            <p className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
              Built {summary.generated_at ? new Date(summary.generated_at).toLocaleString() : "—"} by{" "}
              <code>hub source-monitor</code> ({summary.adapter || "—"}).
            </p>
          </div>
        </>
      )}

      <SourceMonitorLedger />
    </div>
  );
}
