import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import EntityLedger from "@/components/shared/EntityLedger";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { FRESHNESS, MONITOR_STATUS, TIER } from "@/lib/chips";
import {
  FRESHNESS_STATES, MONITOR_CADENCES, MONITOR_COLLECTION, MONITOR_PRODUCERS,
  MONITOR_STATUSES, MONITOR_TIERS, formatLabel, monitorPath, withFreshness,
} from "@/lib/sourceMonitor";

// One read-only template for monitored sources (ADR 0011). Without `producer` it is
// the federation-wide operator table; with it, a producer page's Sources tab.
// Rows are a projection of producer registries written by `hub source-monitor` and
// replaced on every `hub ingest`, so there is nothing to edit here.
export default function SourceMonitorLedger({ producer, now }) {
  const navigate = useNavigate();
  const nowMs = useMemo(() => now ?? Date.now(), [now]);
  const rowMap = useMemo(() => withFreshness(nowMs), [nowMs]);
  const rowFilter = useMemo(() => (producer ? (r) => r.producer === producer : undefined), [producer]);

  const columns = useMemo(() => [
    ...(producer ? [] : [{
      key: "producer", label: "Producer",
      render: (r) => <span className="text-muted-foreground whitespace-nowrap">{r.producer}</span>,
    }]),
    { key: "source_id", label: "ID", render: (r) => <IdCode>{r.source_id}</IdCode> },
    { key: "name", label: "Name", render: (r) => <span className="font-medium">{r.name || r.source_id}</span> },
    {
      key: "producer_family", label: "Family",
      render: (r) => <span className="text-muted-foreground">{r.producer_family || "—"}</span>,
    },
    { key: "evidence_tier", label: "Tier", render: (r) => <StatusChip map={TIER} value={r.evidence_tier} /> },
    { key: "cadence", label: "Cadence", render: (r) => <span className="text-muted-foreground">{formatLabel(r.cadence)}</span> },
    {
      key: "status", label: "Declared status",
      render: (r) => <StatusChip map={MONITOR_STATUS} value={formatLabel(r.status)} />,
    },
    {
      key: "freshness_rank", label: "Producer export",
      render: (r) => (
        <span className="inline-flex items-center gap-2 whitespace-nowrap">
          <StatusChip map={FRESHNESS} value={r.freshness} />
          <span className="text-xs text-muted-foreground">
            {r.export_age_days === null || r.export_age_days === undefined ? "no export" : `${r.export_age_days}d ago`}
          </span>
        </span>
      ),
    },
  ], [producer]);

  const filterDefs = useMemo(() => [
    ...(producer ? [] : [{ key: "producer", label: "Producer", options: MONITOR_PRODUCERS }]),
    { key: "freshness", label: "Freshness", options: FRESHNESS_STATES },
    { key: "status", label: "Status", options: MONITOR_STATUSES },
    { key: "evidence_tier", label: "Tier", options: MONITOR_TIERS },
    { key: "cadence", label: "Cadence", options: MONITOR_CADENCES },
  ], [producer]);

  return (
    <div>
      <p className="mb-3 text-xs text-muted-foreground">
        Read-only. Sources {producer ? "this producer monitors" : "every producer monitors"}, normalized from
        producer registries by <code>hub source-monitor</code> and replaced on every hub ingest. Freshness is the
        age of the producer&apos;s last export package against each source&apos;s cadence, not a per-source poll.
      </p>
      <EntityLedger
        entityName={MONITOR_COLLECTION}
        columns={columns}
        readOnly
        rowMap={rowMap}
        rowFilter={rowFilter}
        onRowClick={(r) => navigate(monitorPath(r.monitor_id || r.id))}
        initialSort={{ key: "freshness_rank", dir: "asc" }}
        searchKeys={["name", "source_id", "producer_family", "producer"]}
        filterDefs={filterDefs}
        emptyTitle="No monitored sources"
        emptyDescription={
          producer
            ? `No sources from ${producer} in the hub. Run \`hub source-monitor\` against a workspace holding its checkout, then \`hub ingest\`.`
            : "Run `hub source-monitor --root <workspace>` and then `hub ingest` to load producer source registries."
        }
        searchPlaceholder="Search sources…"
      />
    </div>
  );
}
