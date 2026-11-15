import React from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Gauge, ExternalLink } from "lucide-react";
import { federation } from "@/api/federationClient";
import PageHeader from "@/components/shared/PageHeader";
import StatusChip from "@/components/shared/StatusChip";
import IdCode from "@/components/shared/IdCode";
import EmptyState from "@/components/shared/EmptyState";
import { FRESHNESS, MONITOR_STATUS, TIER } from "@/lib/chips";
import {
  MONITOR_COLLECTION, PRODUCER_PAGES, ageDays, formatLabel, freshnessReference, freshnessState, successBasisLabel,
} from "@/lib/sourceMonitor";

function Field({ label, children }) {
  return (
    <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm sm:col-span-2 sm:mt-0 break-words">{children ?? <span className="text-muted-foreground">—</span>}</dd>
    </div>
  );
}

const rawValue = (v) => (v !== null && typeof v === "object" ? JSON.stringify(v) : String(v ?? ""));

// One monitored source, read-only (ADR 0012). Shows the normalized fields, the
// producer's own registry fields verbatim, and where the row came from.
export default function SourceMonitorDetail() {
  const { monitorId } = useParams();
  const { data: row, isLoading, error } = useQuery({
    queryKey: ["entity", MONITOR_COLLECTION, "get", monitorId],
    queryFn: () => federation.entities[MONITOR_COLLECTION].get(monitorId),
    retry: false,
  });

  const back = (
    <Link to="/source-monitor" className="mb-4 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
      <ArrowLeft className="h-3.5 w-3.5" /> Source Monitor
    </Link>
  );

  if (isLoading) {
    return <div>{back}<p role="status" className="text-sm text-muted-foreground">Loading source…</p></div>;
  }
  if (error || !row) {
    return (
      <div>
        {back}
        <div className="rounded-xl border border-border bg-card">
          <EmptyState title="Monitored source not found"
            description={`No ${MONITOR_COLLECTION} row with id ${monitorId}. It may have been dropped from its producer registry on the last ingest.`} />
        </div>
      </div>
    );
  }

  const freshness = freshnessState(row);
  const age = ageDays(row);
  const reference = freshnessReference(row);
  const when = (value) => (value ? new Date(value).toLocaleString() : null);
  const raw = Object.entries(row.raw || {});
  const producerPage = PRODUCER_PAGES[row.producer];

  return (
    <div>
      {back}
      <PageHeader icon={Gauge} title={row.name || row.source_id} badge={row.producer}
        description={row.origin === "stream"
          ? "Read-only. Reported by the producer in its source_monitors stream."
          : "Read-only. Normalized from the producer's source registry by hub source-monitor."} />

      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-labelledby="monitor-normalized" className="rounded-xl border border-border bg-card p-4">
          <h2 id="monitor-normalized" className="mb-2 text-sm font-semibold">Monitoring</h2>
          <dl className="divide-y divide-border">
            <Field label="Source ID"><IdCode>{row.source_id}</IdCode></Field>
            <Field label="Producer">
              {producerPage ? <Link to={producerPage} className="hover:underline">{row.producer}</Link> : row.producer}
            </Field>
            <Field label="Family">{row.producer_family}</Field>
            <Field label="Evidence tier">{row.evidence_tier ? <StatusChip map={TIER} value={row.evidence_tier} /> : null}</Field>
            <Field label="Cadence">
              {formatLabel(row.cadence)}{row.cadence_raw ? <span className="text-muted-foreground"> (registry: {row.cadence_raw})</span> : null}
            </Field>
            <Field label="Declared status">
              <StatusChip map={MONITOR_STATUS} value={formatLabel(row.status)} />
              {row.status_raw ? <span className="ml-2 text-muted-foreground">registry: {row.status_raw}</span> : null}
            </Field>
            <Field label="Freshness">
              <StatusChip map={FRESHNESS} value={freshness} />
              <span className="ml-2 text-muted-foreground">
                {age === null ? "no time to measure from" : `${age}d ago, from the ${
                  reference.kind === "last_success" ? "last success" : "producer's last export package"}`}
              </span>
            </Field>
            <Field label="Last success">
              {when(row.last_success_at)}
              <span className={row.last_success_at ? "ml-2 text-muted-foreground" : "text-muted-foreground"}>
                {row.last_success_at ? `(${successBasisLabel(row).toLowerCase()})` : successBasisLabel(row)}
              </span>
            </Field>
            {row.last_attempt_at ? (
              <Field label="Last attempt">
                {when(row.last_attempt_at)}
                {row.last_attempt_status ? <span className="ml-2 text-muted-foreground">({row.last_attempt_status})</span> : null}
              </Field>
            ) : null}
            <Field label="Producer export">{when(row.producer_last_package_at) || <span className="text-muted-foreground">no export package found</span>}</Field>
            <Field label="Origin">{row.origin === "stream" ? "source_monitors stream" : "hub registry reader"}</Field>
            <Field label="Link">
              {row.url ? (
                <a href={row.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-status-info-fg break-all">
                  {row.url} <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                </a>
              ) : null}
            </Field>
          </dl>
          <p className="mt-3 text-xs text-muted-foreground">
            Freshness compares this source&apos;s last success with its cadence window when the producer reports one
            (run receipt or its own outputs); otherwise it uses the producer&apos;s last export package.
          </p>
        </section>

        <section aria-labelledby="monitor-raw" className="rounded-xl border border-border bg-card p-4">
          <h2 id="monitor-raw" className="mb-2 text-sm font-semibold">Registry fields (verbatim)</h2>
          {raw.length ? (
            <dl className="divide-y divide-border">
              {raw.map(([k, v]) => <Field key={k} label={k.replaceAll("_", " ")}>{rawValue(v)}</Field>)}
            </dl>
          ) : <p className="text-sm text-muted-foreground">No registry fields.</p>}
          <h2 className="mb-2 mt-4 text-sm font-semibold">Lineage</h2>
          <dl className="divide-y divide-border">
            <Field label="Registry file"><code>{row.lineage?.registry_path}</code></Field>
            <Field label="Adapter">{row.lineage?.adapter}</Field>
            <Field label="Observed">{row.observed_at ? new Date(row.observed_at).toLocaleString() : null}</Field>
          </dl>
        </section>
      </div>
    </div>
  );
}
