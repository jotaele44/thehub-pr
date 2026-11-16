import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import EntityLedger from "@/components/shared/EntityLedger";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import { useEntityData } from "@/hooks/useEntityData";
import { FRESHNESS, MONITOR_STATUS, TIER } from "@/lib/chips";
import {
  FRESHNESS_STATES, MONITOR_CADENCES, MONITOR_COLLECTION, MONITOR_LIST_LIMIT, MONITOR_PRODUCERS,
  MONITOR_STATUSES, MONITOR_SUMMARY_COLLECTION, MONITOR_SUMMARY_ID, MONITOR_TIERS, SUCCESS_BASES,
  familyOptions, formatLabel, monitorPath, withFreshness,
} from "@/lib/sourceMonitor";

// The list loads at most MONITOR_LIST_LIMIT rows across every producer, so one
// producer's tab can be cut short while the federation total is over the limit.
// Says so when the summary holds more of this producer's sources than loaded.
// `ready` is false until the first rows arrive: before then every producer would
// look cut short. The summary is still requested, alongside the rows.
function ProducerLimitNotice({ producer, loaded, ready }) {
  const { rows: summaries } = useEntityData(MONITOR_SUMMARY_COLLECTION);
  const summary = summaries.find((s) => s.id === MONITOR_SUMMARY_ID);
  const total = Number(summary?.total ?? 0);
  const held = Number(summary?.producers?.[producer]?.count ?? 0);
  if (!ready || !(total > MONITOR_LIST_LIMIT) || !(held > loaded)) return null;
  return (
    <div role="alert" className="mb-4 rounded-lg border border-status-warning/30 bg-status-warning/15 px-4 py-2.5 text-xs text-status-warning-fg">
      The hub holds {held} sources from {producer} but this tab shows {loaded}: the table loads the first{" "}
      {MONITOR_LIST_LIMIT} of {total} monitored sources across all producers.
    </div>
  );
}

// One read-only template for monitored sources (ADR 0012). Without `producer` it is
// the federation-wide operator table; with it, a producer page's Monitor tab.
// Rows come from each producer's source_monitors stream where it emits one (ADR 0013)
// and otherwise from its registry via `hub source-monitor`; `hub ingest` replaces them
// on every run, so there is nothing to edit here.
export default function SourceMonitorLedger({ producer, now }) {
  const navigate = useNavigate();
  // The same call EntityLedger makes for this collection, so both read one
  // react-query entry (["entity", MONITOR_COLLECTION, "-created_date"]) and one request.
  const { rows, isFetching } = useEntityData(MONITOR_COLLECTION);
  const nowMs = useMemo(() => now ?? Date.now(), [now]);
  const rowMap = useMemo(() => withFreshness(nowMs), [nowMs]);
  const rowFilter = useMemo(() => (producer ? (r) => r.producer === producer : undefined), [producer]);
  const scoped = useMemo(() => (rowFilter ? rows.filter(rowFilter) : rows), [rows, rowFilter]);
  const families = useMemo(() => familyOptions(scoped), [scoped]);

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
      key: "freshness_rank", label: "Freshness",
      render: (r) => (
        <span className="inline-flex flex-col gap-0.5 whitespace-nowrap">
          <span className="inline-flex items-center gap-2">
            <StatusChip map={FRESHNESS} value={r.freshness} />
            <span className="text-xs text-muted-foreground">
              {r.age_days === null || r.age_days === undefined ? "no time" : `${r.age_days}d ago`}
            </span>
          </span>
          <span className="text-[11px] text-muted-foreground" data-freshness-kind={r.freshness_kind}>
            {r.freshness_kind === "last_success" ? `last success · ${r.success_basis.toLowerCase()}` : "producer export"}
          </span>
        </span>
      ),
    },
  ], [producer]);

  const filterDefs = useMemo(() => [
    ...(producer ? [] : [{ key: "producer", label: "Producer", options: MONITOR_PRODUCERS }]),
    // Present from the first render, before any row loads: useTableFilter sets each
    // filter's "all" state once, so a filter added later would start undefined and
    // hide every row. Only its options follow the rows.
    { key: "producer_family", label: "Family", options: families },
    { key: "freshness", label: "Freshness", options: FRESHNESS_STATES },
    { key: "success_basis", label: "Basis", options: SUCCESS_BASES },
    { key: "status", label: "Status", options: MONITOR_STATUSES },
    { key: "evidence_tier", label: "Tier", options: MONITOR_TIERS },
    { key: "cadence", label: "Cadence", options: MONITOR_CADENCES },
  ], [producer, families]);

  return (
    <div>
      <p className="mb-3 text-xs text-muted-foreground">
        Read-only. Sources {producer ? "this producer monitors" : "every producer monitors"}, from the
        producer&apos;s <code>source_monitors</code> stream where it emits one and otherwise from its registry via{" "}
        <code>hub source-monitor</code>; replaced on every hub ingest. Freshness uses a source&apos;s own last
        success when the producer reports one, and otherwise the age of the producer&apos;s last export package.
      </p>
      {producer ? (
        <ProducerLimitNotice producer={producer} loaded={scoped.length} ready={!(isFetching && rows.length === 0)} />
      ) : null}
      <EntityLedger
        entityName={MONITOR_COLLECTION}
        columns={columns}
        readOnly
        rowMap={rowMap}
        rowFilter={rowFilter}
        onRowClick={(r) => navigate(
          monitorPath(r.monitor_id || r.id),
          // The detail page's back link returns to this producer's Monitor tab.
          producer ? { state: { fromProducer: producer } } : undefined,
        )}
        initialSort={{ key: "freshness_rank", dir: "asc" }}
        searchKeys={["name", "source_id", "producer_family", "producer"]}
        filterDefs={filterDefs}
        emptyTitle="No monitored sources"
        emptyDescription={
          producer
            ? `No sources from ${producer} in the hub. If it emits the source_monitors stream, they arrive with \`hub aggregate\` and then \`hub ingest\`; otherwise run \`hub source-monitor\` against a workspace holding its checkout, then \`hub ingest\`.`
            : "Producers that emit the source_monitors stream load with `hub aggregate` and then `hub ingest`. For the others, run `hub source-monitor --root <workspace>` and then `hub ingest` to read their source registries."
        }
        searchPlaceholder="Search sources…"
      />
    </div>
  );
}
