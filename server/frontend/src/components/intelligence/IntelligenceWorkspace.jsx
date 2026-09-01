import React, { useEffect, useMemo, useState } from 'react';
import {
  FederationConfidenceBadge,
  FederationFreshnessBadge,
  FederationProvenanceBadge,
  FederationSourceBadge,
} from '@pr-federation/react';
import { Search, Database, MapPin, AlertTriangle, RefreshCw } from 'lucide-react';
import { useEntityData } from '@/hooks/useEntityData';
import MultiMarkerMap from '@/components/shared/MultiMarkerMap';
import ForensicStateBadge from './ForensicStateBadge';
import { filterIntelligenceRows } from '@/lib/intelligenceWorkspaceState';

const TIME_OPTIONS = [
  ['all', 'All'],
  ['6h', '6H'],
  ['24h', '24H'],
  ['7d', '7D'],
  ['30d', '30D'],
];

function nonEmpty(value, fallback = '—') {
  return value === undefined || value === null || String(value).trim() === '' ? fallback : String(value);
}

function normalizeSemantic(value, fallback) {
  return String(value ?? fallback).trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function Metric({ label, value }) {
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-0.5 font-mono text-sm font-semibold text-foreground">{value}</div>
    </div>
  );
}

function RecordCard({ adapter, row, selected, onSelect }) {
  const id = adapter.getId(row);
  const confidence = adapter.getConfidence(row);
  const significance = adapter.getSignificance(row);
  return (
    <button
      type="button"
      onClick={() => onSelect(id)}
      aria-pressed={selected}
      className={`w-full min-h-[52px] rounded-lg border px-3 py-2.5 text-left transition-colors fd-focus ${selected ? 'border-primary bg-primary/10' : 'border-border bg-card hover:bg-muted/60'}`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold leading-tight text-foreground">{adapter.getTitle(row)}</span>
        <span className="shrink-0 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{adapter.getCategory(row)}</span>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
        <span>{adapter.getLocation(row)}</span>
        {confidence ? <span>confidence {confidence}</span> : null}
        {significance !== undefined && significance !== null && significance !== '' ? <span>significance {String(significance)}</span> : null}
      </div>
    </button>
  );
}

function Inspector({ adapter, row, relatedRows, queryUpdatedAt }) {
  if (!row) {
    return (
      <aside className="rounded-xl border border-border bg-card p-5" aria-label="Evidence inspector">
        <h3 className="text-sm font-semibold">Evidence inspector</h3>
        <p className="mt-2 text-sm text-muted-foreground">Select a visible record to inspect evidence, provenance, contradictions, and adjudication state.</p>
      </aside>
    );
  }

  const axes = adapter.getForensicAxes(row);
  const sources = adapter.getSources(row);
  const contradictions = adapter.getContradictions(row);
  const confidence = normalizeSemantic(adapter.getConfidence(row), 'unknown');
  const provenance = normalizeSemantic(axes.provenance, 'missing');
  const freshness = normalizeSemantic(axes.freshness, 'unknown');

  return (
    <aside className="rounded-xl border border-border bg-card" aria-label="Evidence inspector">
      <div className="border-b border-border p-4">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Inspector</div>
        <h3 className="mt-1 text-base font-semibold text-foreground">{adapter.getTitle(row)}</h3>
        <div className="mt-1 text-xs text-muted-foreground">{adapter.getLocation(row)}</div>
      </div>

      <div className="space-y-4 p-4">
        <section aria-label="Independent analytical states">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Independent states</h4>
          <div className="mt-2 flex flex-wrap gap-2">
            <ForensicStateBadge axis="Identity" value={axes.identity} />
            <ForensicStateBadge axis="Certification" value={axes.certification} />
            <ForensicStateBadge axis="Epistemic" value={axes.epistemic} />
            <FederationConfidenceBadge confidence={confidence} />
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">Visual prominence and map proximity are never promoted to identity or certification. Missing explicit state fails closed.</p>
        </section>

        {adapter.getSummary(row) ? (
          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Summary</h4>
            <p className="mt-1.5 text-sm leading-relaxed text-foreground">{adapter.getSummary(row)}</p>
          </section>
        ) : null}

        <section>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Record fields</h4>
          <dl className="mt-2 grid grid-cols-1 gap-2 text-xs sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            <div><dt className="text-muted-foreground">Stable/display ID</dt><dd className="mt-0.5 break-all font-mono text-foreground">{nonEmpty(adapter.getId(row))}</dd></div>
            {adapter.inspectorFields.map(([label, getter]) => (
              <div key={label}><dt className="text-muted-foreground">{label}</dt><dd className="mt-0.5 break-words text-foreground">{nonEmpty(getter(row))}</dd></div>
            ))}
          </dl>
        </section>

        <section>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Provenance & freshness</h4>
          <div className="mt-2 flex flex-wrap gap-2">
            <FederationProvenanceBadge state={provenance} />
            <FederationFreshnessBadge freshness={freshness} />
            {sources.map((source) => <FederationSourceBadge key={source} source={source} />)}
          </div>
          {sources.length === 0 ? <p className="mt-2 text-xs text-muted-foreground">No explicit source manifestation is attached to this loaded row.</p> : null}
          <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">Hub query updated {queryUpdatedAt ? new Date(queryUpdatedAt).toLocaleString() : 'at an unknown time'}. Query recency is not source freshness.</p>
        </section>

        <section>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Contradictions</h4>
          </div>
          {contradictions.length ? (
            <ul className="mt-2 space-y-1.5 text-xs text-foreground">
              {contradictions.map((item, index) => <li key={`${index}-${item}`} className="rounded border border-border bg-muted/40 px-2 py-1.5">{item}</li>)}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground">No explicit contradiction field is present in this loaded row. This does not prove that no contradiction exists.</p>
          )}
        </section>

        <section>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{adapter.relatedNoun}</h4>
          <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{adapter.relatedDisclaimer}</p>
          {relatedRows.length ? (
            <ul className="mt-2 space-y-1.5">
              {relatedRows.slice(0, 25).map((related, index) => (
                <li key={related.id || related.review_id || related.edge_id || related.risk_id || index} className="rounded border border-border px-2.5 py-2">
                  <div className="text-xs font-medium text-foreground">{adapter.getRelatedTitle(related)}</div>
                  <div className="mt-0.5 text-[11px] text-muted-foreground">{adapter.getRelatedSubtitle(related) || 'No additional relation metadata'}</div>
                </li>
              ))}
            </ul>
          ) : <p className="mt-2 text-xs text-muted-foreground">No related records in the loaded Hub query.</p>}
        </section>
      </div>
    </aside>
  );
}

export default function IntelligenceWorkspace({ adapter }) {
  const primary = useEntityData(adapter.primaryEntity, '-created_date', { refetchInterval: 60000 });
  const related = useEntityData(adapter.relatedEntity);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [timeWindow, setTimeWindow] = useState('all');
  const [selectedId, setSelectedId] = useState(null);

  const categories = useMemo(() => [...new Set(primary.rows.map(adapter.getCategory).filter(Boolean))].sort(), [primary.rows, adapter]);
  const filtered = useMemo(
    () => filterIntelligenceRows(primary.rows, adapter, { query, category, timeWindow }),
    [primary.rows, adapter, query, category, timeWindow],
  );

  useEffect(() => {
    const ids = new Set(filtered.visible.map(adapter.getId));
    if (!selectedId || !ids.has(selectedId)) setSelectedId(filtered.visible[0] ? adapter.getId(filtered.visible[0]) : null);
  }, [filtered.visible, adapter, selectedId]);

  const selected = filtered.visible.find((row) => adapter.getId(row) === selectedId) || null;
  const relatedRows = selected ? adapter.getRelated(related.rows, selected) : [];
  const mapPoints = filtered.visible.map((row) => ({
    id: adapter.getId(row),
    lat: adapter.getLatitude(row),
    lon: adapter.getLongitude(row),
    title: adapter.getTitle(row),
    subtitle: [adapter.getCategory(row), adapter.getLocation(row)].filter(Boolean).join(' · '),
  })).filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lon));

  const loading = primary.isLoading || related.isLoading;
  const error = primary.isError || related.isError;

  return (
    <section className="space-y-3" data-intelligence-workspace={adapter.key}>
      <div className="rounded-xl border border-border bg-card p-3" data-intelligence-toolbar>
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[220px] flex-1 text-xs font-medium text-muted-foreground" htmlFor={`${adapter.key}-intelligence-search`}>
            Search
            <span className="relative mt-1 block">
              <Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <input
                id={`${adapter.key}-intelligence-search`}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="min-h-[44px] w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder={`Search ${adapter.primaryNoun}…`}
              />
            </span>
          </label>

          <label className="min-w-[180px] text-xs font-medium text-muted-foreground" htmlFor={`${adapter.key}-intelligence-category`}>
            Category
            <select
              id={`${adapter.key}-intelligence-category`}
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              className="mt-1 min-h-[44px] w-full rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="all">All categories</option>
              {categories.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>

          <fieldset className="min-w-[280px]">
            <legend className="text-xs font-medium text-muted-foreground">Time range</legend>
            <div className="mt-1 flex flex-wrap gap-1" role="group" aria-label="Time range">
              {TIME_OPTIONS.map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={timeWindow === value}
                  onClick={() => setTimeWindow(value)}
                  className={`min-h-[44px] min-w-[48px] rounded-md border px-3 text-xs font-semibold fd-focus ${timeWindow === value ? 'border-primary bg-primary/10 text-foreground' : 'border-border bg-background text-muted-foreground hover:text-foreground'}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </fieldset>
        </div>
        <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{adapter.temporalNote}</p>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="Loaded rows" value={filtered.metrics.sourceCount} />
        <Metric label="Visible" value={filtered.metrics.visibleCount} />
        <Metric label="Excluded" value={filtered.metrics.excludedCount} />
        <Metric label="Undated" value={filtered.metrics.undatedCount} />
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1"><Database className="h-3.5 w-3.5" aria-hidden="true" />Loaded-row denominator: {filtered.metrics.sourceCount} = {filtered.metrics.visibleCount} visible + {filtered.metrics.excludedCount} excluded.</span>
        <span>Bounded to the current Hub entity query; not a universal source denominator.</span>
        {filtered.metrics.futureTimestampCount ? <span>{filtered.metrics.futureTimestampCount} future-dated row(s) detected.</span> : null}
      </div>

      {error ? (
        <div role="alert" className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-foreground">Hub query failed for at least one workspace collection. Results are incomplete and cannot be certified.</div>
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-sm text-muted-foreground" role="status">Loading workspace records…</div>
      ) : (
        <div className="grid gap-3 xl:grid-cols-[minmax(260px,0.8fr)_minmax(420px,1.8fr)_minmax(300px,1fr)]">
          <section className="min-w-0 rounded-xl border border-border bg-card" aria-label={`${adapter.label} event feed`}>
            <div className="flex items-center justify-between border-b border-border px-3 py-2.5">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Feed</div>
                <div className="text-sm font-semibold text-foreground">{adapter.primaryNoun}</div>
              </div>
              <span className="text-xs text-muted-foreground">{filtered.metrics.visibleCount}</span>
            </div>
            <div className="max-h-[640px] space-y-2 overflow-y-auto p-2">
              {filtered.visible.length ? filtered.visible.map((row) => (
                <RecordCard key={adapter.getId(row)} adapter={adapter} row={row} selected={adapter.getId(row) === selectedId} onSelect={setSelectedId} />
              )) : (
                <div className="p-5 text-center text-sm text-muted-foreground">No records match the current filters.</div>
              )}
            </div>
          </section>

          <section className="min-w-0 rounded-xl border border-border bg-card p-2" aria-label="Map workspace">
            <div className="flex flex-wrap items-center justify-between gap-2 px-1 pb-2 text-[11px] text-muted-foreground">
              <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" aria-hidden="true" />{mapPoints.length} of {filtered.metrics.visibleCount} visible rows have plottable coordinates.</span>
              <span className="inline-flex items-center gap-1"><RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />Hub query refreshes while this workspace is open.</span>
            </div>
            {mapPoints.length ? (
              <MultiMarkerMap points={mapPoints} height={600} selectedId={selectedId} onPointSelect={(point) => setSelectedId(point.id)} />
            ) : (
              <div className="flex h-[600px] items-center justify-center rounded-lg border border-border bg-muted/20 p-6 text-center text-sm text-muted-foreground">No visible rows have valid coordinates. The feed and inspector remain authoritative for the loaded records.</div>
            )}
          </section>

          <Inspector adapter={adapter} row={selected} relatedRows={relatedRows} queryUpdatedAt={primary.dataUpdatedAt} />
        </div>
      )}
    </section>
  );
}
