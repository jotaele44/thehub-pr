import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink } from 'lucide-react';
import { federation } from '@/api/federationClient';
import PageHeader from '@/components/shared/PageHeader';
import IdCode from '@/components/shared/IdCode';
import { PRECISION_LABEL } from '@/pages/Timeline';
import {
  CandidateSignals, CaseLink, EmptyLedger, FalsificationChecklist, SourceRefs, StatusBadge,
} from '@/components/research/ResearchRecords';

// Case reconstruction (FDX-016) and the case report viewer (TWIN-013/222/223):
// one OVNIS case with its source, its report, and every research record that
// names it. Dates keep their recorded precision; a duplicate candidate shows
// what the other case records and stays unreviewed until a curator decides it.

function Section({ title, count, children, empty }) {
  return (
    <section aria-label={title} className="space-y-2" data-case-section={title}>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {title}{count !== undefined ? ` (${count})` : ''}
      </h2>
      {count === 0 ? <p className="text-sm text-muted-foreground">{empty}</p> : children}
    </section>
  );
}

function Report({ body, status }) {
  if (status !== 'HELD') {
    return (
      <EmptyLedger>
        This Hub&apos;s store does not hold the report for this case. OVNIS exports one report per case; the committed fixture holds a sample.
      </EmptyLedger>
    );
  }
  const receipt = body.receipt || {};
  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4" data-case-report={body.report_id}>
      <div>
        <h3 className="text-sm font-semibold">Evidence ids</h3>
        <ul className="text-xs">
          {Object.entries(body.evidence_ids || {}).map(([name, id]) => (
            <li key={name}>{name}: <IdCode>{id}</IdCode></li>
          ))}
        </ul>
      </div>
      <div>
        <h3 className="text-sm font-semibold">Unresolved</h3>
        {body.unresolved?.length ? (
          <ul className="list-disc pl-5 text-sm" data-unresolved>
            {body.unresolved.map((item, index) => (
              <li key={`${item.kind}-${index}`}>{item.detail}{item.ref ? <> (<IdCode>{item.ref}</IdCode>)</> : null}</li>
            ))}
          </ul>
        ) : <p className="text-sm text-muted-foreground">Nothing is recorded as unresolved.</p>}
      </div>
      <div>
        <h3 className="text-sm font-semibold">Reproducibility receipt</h3>
        <dl className="grid gap-1 text-xs sm:grid-cols-2" data-report-receipt>
          <div><dt className="text-muted-foreground">Run</dt><dd><IdCode>{receipt.run_id}</IdCode></dd></div>
          <div><dt className="text-muted-foreground">Report sha256</dt><dd className="break-all font-mono">{receipt.report_sha256}</dd></div>
          <div><dt className="text-muted-foreground">Snapshot</dt><dd className="break-all font-mono">{receipt.snapshot_id}</dd></div>
          <div><dt className="text-muted-foreground">Generated</dt><dd>{receipt.created_at}</dd></div>
        </dl>
      </div>
    </div>
  );
}

export default function CaseReconstruction() {
  const { caseId } = useParams();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['research-case', caseId],
    queryFn: () => federation.research.caseRecord(caseId),
    retry: false,
  });

  if (isLoading) return <p role="status" className="p-4 text-sm text-muted-foreground">Loading case {caseId}…</p>;
  if (isError) {
    return (
      <div className="space-y-4 p-4 md:p-8">
        <PageHeader title={`Case ${caseId}`} description="OVNIS case reconstruction" />
        <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          This case cannot be shown: {String(error?.message || error)}
        </div>
      </div>
    );
  }

  const { case: record, source } = data;
  const place = record.place.municipality || record.place.location_name || 'Place not recorded';
  return (
    <div className="space-y-6 p-4 md:p-8">
      <PageHeader
        title={`Case ${record.case_id}`}
        description="Everything this Hub holds about one OVNIS case, as recorded. Nothing here is inferred, and no case is merged with another."
      />
      <section aria-label="Case as recorded" className="space-y-2 rounded-xl border border-border bg-card p-4" data-case-record={record.case_id}>
        <h2 className="text-base font-semibold">{record.title}</h2>
        <p className="text-sm">
          <time className="font-mono" dateTime={record.date || undefined}>{record.date || 'Undated'}{record.time ? ` ${record.time}` : ''}</time>
          {' '}<span className="text-xs text-muted-foreground" data-temporal-precision={record.temporal_precision}>({PRECISION_LABEL[record.temporal_precision] || 'undated'})</span>
          {' · '}{place}
          {record.category ? ` · ${record.category}` : ''}
          {record.evidence_tier ? ` · Tier ${record.evidence_tier}` : ''}
        </p>
        <p className="text-sm">{record.narrative || <span className="text-muted-foreground">No narrative was exported for this case.</span>}</p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {source ? (
            <>
              <span>Source: {source.name || source.ref || source.source_id}</span>
              {/^https?:\/\//i.test(source.url || '') ? (
                <a className="inline-flex items-center gap-1 text-primary underline" href={source.url} target="_blank" rel="noreferrer noopener">
                  Open source <ExternalLink className="h-3 w-3" aria-hidden="true" />
                </a>
              ) : null}
              <Link className="text-primary underline" to={source.evidence_href}>Source provenance</Link>
            </>
          ) : <span className="text-muted-foreground">Source not held by the Hub</span>}
          <Link className="text-primary underline" to={record.evidence_href}>Provenance</Link>
          <Link className="text-primary underline" to={record.entity_href}>Case composition</Link>
        </div>
      </section>

      <Section title="Case report">
        <Report body={data.report} status={data.report_status} />
      </Section>

      <Section title="Duplicate candidates and adjudications" count={data.adjudications.length} empty="No other case is paired with this one.">
        <ul className="space-y-3">
          {data.adjudications.map((pair) => (
            <li key={pair.record_id} className="rounded-xl border border-border bg-card p-4" data-adjudication={pair.record_id}>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <IdCode>{pair.record_id}</IdCode><StatusBadge status={pair.status} origin={pair.origin} />
              </div>
              <p className="mt-1 text-sm">
                Paired with <CaseLink caseId={pair.other_case.case_id} />
                {pair.other_case.held
                  ? ` — ${pair.other_case.date || 'undated'} (${PRECISION_LABEL[pair.other_case.temporal_precision] || 'undated'}), ${pair.other_case.place?.municipality || pair.other_case.place?.location_name || 'place not recorded'}${pair.other_case.category ? `, ${pair.other_case.category}` : ''}`
                  : ' — not held by this Hub'}
              </p>
              <CandidateSignals signals={pair.attributes.signals} />
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Findings" count={data.findings.length} empty="No findings name this case.">
        <ul className="space-y-3">
          {data.findings.map((finding) => (
            <li key={finding.record_id} className="rounded-xl border border-border bg-card p-4" data-finding={finding.record_id}>
              <div className="flex flex-wrap items-center gap-2 text-xs"><IdCode>{finding.record_id}</IdCode><StatusBadge status={finding.status} /></div>
              <p className="mt-1 text-sm">{finding.attributes.statement}</p>
              <SourceRefs refs={finding.attributes.source_refs} />
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Hypotheses" count={data.hypotheses.length} empty="No hypotheses name this case.">
        <ul className="space-y-3">
          {data.hypotheses.map((hypothesis) => (
            <li key={hypothesis.record_id} className="rounded-xl border border-border bg-card p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs"><IdCode>{hypothesis.record_id}</IdCode><StatusBadge status={hypothesis.status} /></div>
              <p className="mt-1 text-sm">{hypothesis.attributes.statement}</p>
              <FalsificationChecklist checks={hypothesis.attributes.falsification} />
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Contradictions" count={data.contradictions.length} empty="No contradictions name this case.">
        <ul className="space-y-3">
          {data.contradictions.map((contradiction) => (
            <li key={contradiction.record_id} className="rounded-xl border border-border bg-card p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs"><IdCode>{contradiction.record_id}</IdCode><StatusBadge status={contradiction.status} /></div>
              <p className="mt-1 text-sm">“{contradiction.attributes.claim_a?.text}” / “{contradiction.attributes.claim_b?.text}”</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Open questions" count={data.queue.length} empty="No research questions are queued for this case.">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {data.queue.map((item) => <li key={item.record_id}>{item.attributes.question} <StatusBadge status={item.status} /></li>)}
        </ul>
      </Section>

      <Section title="Media episodes" count={data.episodes.length} empty="No recorded episode discusses this case.">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {data.episodes.map((episode) => <li key={episode.record_id}>{episode.attributes.series}: {episode.attributes.title}</li>)}
        </ul>
      </Section>
    </div>
  );
}
