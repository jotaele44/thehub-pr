import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FlaskConical } from 'lucide-react';
import { federation } from '@/api/federationClient';
import PageHeader from '@/components/shared/PageHeader';
import IdCode from '@/components/shared/IdCode';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import ResearchAssistant from '@/pages/ResearchAssistant';
import {
  CandidateSignals, CaseLink, CaseLinks, EmptyLedger, FalsificationChecklist, ResearchRecordList, SourceRefs,
  StatusBadge, chip,
} from '@/components/research/ResearchRecords';
import { cn } from '@/lib/utils';

// Research Hub (TWIN-004, TWIN-164..175; FDX-013..017). OVNIS owns the
// research record and curators write it; this page renders what the Hub store
// holds. Empty ledgers say so, computed duplicate pairs stay candidates, and
// the LLM research assistant keeps its own tab, unchanged.
export const RESEARCH_TABS = [
  { value: 'topics', label: 'Topics' },
  { value: 'hypotheses', label: 'Hypotheses' },
  { value: 'contradictions', label: 'Contradictions' },
  { value: 'candidates', label: 'Duplicate candidates' },
  { value: 'queue', label: 'Queue' },
  { value: 'assistant', label: 'Assistant' },
];
const NONE_YET = 'nothing is generated into it; records appear here only after a curator adds them to the OVNIS research ledger.';

function TopicFindings({ findingIds }) {
  const { data, isLoading } = useQuery({
    queryKey: ['research-records', 'findings', 'all'],
    queryFn: () => federation.research.records('findings', { limit: 200 }),
  });
  if (isLoading) return <p role="status" className="text-xs text-muted-foreground">Loading findings…</p>;
  const findings = (data?.records || []).filter((f) => findingIds.includes(f.record_id));
  if (!findings.length) return <p className="text-xs text-muted-foreground">No findings are recorded for this topic.</p>;
  return (
    <ul className="mt-3 space-y-3 border-l-2 border-border pl-4" data-topic-findings>
      {findings.map((finding) => (
        <li key={finding.record_id} data-finding={finding.record_id}>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <IdCode>{finding.record_id}</IdCode>
            <StatusBadge status={finding.status} />
            <span className={cn(chip, 'border-border text-muted-foreground')}>{finding.attributes.epistemic_class}</span>
          </div>
          <p className="mt-1 text-sm text-foreground">{finding.attributes.statement}</p>
          {finding.attributes.interpretation_basis ? (
            <p className="text-xs text-muted-foreground">Interpretation basis: {finding.attributes.interpretation_basis}</p>
          ) : null}
          <div className="mt-1"><SourceRefs refs={finding.attributes.source_refs} /></div>
        </li>
      ))}
    </ul>
  );
}

function TopicCard({ topic }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-xl border border-border bg-card p-4" data-topic-card={topic.record_id}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <IdCode>{topic.record_id}</IdCode>
        <StatusBadge status={topic.status} />
        {(topic.attributes.tags || []).map((tag) => (
          <span key={tag} className={cn(chip, 'border-border text-muted-foreground')}>{tag}</span>
        ))}
      </div>
      <h3 className="mt-1 text-base font-semibold text-foreground">{topic.attributes.title}</h3>
      <p className="text-sm text-muted-foreground">{topic.attributes.scope}</p>
      <p className="mt-2 text-xs text-foreground" data-topic-counts>
        {topic.finding_count} finding{topic.finding_count === 1 ? '' : 's'} ·{' '}
        <span title={topic.source_count_basis}>{topic.source_count} distinct source{topic.source_count === 1 ? '' : 's'}</span>
      </p>
      <button
        type="button"
        className="mt-2 min-h-[44px] rounded-md border border-border px-3 text-sm"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? 'Hide findings' : 'View findings'}
      </button>
      {open ? <TopicFindings findingIds={topic.finding_ids} /> : null}
    </li>
  );
}

function TopicsTab({ overview }) {
  if (!overview.topics.length) {
    return <EmptyLedger>No topics are recorded in the OVNIS research ledger yet; {NONE_YET}</EmptyLedger>;
  }
  return <ul className="space-y-3">{overview.topics.map((topic) => <TopicCard key={topic.record_id} topic={topic} />)}</ul>;
}

function Overview({ overview }) {
  const kinds = overview.kinds;
  const items = [
    ['Topics', kinds.topics.total], ['Findings', kinds.findings.total], ['Hypotheses', kinds.hypotheses.total],
    ['Contradictions', kinds.contradictions.total], ['Duplicate candidates', kinds.adjudications.computed_candidates],
    ['Reviewed adjudications', kinds.adjudications.curated_decisions], ['Queue items', kinds.queue.total],
    ['Case reports', kinds.reports.total],
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-research-overview>
      {items.map(([label, value]) => (
        <div key={label} className="rounded-xl border border-border bg-card p-3">
          <dt className="text-xs text-muted-foreground">{label}</dt>
          <dd className="text-xl font-semibold text-foreground">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function ResearchHub() {
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab');
  const tab = RESEARCH_TABS.some((t) => t.value === requested) ? requested : 'topics';
  const { data: overview, isLoading, isError, error } = useQuery({
    queryKey: ['research-overview'],
    queryFn: () => federation.research.overview(),
  });

  const selectTab = (value) => {
    const next = new URLSearchParams(params);
    next.set('tab', value);
    setParams(next);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FlaskConical}
        title="Research Hub"
        description="OVNIS research records: topics, findings, hypotheses under falsification test, contradictions and duplicate-case candidates. A finding is a sourced claim, not an established fact, and a candidate pair is never treated as one event until a curator decides it."
      />
      {isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading research…</p> : null}
      {isError ? (
        <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          The research overview is unavailable: {String(error?.message || error)}
        </div>
      ) : null}
      {overview?.producer_status === 'NO_DATA' ? (
        <EmptyLedger>The Hub holds no OVNIS research records. Run the federation ingest to load the producer&apos;s export.</EmptyLedger>
      ) : null}
      {overview ? <Overview overview={overview} /> : null}

      <Tabs value={tab} onValueChange={selectTab} className="w-full">
        <TabsList className="mb-4 h-auto flex-wrap">
          {RESEARCH_TABS.map((t) => <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>)}
        </TabsList>

        <TabsContent value="topics">{overview ? <TopicsTab overview={overview} /> : null}</TabsContent>

        <TabsContent value="hypotheses">
          <ResearchRecordList kind="hypotheses" emptyText={`No hypotheses are recorded in the OVNIS research ledger yet; ${NONE_YET}`}>
            {(hypothesis) => (
              <>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <IdCode>{hypothesis.record_id}</IdCode><StatusBadge status={hypothesis.status} />
                </div>
                <p className="mt-1 text-sm text-foreground">{hypothesis.attributes.statement}</p>
                <p className="mt-1 text-xs">Cases: <CaseLinks caseIds={hypothesis.case_ids} /></p>
                <FalsificationChecklist checks={hypothesis.attributes.falsification} />
              </>
            )}
          </ResearchRecordList>
        </TabsContent>

        <TabsContent value="contradictions">
          <ResearchRecordList kind="contradictions" emptyText={`No contradictions are recorded in the OVNIS research ledger yet; ${NONE_YET}`}>
            {(contradiction) => (
              <>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <IdCode>{contradiction.record_id}</IdCode><StatusBadge status={contradiction.status} />
                </div>
                <div className="mt-2 grid gap-3 sm:grid-cols-2">
                  {['claim_a', 'claim_b'].map((side) => (
                    <blockquote key={side} className="rounded-md border border-border p-3 text-sm">
                      <p>{contradiction.attributes[side]?.text}</p>
                      <SourceRefs refs={contradiction.attributes[side]?.source_ref ? [contradiction.attributes[side].source_ref] : []} />
                    </blockquote>
                  ))}
                </div>
                {contradiction.attributes.adjudication ? (
                  <p className="mt-2 text-xs">Adjudication: {contradiction.attributes.adjudication} — {contradiction.attributes.rationale}</p>
                ) : null}
              </>
            )}
          </ResearchRecordList>
        </TabsContent>

        <TabsContent value="candidates">
          <p className="mb-3 text-xs text-muted-foreground">
            Pairs of cases whose recorded dates agree and that share a place. These signals rank a review queue; they never decide that two cases are one event.
          </p>
          <ResearchRecordList kind="adjudications" emptyText="No duplicate-case candidates or adjudications are held by this Hub.">
            {(pair) => (
              <>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <IdCode>{pair.record_id}</IdCode><StatusBadge status={pair.status} origin={pair.origin} />
                </div>
                <p className="mt-1 text-sm">
                  <CaseLink caseId={pair.attributes.case_a} /> and <CaseLink caseId={pair.attributes.case_b} />
                </p>
                <CandidateSignals signals={pair.attributes.signals} />
                {pair.origin === 'CURATED' ? (
                  <p className="mt-1 text-xs">Reviewed by {pair.attributes.reviewed_by}: {pair.attributes.rationale}</p>
                ) : null}
              </>
            )}
          </ResearchRecordList>
        </TabsContent>

        <TabsContent value="queue">
          <ResearchRecordList kind="queue" emptyText={`No research questions are queued in the OVNIS research ledger yet; ${NONE_YET}`}>
            {(item) => (
              <>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <IdCode>{item.record_id}</IdCode><StatusBadge status={item.status} />
                  <span className={cn(chip, 'border-border text-muted-foreground')}>{item.attributes.kind}</span>
                </div>
                <p className="mt-1 text-sm text-foreground">{item.attributes.question}</p>
                <p className="mt-1 text-xs">Cases: <CaseLinks caseIds={item.case_ids} /></p>
              </>
            )}
          </ResearchRecordList>
        </TabsContent>

        <TabsContent value="assistant">
          <ResearchAssistant />
        </TabsContent>
      </Tabs>
    </div>
  );
}
