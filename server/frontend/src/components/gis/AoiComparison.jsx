import React, { Suspense, lazy, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { federation } from '@/api/federationClient';
import { acquireOnlineSource } from '@/gis/acquisitionFacade';
import {
  MIN_COMBINED_RECORDS, NOT_A_FINDING, aoiFromBbox, aoiFromMunicipio, compareAois, comparisonReceipt,
} from '@/gis/aoiComparison';
import { PROPERTY_MAP_BASEMAPS } from '@/gis/basemaps';
import { MUNICIPIO_BOUNDARY_SOURCE_ID, boundaryName, categoryColors, featureCollection, featurePaint } from '@/gis/propertyMap';
import { describeStore } from '@/gis/storeBasis';
import { downloadText } from '@/lib/download';

// AOI comparison with negative controls (FDX-028/029; directive §32 and §46).
// A study AOI is compared with disjoint control AOIs by records per km², per
// (producer, stream, category). Every result is a BACKGROUND COMPARISON, not a
// finding, and is read against the store's sampling basis. Only points whose
// producer declared a placed point count; stand-ins are counted apart.
const PropertyMapCanvas = lazy(() => import('@/components/gis/PropertyMapCanvas'));

const INITIAL_VIEW = Object.freeze({ bounds: [[-67.3, 17.85], [-65.2, 18.55]] });
const ROLE_OUTLINE = Object.freeze({
  color: '#94a3b8', dashed: false, byProperty: Object.freeze({ name: 'role', colors: Object.freeze({ study: '#f59e0b', control: '#38bdf8' }) }),
});
const button = 'min-h-[44px] rounded-md border border-border px-3 text-sm font-medium hover:bg-muted disabled:opacity-50';
const field = 'min-h-[44px] w-full rounded-md border border-border bg-background px-2 text-sm';

let nextId = 0;
const newRow = (role) => ({ id: `aoi-${nextId += 1}`, role, kind: 'bbox', text: '', name: '' });

// "Study AOI" or "Control n", numbered by position among the controls.
function titleOf(row, controls) {
  return row.role === 'study' ? 'Study AOI' : `Control ${controls.indexOf(row) + 1}`;
}

function formatRatio(row) {
  if (row.status === 'TOO_FEW') return `too few records to compare (fewer than ${MIN_COMBINED_RECORDS} combined)`;
  const number = (value) => (value === Infinity ? '∞' : value.toFixed(2));
  if (row.ratio === Infinity) return `∞ (no control records; 95% CI ${number(row.ci[0])}–${number(row.ci[1])})`;
  return `${number(row.ratio)} (95% CI ${number(row.ci[0])}–${number(row.ci[1])})`;
}

function AoiRow({ row, title, boundaries, removable, onChange, onRemove }) {
  const municipios = boundaries?.features ? [...new Set(boundaries.features.map((item) => boundaryName(item.properties)).filter(Boolean))].sort() : [];
  return (
    <li className="grid gap-2 rounded-md border border-border p-2 sm:grid-cols-[10rem_1fr_auto]" data-aoi-row={row.role}>
      <label className="text-xs">
        {title} kind
        <select aria-label={`${title} kind`} className={field} value={row.kind} onChange={(event) => onChange({ kind: event.target.value })}>
          <option value="bbox">Bounding box</option>
          <option value="municipio">Municipio</option>
        </select>
      </label>
      {row.kind === 'bbox' ? (
        <label className="text-xs">
          {title} bounding box
          <input
            aria-label={`${title} bounding box`} className={field} value={row.text} placeholder="minLon,minLat,maxLon,maxLat"
            onChange={(event) => onChange({ text: event.target.value })}
          />
        </label>
      ) : (
        <label className="text-xs">
          {title} municipio
          <select
            aria-label={`${title} municipio`} className={field} value={row.name} disabled={!municipios.length}
            onChange={(event) => onChange({ name: event.target.value })}
          >
            <option value="">{municipios.length ? 'Choose a municipio…' : 'Load the boundary layer first'}</option>
            {municipios.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
      )}
      {removable ? <button type="button" className={`${button} self-end`} aria-label={`Remove ${title}`} onClick={onRemove}>Remove</button> : <span />}
    </li>
  );
}

function Results({ comparison, store, onDownload }) {
  const { result } = comparison;
  const outside = result.outside;
  return (
    <section aria-labelledby="ac-results" className="space-y-3 rounded-xl border border-border bg-card p-3">
      <h3 id="ac-results" className="font-semibold">Results</h3>
      <p data-not-a-finding className="inline-block rounded-md border border-amber-500/60 bg-amber-500/10 px-2 py-1 text-sm font-semibold">{NOT_A_FINDING}</p>
      <div data-aoi-summary className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <caption className="sr-only">Areas compared</caption>
          <thead><tr><th scope="col">AOI</th><th scope="col">Role</th><th scope="col">Basis</th><th scope="col">Area (km²)</th></tr></thead>
          <tbody>
            {result.aois.map((item, index) => (
              <tr key={item.id}>
                <th scope="row">{item.label}</th>
                <td>{index === 0 ? 'study' : 'control'}</td>
                <td>{item.source}; {item.areaMethod}</td>
                <td>{(item.areaM2 / 1e6).toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <caption className="sr-only">Records per km² in the study AOI and the pooled controls, by category</caption>
          <thead>
            <tr>
              <th scope="col">Category (producer · stream · type)</th>
              <th scope="col">Study records</th><th scope="col">Study per km²</th>
              <th scope="col">Control records</th><th scope="col">Controls per km²</th>
              <th scope="col">Rate ratio</th><th scope="col">Exact p</th>
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row) => (
              <tr key={row.key} data-comparison-row={row.key}>
                <th scope="row">{row.producer} · {row.stream} · {row.category}</th>
                <td>
                  <span data-study-count>{row.study.count}</span>
                  {row.study.undetermined ? <span data-study-stand-ins className="block text-muted-foreground">{row.study.undetermined} stand-in{row.study.undetermined === 1 ? '' : 's'}, membership not determined</span> : null}
                </td>
                <td>{row.study.perKm2.toFixed(4)}</td>
                <td>
                  <span data-control-count>{row.controls.count}</span>
                  {row.controls.undetermined ? <span className="block text-muted-foreground">{row.controls.undetermined} stand-in{row.controls.undetermined === 1 ? '' : 's'}, membership not determined</span> : null}
                </td>
                <td>{row.controls.perKm2.toFixed(4)}</td>
                <td data-ratio>{formatRatio(row)}</td>
                <td data-p>{row.p === null ? '—' : row.p.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs" data-multiplicity>{result.multiplicity}</p>
      <p className="text-xs" data-outside>{outside} record{outside === 1 ? ' is' : 's are'} outside every AOI and not counted.</p>
      <p className="text-xs text-muted-foreground" data-results-store>{describeStore(store).text}</p>
      <button type="button" className={button} onClick={onDownload}>Download receipt (JSON)</button>
    </section>
  );
}

export default function AoiComparison() {
  const query = useQuery({ queryKey: ['spatial-features', false, null], queryFn: () => federation.spatial.features({}) });
  const data = query.data;
  const colors = useMemo(() => categoryColors(data?.categories || []), [data]);
  const paint = useMemo(() => featurePaint(colors), [colors]);
  const [rows, setRows] = useState(() => [newRow('study'), newRow('control')]);
  const [boundary, setBoundary] = useState({ status: 'idle', layer: null, error: null });
  const [comparison, setComparison] = useState(null);
  const [errors, setErrors] = useState([]);

  const update = (id, patch) => setRows((previous) => previous.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  const controlsOnly = rows.filter((row) => row.role === 'control');

  async function loadBoundary() {
    setBoundary({ status: 'loading', layer: null, error: null });
    try {
      setBoundary({ status: 'loaded', layer: await acquireOnlineSource(MUNICIPIO_BOUNDARY_SOURCE_ID), error: null });
    } catch (error) {
      setBoundary({ status: 'error', layer: null, error: error.message });
    }
  }

  function compare() {
    const boundaries = boundary.layer?.geojson || null;
    const built = [];
    const problems = [];
    rows.forEach((row) => {
      const title = titleOf(row, controlsOnly);
      try {
        built.push(row.kind === 'municipio'
          ? aoiFromMunicipio(row.id, row.name, boundaries)
          : aoiFromBbox(row.id, `${title.replace('Study AOI', 'Study')} (bbox)`, row.text));
      } catch (error) {
        problems.push(`${title}: ${error.message}`);
      }
    });
    if (problems.length) {
      setErrors(problems);
      setComparison(null);
      return;
    }
    const result = compareAois({ features: data.features, study: built[0], controls: built.slice(1) });
    if (result.errors) {
      setErrors(result.errors);
      setComparison(null);
      return;
    }
    setErrors([]);
    setComparison({ result, generatedAt: new Date().toISOString() });
  }

  const outline = useMemo(() => featureCollection((comparison?.result.aois || []).map((item, index) => (
    { type: 'Feature', geometry: item.geometry, properties: { role: index === 0 ? 'study' : 'control', label: item.label } }))), [comparison]);

  return (
    <div className="space-y-4" data-aoi-comparison>
      <div>
        <h2 className="text-lg font-semibold">AOI comparison</h2>
        <p className="text-sm text-muted-foreground">
          Compare records per km² in a study area with disjoint control areas. A ratio above 1 means more records per km² in the study
          area than in the controls; it says nothing about why (reporting, population, infrastructure or how the store was sampled).
        </p>
      </div>
      {query.isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading Hub records…</p> : null}
      {query.isError ? (
        <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          The Hub could not return spatial features: {query.error?.message}
        </div>
      ) : null}
      {data ? (
        <>
          <p role="note" data-store-basis className="rounded-md border border-amber-500/60 bg-amber-500/10 p-2 text-sm">{describeStore(data.store).text}</p>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,32rem)]">
            <div className="h-[380px] overflow-hidden rounded-xl border border-border">
              <Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading the map…</div>}>
                <PropertyMapCanvas
                  testId="aoi-map" label="Map of the study and control areas over the Hub records. The areas are also listed in the results."
                  basemap={PROPERTY_MAP_BASEMAPS.cartoDark} initialView={INITIAL_VIEW} features={data.features} paint={paint}
                  outline={outline} outlineStyle={ROLE_OUTLINE} selectedId={null} intelPoint={null} radiusM={0} focusPoint={null}
                  onSelectFeature={() => {}} onPickPoint={() => {}}
                />
              </Suspense>
            </div>
            <section aria-labelledby="ac-aois" className="space-y-2 rounded-xl border border-border bg-card p-3">
              <h3 id="ac-aois" className="font-semibold">Areas</h3>
              <p className="text-xs text-muted-foreground">
                The study area is outlined amber and controls blue on the map. Areas must not overlap, and a record counts only where its
                producer declared a placed point.
              </p>
              <ul className="space-y-2">
                {rows.map((row) => (
                  <AoiRow
                    key={row.id} row={row} title={titleOf(row, controlsOnly)}
                    boundaries={boundary.layer?.geojson} removable={row.role === 'control' && controlsOnly.length > 1}
                    onChange={(patch) => update(row.id, patch)} onRemove={() => setRows((previous) => previous.filter((item) => item.id !== row.id))}
                  />
                ))}
              </ul>
              <div className="flex flex-wrap gap-2">
                <button type="button" className={button} onClick={() => setRows((previous) => [...previous, newRow('control')])}>Add control AOI</button>
                <button type="button" className={button} onClick={loadBoundary} disabled={boundary.status === 'loading'}>
                  {boundary.status === 'loading' ? 'Loading municipio boundaries…' : 'Load municipio boundaries (TIGERweb 2025)'}
                </button>
                <button type="button" className={button} onClick={compare}>Compare</button>
              </div>
              {boundary.status === 'error' ? <p role="alert" className="text-xs text-destructive">Boundary layer unavailable: {boundary.error}</p> : null}
              {errors.length ? (
                <ul role="alert" className="list-disc pl-4 text-sm text-destructive">{errors.map((message) => <li key={message}>{message}</li>)}</ul>
              ) : null}
            </section>
          </div>
          {comparison ? (
            <Results
              comparison={comparison} store={data.store}
              onDownload={() => downloadText('aoi-comparison.json', JSON.stringify(comparisonReceipt({
                result: comparison.result, store: data.store, generatedAt: comparison.generatedAt,
              }), null, 2), 'application/json')}
            />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
