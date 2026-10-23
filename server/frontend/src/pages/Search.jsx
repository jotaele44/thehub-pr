import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search as SearchIcon } from 'lucide-react';
import { federation } from '@/api/federationClient';
import PageHeader from '@/components/shared/PageHeader';
import IdCode from '@/components/shared/IdCode';
import { cn } from '@/lib/utils';
import { SEARCH_TYPES } from '@/lib/deepLinks';
import { SYNTHETIC_TONE } from '@/lib/evidenceState';

const TYPE_LABELS = {
  ALL: 'All', READING: 'Readings', FINDING: 'Findings', TIMELINE: 'Timeline', SOURCE: 'Sources', ENTITY: 'Entities',
};
const chip = 'inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold';

function SearchResult({ result }) {
  return (
    <li className="rounded-xl border border-border bg-card p-4" data-search-result={result.evidence_id} data-result-kind={result.kind}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn(chip, 'border-border text-muted-foreground')}>{TYPE_LABELS[result.kind] || result.kind}</span>
        {result.synthetic ? (
          <span className={cn(chip, SYNTHETIC_TONE)}>Synthetic / test row</span>
        ) : null}
        {result.finding_status ? (
          <span className={cn(chip, 'border-border text-foreground')} data-finding-status={result.finding_status}>
            Finding status: {result.finding_status}
          </span>
        ) : null}
        <span className="text-xs text-muted-foreground">{result.type}</span>
      </div>
      <h2 className="mt-2 text-base font-semibold text-foreground">
        <Link className="hover:underline" to={result.evidence_href}>{result.title}</Link>
      </h2>
      <p className="mt-1 text-xs text-muted-foreground">
        {result.producers.join(', ') || 'unattributed'} · <IdCode>{result.record_id}</IdCode>
        {result.declared_epistemic_class ? ` · declared ${result.declared_epistemic_class}` : ' · class not declared by producer'}
      </p>
      <div className="mt-2 flex flex-wrap gap-3 text-xs">
        <Link className="text-primary underline" to={result.evidence_href}>Provenance</Link>
        {result.entity_href ? <Link className="text-primary underline" to={result.entity_href}>Entity composition</Link> : null}
      </div>
    </li>
  );
}

function ProducerStatus({ producers }) {
  if (!producers?.length) return null;
  return (
    <section aria-label="Producer coverage" className="rounded-xl border border-border bg-card p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Producer coverage</h2>
      <ul className="mt-3 space-y-1.5 text-sm">
        {producers.map((p) => (
          <li key={p.producer} className="flex items-center justify-between gap-2" data-producer-status={p.status}>
            <span className="truncate">{p.producer}</span>
            <span className="text-xs text-muted-foreground">
              {p.status === 'AVAILABLE' ? `${p.indexed_records} records` : 'No data in the Hub'}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// Federated search (TWIN-012, TWIN-082..096). Query, filter, synthetic toggle
// and page all live in the URL, so every result list is a deep link.
export default function Search() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') || '';
  const rawType = (params.get('type') || 'ALL').toUpperCase();
  const type = SEARCH_TYPES.includes(rawType) ? rawType : 'ALL';
  const includeSynthetic = params.get('synthetic') === '1';
  const cursor = params.get('cursor') || undefined;
  const [draft, setDraft] = useState(q);
  useEffect(() => setDraft(q), [q]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['search', q, type, includeSynthetic, cursor],
    queryFn: () => federation.search.query({ q, type, includeSynthetic, cursor }),
    retry: false,
  });

  const update = (changes) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === undefined || value === '' || value === false) next.delete(key);
      else next.set(key, value === true ? '1' : String(value));
    }
    if (!('cursor' in changes)) next.delete('cursor');
    setParams(next);
  };

  return (
    <div>
      <PageHeader
        icon={SearchIcon}
        title="Search the Federation"
        description="One search across every producer's canonical records. Every word must match; accents and case are ignored. Press Ctrl+K anywhere to search or jump."
      />
      <form
        role="search"
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => { event.preventDefault(); update({ q: draft.trim() }); }}
      >
        <label htmlFor="federation-search" className="sr-only">Search query</label>
        <input
          id="federation-search"
          type="search"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="e.g. laguna cartagena"
          className="h-11 flex-1 rounded-md border border-border bg-background px-3 text-sm"
        />
        <button type="submit" className="h-11 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground">Search</button>
      </form>

      <div className="mt-3 flex flex-wrap items-center gap-2" role="group" aria-label="Result type">
        {SEARCH_TYPES.map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={type === value}
            onClick={() => update({ type: value === 'ALL' ? null : value })}
            className={cn('min-h-9 rounded-full border px-3 text-xs', type === value ? 'border-primary bg-primary/10 font-semibold' : 'border-border')}
          >
            {TYPE_LABELS[value]}
          </button>
        ))}
        <label className="ml-auto flex min-h-9 items-center gap-2 text-xs text-muted-foreground">
          <input type="checkbox" checked={includeSynthetic} onChange={(event) => update({ synthetic: event.target.checked })} />
          Include synthetic / test rows
        </label>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
        <div>
          {isLoading ? (
            <p role="status" className="text-sm text-muted-foreground">Searching…</p>
          ) : error ? (
            <div role="alert" className="rounded-xl border border-border bg-card p-4 text-sm">
              Search is unavailable: {error.message}. No results are shown in its place.
            </div>
          ) : data ? (
            <>
              <p role="status" className="text-xs text-muted-foreground" data-search-summary>
                {data.indexed_records} indexed records
                {data.query_status === 'EMPTY_QUERY' ? ' · type a query to search' : ` · ${data.total} result${data.total === 1 ? '' : 's'}`}
                {data.excluded_synthetic ? ` · ${data.excluded_synthetic} synthetic excluded` : ''}
              </p>
              {data.type_status === 'NO_FINDINGS_RECORDED' ? (
                <p role="note" className="mt-3 rounded-xl border border-border bg-card p-4 text-sm" data-type-status={data.type_status}>
                  No findings are recorded in the OVNIS research ledger yet, so this filter has nothing to search. It is not an empty result.
                </p>
              ) : null}
              {data.query_status === 'OK' && data.total === 0 && data.type_status === 'OK' ? (
                <p className="mt-3 rounded-xl border border-border bg-card p-4 text-sm">
                  Nothing in the Federation matches every word of “{data.query}”.
                </p>
              ) : null}
              <ul className="mt-3 space-y-3">
                {data.results.map((result) => <SearchResult key={result.evidence_id} result={result} />)}
              </ul>
              <nav aria-label="Result pages" className="mt-4 flex gap-3 text-sm">
                {cursor ? <button type="button" className="text-primary underline" onClick={() => update({ cursor: null })}>First page</button> : null}
                {data.next_cursor ? (
                  <button type="button" className="text-primary underline" onClick={() => update({ cursor: data.next_cursor })}>Next results</button>
                ) : null}
              </nav>
            </>
          ) : null}
        </div>
        <ProducerStatus producers={data?.producers} />
      </div>
    </div>
  );
}
