import React from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink } from 'lucide-react';
import { federation } from '@/api/federationClient';
import PageHeader from '@/components/shared/PageHeader';
import IdCode from '@/components/shared/IdCode';
import { cn } from '@/lib/utils';
import { SYNTHETIC_TONE } from '@/lib/evidenceState';

// TWIN-180…200 (directive §13). OVNIS owns the case corpus; this page orders
// what the Hub store holds. Dates keep the precision the source recorded and
// places stay as the source gives them; nothing here is inferred.
export const PRECISION_LABEL = {
  YEAR_ONLY: 'year only',
  MONTH_YEAR: 'month',
  DATE_ONLY: 'date',
  EXACT_TIMESTAMP: 'date and time',
  UNKNOWN: 'undated',
};
const chip = 'inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold';
const toggle = (active) => cn(
  'min-h-[44px] rounded-md border px-3 text-sm font-medium',
  active ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card text-foreground hover:bg-muted',
);

function readParams(searchParams) {
  return {
    sort: searchParams.get('sort') === 'newest' ? 'newest' : 'oldest',
    categories: searchParams.getAll('category'),
    findingsOnly: searchParams.get('findings') === '1',
    includeSynthetic: searchParams.get('synthetic') === '1',
    cursor: searchParams.get('cursor') || undefined,
  };
}

function TimelineEvent({ event }) {
  const place = event.place.municipality || event.place.location_name || 'Place not recorded';
  return (
    <li className="relative border-l-2 border-border pb-6 pl-5" data-timeline-event={event.observation_id}>
      <span aria-hidden="true" className="absolute -left-[7px] top-1.5 h-3 w-3 rounded-full border-2 border-primary bg-background" />
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <time className="font-mono font-semibold text-foreground" dateTime={event.date || undefined}>
          {event.date ? `${event.date}${event.time ? ` ${event.time}` : ''}` : 'Undated'}
        </time>
        <span className={cn(chip, 'border-border text-muted-foreground')} data-temporal-precision={event.temporal_precision}>
          {PRECISION_LABEL[event.temporal_precision] || 'undated'}
        </span>
        <span className={cn(chip, 'border-primary/40 text-foreground')} data-event-category={event.category}>{event.category}</span>
        {event.evidence_tier ? <span className={cn(chip, 'border-border text-muted-foreground')}>Tier {event.evidence_tier}</span> : null}
        {event.synthetic ? <span className={cn(chip, SYNTHETIC_TONE)}>Synthetic / test row</span> : null}
      </div>
      <h3 className="mt-1.5 text-base font-semibold text-foreground">{event.title}</h3>
      <p className="text-xs text-muted-foreground">
        {place}{event.case_id ? <> · <IdCode>{event.case_id}</IdCode></> : null}
      </p>
      <p className="mt-2 text-sm text-foreground">
        {event.narrative || <span className="text-muted-foreground">No narrative was exported for this case.</span>}
      </p>
      {event.findings?.length ? (
        <p className="mt-2 text-xs text-foreground">{event.findings.length} OVNIS finding(s) name this case.</p>
      ) : null}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {event.source ? (
          <>
            {/^https?:\/\//i.test(event.source.url || '') ? (
              <a className="inline-flex items-center gap-1 text-primary underline" href={event.source.url} target="_blank" rel="noreferrer noopener">
                Source <ExternalLink className="h-3 w-3" aria-hidden="true" />
              </a>
            ) : event.source.url ? (
              <span className="break-all text-muted-foreground" data-source-locator>Source locator: {event.source.url}</span>
            ) : null}
            <Link className="text-primary underline" to={event.source.evidence_href}>Source provenance</Link>
          </>
        ) : <span className="text-muted-foreground">Source not held by the Hub</span>}
        <Link className="text-primary underline" to={event.evidence_href}>Provenance</Link>
        {event.entity_href ? <Link className="text-primary underline" to={event.entity_href}>Case composition</Link> : null}
      </div>
    </li>
  );
}

function EventList({ events }) {
  const groups = [];
  events.forEach((event) => {
    const era = event.era || 'Undated';
    if (!groups.length || groups[groups.length - 1].era !== era) groups.push({ era, events: [] });
    groups[groups.length - 1].events.push(event);
  });
  return (
    <div className="space-y-4">
      {groups.map((group, index) => (
        <section key={`${group.era}-${index}`} aria-label={group.era}>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{group.era}</h2>
          <ol className="ml-2">{group.events.map((event) => <TimelineEvent key={event.observation_id} event={event} />)}</ol>
        </section>
      ))}
    </div>
  );
}

export default function Timeline() {
  const [searchParams, setSearchParams] = useSearchParams();
  const params = readParams(searchParams);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['timeline', params],
    queryFn: () => federation.timeline.query(params),
  });

  const update = (changes) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(changes).forEach(([key, value]) => {
      next.delete(key);
      if (Array.isArray(value)) value.forEach((v) => next.append(key, v));
      else if (value !== undefined && value !== null && value !== '') next.set(key, value);
    });
    if (!('cursor' in changes)) next.delete('cursor');
    setSearchParams(next);
  };
  const toggleCategory = (category) => update({
    category: params.categories.includes(category)
      ? params.categories.filter((c) => c !== category)
      : [...params.categories, category],
  });

  return (
    <div className="space-y-6 p-4 md:p-8">
      <PageHeader
        title="Event Timeline"
        description="OVNIS case events ordered by recorded date. Dates keep the precision the source recorded, and places are as the source gives them."
      />

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Sort order">
        <button type="button" className={toggle(params.sort === 'oldest')} aria-pressed={params.sort === 'oldest'} onClick={() => update({ sort: 'oldest' })}>
          Oldest first
        </button>
        <button type="button" className={toggle(params.sort === 'newest')} aria-pressed={params.sort === 'newest'} onClick={() => update({ sort: 'newest' })}>
          Newest first
        </button>
        <button type="button" className={toggle(params.findingsOnly)} aria-pressed={params.findingsOnly} onClick={() => update({ findings: params.findingsOnly ? '' : '1' })}>
          Findings only
        </button>
        <label className="ml-2 inline-flex min-h-[44px] items-center gap-2 text-sm text-foreground">
          <input type="checkbox" checked={params.includeSynthetic} onChange={() => update({ synthetic: params.includeSynthetic ? '' : '1' })} />
          Include synthetic / test rows
        </label>
      </div>

      {data?.categories?.length ? (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Categories">
          {data.categories.map(({ category, count }) => (
            <button
              key={category}
              type="button"
              className={toggle(params.categories.includes(category))}
              aria-pressed={params.categories.includes(category)}
              onClick={() => toggleCategory(category)}
            >
              {category} <span className="ml-1 opacity-80">({count})</span>
            </button>
          ))}
        </div>
      ) : null}

      {isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading the timeline…</p> : null}
      {isError ? (
        <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          The timeline is unavailable: {String(error?.message || error)}
        </div>
      ) : null}

      {data ? (
        <>
          <p className="text-sm text-muted-foreground" data-timeline-summary>
            {data.loaded_events} events in this Hub&apos;s store · {data.matched} match
            {data.undated ? ` · ${data.undated} undated, listed last` : ''}
            {data.excluded_synthetic ? ` · ${data.excluded_synthetic} synthetic excluded` : ''}
            {' · '}{data.findings_total} OVNIS findings recorded
          </p>
          {data.producer_status === 'NO_DATA' ? (
            <div role="status" className="rounded-xl border border-border bg-card p-4 text-sm">
              The Hub holds no OVNIS case events. Run the federation ingest to load the producer&apos;s export.
            </div>
          ) : null}
          {params.findingsOnly && data.findings_status === 'NO_FINDINGS_RECORDED' ? (
            <div role="status" className="rounded-xl border border-border bg-card p-4 text-sm" data-findings-status={data.findings_status}>
              No findings are recorded yet. OVNIS publishes findings through its research ledger; none exist, so
              this view shows nothing rather than treating cases as findings.
            </div>
          ) : null}
          {data.events.length ? <EventList events={data.events} /> : null}
          {!data.events.length && data.producer_status === 'AVAILABLE' && !params.findingsOnly ? (
            <p role="status" className="text-sm text-muted-foreground">No events match these filters.</p>
          ) : null}
          {data.next_cursor ? (
            <button type="button" className={toggle(false)} onClick={() => update({ cursor: data.next_cursor })}>
              Next events
            </button>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
