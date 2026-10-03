import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { federation } from '@/api/federationClient';
import IdCode from '@/components/shared/IdCode';
import { cn } from '@/lib/utils';

// Shared pieces for the OVNIS research views (Research Hub, case
// reconstruction, reports, show log). Every list reads one research kind from
// /api/research/records/{kind}; an empty ledger says so instead of rendering a
// silent empty list, because OVNIS records research only through curators.

export const chip = 'inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold';

export const FALSIFICATION_LABELS = {
  identity_errors: 'Identity errors',
  duplicate_manifestations: 'Duplicate manifestations',
  ordinary_explanations: 'Ordinary explanations',
  background_prevalence: 'Background prevalence',
  missing_data: 'Missing data',
  source_dependence: 'Source dependence',
  temporal_mismatch: 'Temporal mismatch',
  geometry_uncertainty: 'Geometry uncertainty',
  contradictions: 'Contradictions',
};

const STATUS_NOTES = {
  CANDIDATE: 'not yet reviewed',
  ACCEPTED: 'accepted by a reviewer as supported by its cited sources; not an established fact',
};

export function StatusBadge({ status, origin }) {
  if (!status) return null;
  const note = origin === 'COMPUTED' && status === 'CANDIDATE' ? 'computed, not reviewed' : STATUS_NOTES[status];
  return (
    <span className={cn(chip, 'border-border text-foreground')} data-record-status={status} title={note}>
      {status}{note ? <span className="ml-1 font-normal text-muted-foreground">· {note}</span> : null}
    </span>
  );
}

export function CaseLink({ caseId }) {
  return (
    <Link className="text-primary underline" to={`/research/case/${encodeURIComponent(caseId)}`} data-case-link={caseId}>
      <IdCode>{caseId}</IdCode>
    </Link>
  );
}

export function CaseLinks({ caseIds }) {
  if (!caseIds?.length) return <span className="text-muted-foreground">no case named</span>;
  return (
    <span className="inline-flex flex-wrap gap-2">
      {caseIds.map((caseId) => <CaseLink key={caseId} caseId={caseId} />)}
    </span>
  );
}

export function SourceRefs({ refs }) {
  if (!refs?.length) return <span className="text-muted-foreground">no source cited</span>;
  return (
    <ul className="space-y-1">
      {refs.map((ref, index) => (
        <li key={`${ref.case_id || ref.source_id}-${index}`} className="text-xs">
          {ref.case_id ? <>Case <CaseLink caseId={ref.case_id} /></> : <>Registry source <IdCode>{ref.source_id}</IdCode></>}
          {' · '}{ref.locator}
          {ref.quote ? <q className="ml-1 text-muted-foreground">{ref.quote}</q> : null}
        </li>
      ))}
    </ul>
  );
}

export function EmptyLedger({ children }) {
  return (
    <p role="status" className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground" data-empty-ledger>
      {children}
    </p>
  );
}

/** One research kind, page by page. `children(record)` renders a record. */
export function ResearchRecordList({ kind, emptyText, params = {}, children }) {
  const [cursor, setCursor] = useState(undefined);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['research-records', kind, params, cursor],
    queryFn: () => federation.research.records(kind, { ...params, cursor }),
  });
  if (isLoading) return <p role="status" className="text-sm text-muted-foreground">Loading…</p>;
  if (isError) {
    return (
      <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
        Research records are unavailable: {String(error?.message || error)}
      </div>
    );
  }
  if (data.kind_status === 'NONE_RECORDED') return <EmptyLedger>{emptyText}</EmptyLedger>;
  return (
    <div className="space-y-3" data-research-kind={kind}>
      <p className="text-xs text-muted-foreground" data-research-summary>
        {data.matched} of {data.total} recorded
      </p>
      <ul className="space-y-3">
        {data.records.map((record) => (
          <li key={record.record_id} className="rounded-xl border border-border bg-card p-4" data-research-record={record.record_id}>
            {children(record)}
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        {cursor ? (
          <button type="button" className="min-h-[44px] rounded-md border border-border px-3 text-sm" onClick={() => setCursor(undefined)}>
            First page
          </button>
        ) : null}
        {data.next_cursor ? (
          <button type="button" className="min-h-[44px] rounded-md border border-border px-3 text-sm" onClick={() => setCursor(data.next_cursor)}>
            More
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function FalsificationChecklist({ checks }) {
  return (
    <table className="mt-2 w-full text-left text-xs">
      <caption className="sr-only">Falsification checks</caption>
      <thead>
        <tr className="text-muted-foreground">
          <th scope="col" className="py-1 pr-3 font-medium">Check</th>
          <th scope="col" className="py-1 pr-3 font-medium">Status</th>
          <th scope="col" className="py-1 font-medium">Note</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(FALSIFICATION_LABELS).map(([key, label]) => {
          const check = checks?.[key] || {};
          return (
            <tr key={key} className="border-t border-border" data-falsification-check={key}>
              <th scope="row" className="py-1 pr-3 font-normal">{label}</th>
              <td className="py-1 pr-3 font-mono">{check.status || 'NOT_RUN'}</td>
              <td className="py-1">{check.note || ''}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function CandidateSignals({ signals }) {
  if (!signals) return null;
  return (
    <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4" data-candidate-signals>
      <div><dt className="text-muted-foreground">Dates</dt><dd>{signals.date_relation === 'IDENTICAL_RECORDED_DATE' ? 'identical recorded date' : 'agree at the coarser precision'}</dd></div>
      <div><dt className="text-muted-foreground">Place</dt><dd>{signals.place_basis === 'MUNICIPALITY' ? 'same municipality' : 'near-identical location text'}</dd></div>
      <div><dt className="text-muted-foreground">Narrative similarity</dt><dd>{Math.round((signals.narrative_similarity || 0) * 100)}%</dd></div>
      <div><dt className="text-muted-foreground">Same source</dt><dd>{signals.same_source ? 'yes' : 'no'}</dd></div>
    </dl>
  );
}
