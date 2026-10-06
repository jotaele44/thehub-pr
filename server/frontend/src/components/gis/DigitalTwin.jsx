import React, { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { federation } from '@/api/federationClient';
import { PrecisionMarker, SelectedRecord } from '@/components/gis/PropertyMap';
import { terrainSource } from '@/gis/advanced3dSourceRegistry';
import { BASEMAPS, IMAGERY_BASEMAPS } from '@/gis/basemaps';
import { CUDEM_PR, covers, elevationAt, formatElevation } from '@/gis/cudem';
import {
  DIGITAL_TWIN_PANELS, TIME_WINDOWS, filterByTime, findingFeatures, findingStatement, geojsonExport, liveCounts, liveStatement,
  panelFrom, timeBounds, timeWindow, usdaExport,
} from '@/gis/digitalTwin';
import { categoryColors, featurePaint, precisionStyle } from '@/gis/propertyMap';
import { cn } from '@/lib/utils';

// Digital Twin (TWIN-005/150..163, FDX-023/030/031; directive §11). One shared
// state drives four panels: perspective (Cesium on the uniform-datum CUDEM
// terrain), ortho, overhead imagery and details. Selection, camera and the time
// cursor are synchronized; every count says what it counts.
const DigitalTwinPerspective = lazy(() => import('@/components/gis/DigitalTwinPerspective'));
const PropertyMapCanvas = lazy(() => import('@/components/gis/PropertyMapCanvas'));

const INITIAL_VIEW = Object.freeze({ center: [-66.25, 18.2], zoom: 8.6, bearing: 0 });
const PLAY_STEP_DAYS = 30;
const PLAY_INTERVAL_MS = 400;
const LIST_LIMIT = 50;
const button = 'min-h-[36px] rounded-md border border-border px-2 text-xs font-medium hover:bg-muted disabled:opacity-50';
const control = 'min-h-[36px] rounded-md border border-border bg-background px-2 text-xs';

function dateText(ms) {
  return Number.isFinite(ms) ? new Date(ms).toISOString().slice(0, 10) : '—';
}

function download(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function Panel({ id, label, maximized, onMaximize, children }) {
  const ref = useRef(null);
  const isMax = maximized === id;
  const fullscreenAvailable = typeof document !== 'undefined' && document.fullscreenEnabled;
  return (
    <section
      ref={ref} aria-label={label} data-dt-panel={id} data-maximized={isMax ? 'true' : 'false'}
      className={cn('flex min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-card',
        maximized && !isMax && 'hidden', isMax ? 'col-span-2 h-[720px]' : 'h-[420px]')}
    >
      <header className="flex items-center justify-between gap-2 border-b border-border px-3 py-1.5">
        <h3 className="text-sm font-semibold">{label}</h3>
        <div className="flex gap-1">
          <button type="button" className={button} aria-pressed={isMax} onClick={() => onMaximize(isMax ? null : id)}>
            {isMax ? `Restore ${label}` : `Maximize ${label}`}
          </button>
          {fullscreenAvailable ? (
            <button type="button" className={button} onClick={() => ref.current?.requestFullscreen?.()}>Fullscreen</button>
          ) : null}
        </div>
      </header>
      <div className="relative min-h-0 flex-1">{children}</div>
    </section>
  );
}

function Elevation({ point }) {
  const inside = point && covers([point.lon, point.lat, point.lon, point.lat]);
  const query = useQuery({
    queryKey: ['cudem-elevation', point?.lon, point?.lat],
    queryFn: () => elevationAt(point.lon, point.lat),
    enabled: Boolean(inside),
    staleTime: Infinity,
  });
  let text = 'Select a record to read its CUDEM elevation.';
  if (point && !inside) text = 'Outside CUDEM coverage (no height reported).';
  else if (query.isLoading) text = 'Reading CUDEM…';
  else if (query.isError) text = `CUDEM could not be read: ${query.error?.message}`;
  else if (point && query.data === null) text = 'CUDEM has no value here (no height reported).';
  else if (query.data) text = formatElevation(query.data);
  return <dd data-dt-elevation>{text}</dd>;
}

function DetailsPanel({ selected, point, visible, onSelect, selectedId, tilesRead, terrainError, terrain, counts, timeRange }) {
  return (
    <div className="h-full space-y-3 overflow-y-auto p-3 text-xs">
      {selected ? <SelectedRecord feature={selected} /> : <p className="text-muted-foreground">No record selected.</p>}
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        <dt className="text-muted-foreground">Point</dt>
        <dd>{point ? `${point.lat.toFixed(5)}, ${point.lon.toFixed(5)} (WGS84)` : '—'}</dd>
        <dt className="text-muted-foreground">Elevation</dt>
        <Elevation point={point} />
        <dt className="text-muted-foreground">Time window</dt>
        <dd data-dt-window>{timeRange ? `${dateText(timeRange[0])} to ${dateText(timeRange[1])}` : 'No dated records'}</dd>
        <dt className="text-muted-foreground">Records</dt>
        <dd data-dt-counts>{counts.visible} shown · {counts.outside} outside the time window · {counts.undated} undated</dd>
      </dl>
      <section aria-labelledby="dt-records" data-dt-records>
        <h4 id="dt-records" className="font-semibold">Records shown</h4>
        <ul className="max-h-48 space-y-0.5 overflow-y-auto">
          {visible.slice(0, LIST_LIMIT).map((item) => (
            <li key={item.id}>
              <button
                type="button" aria-pressed={item.id === selectedId} data-dt-record={item.id}
                className={cn('flex min-h-[32px] w-full items-center gap-2 rounded px-1 text-left hover:bg-muted', item.id === selectedId && 'bg-muted')}
                onClick={() => onSelect(item.id)}
              >
                <PrecisionMarker marker={precisionStyle(item.properties.geometry_precision)?.marker} />
                <span className="truncate">{item.properties.title} · {item.properties.category}</span>
              </button>
            </li>
          ))}
        </ul>
        {visible.length > LIST_LIMIT ? <p className="text-muted-foreground">Showing {LIST_LIMIT} of {visible.length}.</p> : null}
      </section>
      <section aria-labelledby="dt-dem" data-dt-dem-provenance>
        <h4 id="dt-dem" className="font-semibold">Terrain (DEM) provenance</h4>
        <p>{CUDEM_PR.label}. {CUDEM_PR.provider}; dataset {CUDEM_PR.datasetId}, created {CUDEM_PR.created}, published {CUDEM_PR.published}; {CUDEM_PR.citation}.</p>
        <p>Vertical datum {CUDEM_PR.verticalDatum}, {CUDEM_PR.verticalUnits}; horizontal {CUDEM_PR.horizontalDatum}; {CUDEM_PR.resolution}.</p>
        <p data-dt-terrain-status>3D binding: {terrain?.status === 'READY_FOR_RUNTIME_BINDING' ? 'bound (uniform vertical datum)' : `not bound (${terrain?.status || 'no source'})`}.</p>
        <ul className="list-disc pl-4 text-muted-foreground">{CUDEM_PR.heightCaveats.map((line) => <li key={line}>{line}</li>)}</ul>
        <p data-dt-terrain-tiles>{tilesRead.length ? `CUDEM tiles read: ${tilesRead.join(', ')}` : 'No CUDEM tile read yet in this view.'}</p>
        {terrainError ? <p role="alert" className="text-destructive">Terrain tiles failed to load; the surface is flat there: {terrainError}</p> : null}
      </section>
      <section aria-labelledby="dt-imagery">
        <h4 id="dt-imagery" className="font-semibold">Imagery provenance</h4>
        <p>{IMAGERY_BASEMAPS.usgsImagery.attribution}. {IMAGERY_BASEMAPS.usgsImagery.note}</p>
      </section>
    </div>
  );
}

export default function DigitalTwin() {
  const [searchParams, setSearchParams] = useSearchParams();
  const maximized = panelFrom(searchParams);
  const [view, setView] = useState(INITIAL_VIEW);
  const [selectedId, setSelectedId] = useState(null);
  const [cursor, setCursor] = useState(null);
  const [windowId, setWindowId] = useState('cumulative');
  const [playing, setPlaying] = useState(false);
  const [showUndated, setShowUndated] = useState(true);
  const [showFindings, setShowFindings] = useState(true);
  const [liveOnly, setLiveOnly] = useState(false);
  const [tilesRead, setTilesRead] = useState([]);
  const [terrainError, setTerrainError] = useState(null);
  const [terrain] = useState(() => terrainSource(CUDEM_PR.sourceId));

  const query = useQuery({ queryKey: ['spatial-features', false, null], queryFn: () => federation.spatial.features({}) });
  const data = query.data;
  const all = useMemo(() => data?.features || [], [data]);
  const bounds = useMemo(() => timeBounds(data?.time_extent), [data]);
  const at = cursor ?? bounds?.end ?? null;
  const timeRange = useMemo(() => timeWindow(at, windowId, bounds), [at, windowId, bounds]);
  const findings = useMemo(() => findingFeatures(all), [all]);
  const live = useMemo(() => liveCounts(all), [all]);
  const pool = useMemo(() => all.filter((item) => (showFindings || item.properties.category !== 'finding')
    && (!liveOnly || ['LIVE', 'CURRENT'].includes(item.properties.temporal_state))), [all, showFindings, liveOnly]);
  const timed = useMemo(() => filterByTime(pool, timeRange, { showUndated }), [pool, timeRange, showUndated]);
  const colors = useMemo(() => categoryColors(data?.categories || []), [data]);
  const paint = useMemo(() => featurePaint(colors), [colors]);
  const selected = all.find((item) => item.id === selectedId) || null;
  // Elevation is read for the selected record only, so panning never fetches terrain blocks for a readout.
  const point = selected ? { lon: selected.geometry.coordinates[0], lat: selected.geometry.coordinates[1] } : null;

  useEffect(() => {
    if (!playing || !bounds) return undefined;
    const timer = setInterval(() => {
      setCursor((previous) => {
        const next = (previous ?? bounds.start) + PLAY_STEP_DAYS * 86_400_000;
        if (next >= bounds.end) { setPlaying(false); return bounds.end; }
        return next;
      });
    }, PLAY_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [playing, bounds]);

  function maximize(id) {
    setSearchParams((previous) => {
      const next = new URLSearchParams(previous);
      if (id) next.set('panel', id); else next.delete('panel');
      return next;
    });
  }

  function addTiles(names) {
    setTilesRead((previous) => (names.every((name) => previous.includes(name)) ? previous : [...new Set([...previous, ...names])].sort()));
  }

  function exportContext() {
    return {
      generatedAt: new Date().toISOString(),
      window: timeRange,
      filters: { show_undated: showUndated, show_findings: showFindings, live_or_current_only: liveOnly },
      counts: { visible: timed.visible.length, outside_time_window: timed.outside, undated: timed.undated, loaded: data?.loaded ?? null },
      layers: { records: 'Hub store (federation-spatial-features-v1)', terrain: terrain?.status === 'READY_FOR_RUNTIME_BINDING' ? CUDEM_PR.sourceId : null },
    };
  }

  const mapPanel = (testId, basemap, label) => (
    <Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading…</div>}>
      <PropertyMapCanvas
        testId={testId} label={label} basemap={basemap} initialView={INITIAL_VIEW} features={timed.visible} paint={paint}
        outline={null} selectedId={selectedId} intelPoint={null} radiusM={0} focusPoint={null}
        view={view} onViewChange={setView} onSelectFeature={setSelectedId}
      />
    </Suspense>
  );

  return (
    <div className="space-y-3" data-digital-twin>
      <div>
        <h2 className="text-lg font-semibold">Digital Twin</h2>
        <p className="text-sm text-muted-foreground">
          Hub-held records over uniform-datum terrain (NOAA CUDEM, PRVD02). Panels share one camera, one selection and one time cursor.
        </p>
      </div>
      {query.isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading records…</p> : null}
      {query.isError ? <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">The Hub could not return spatial features: {query.error?.message}</div> : null}
      {data ? (
        <section aria-label="Digital Twin controls" className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-3 text-xs">
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={showFindings} onChange={() => setShowFindings((value) => !value)} />
            Findings <span data-dt-findings-count className="font-semibold">({findings.length})</span>
          </label>
          <span data-dt-findings-status className="text-muted-foreground">{findingStatement(findings.length)}</span>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={liveOnly} onChange={() => setLiveOnly((value) => !value)} />
            Live / current only <span data-dt-live-count className="font-semibold">({live.LIVE + live.CURRENT})</span>
          </label>
          <span data-dt-live-status className="text-muted-foreground">{liveStatement(live)}</span>
          {bounds ? (
            <div className="flex flex-wrap items-center gap-2" data-dt-time>
              <button type="button" className={button} onClick={() => setPlaying((value) => !value)} aria-pressed={playing}>{playing ? 'Pause' : 'Play'}</button>
              <label className="flex items-center gap-1.5">
                Time
                <input
                  type="range" min={bounds.start} max={bounds.end} step={86_400_000} value={at}
                  aria-valuetext={dateText(at)} onChange={(event) => { setPlaying(false); setCursor(Number(event.target.value)); }}
                />
              </label>
              <span data-dt-cursor>{dateText(at)}</span>
              <label className="flex items-center gap-1.5">
                Window
                <select className={control} value={windowId} onChange={(event) => setWindowId(event.target.value)}>
                  {TIME_WINDOWS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                </select>
              </label>
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={showUndated} onChange={() => setShowUndated((value) => !value)} />
                Show undated ({timed.undated})
              </label>
            </div>
          ) : <span className="text-muted-foreground">No mapped record is dated, so there is no time to play.</span>}
          <button type="button" className={button} onClick={() => download('digital-twin.geojson', JSON.stringify(geojsonExport(timed.visible, exportContext()), null, 2), 'application/geo+json')}>Export GeoJSON</button>
          <button type="button" className={button} onClick={() => download('digital-twin.usda', usdaExport(timed.visible, { ...exportContext(), origin: { lon: view.center[0], lat: view.center[1] } }), 'model/vnd.usda')}>Export USD</button>
        </section>
      ) : null}
      <div className="grid gap-3 lg:grid-cols-2" data-dt-layout={maximized || 'grid'}>
        <Panel id="perspective" label={DIGITAL_TWIN_PANELS[0].label} maximized={maximized} onMaximize={maximize}>
          <Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading the 3D view…</div>}>
            <DigitalTwinPerspective
              features={timed.visible} colors={colors} selectedId={selectedId} view={view} onViewChange={setView}
              onSelectFeature={setSelectedId} onTerrainTiles={addTiles}
              onTerrainError={(error) => setTerrainError(String(error?.message || error))}
            />
          </Suspense>
        </Panel>
        <Panel id="ortho" label={DIGITAL_TWIN_PANELS[1].label} maximized={maximized} onMaximize={maximize}>
          {mapPanel('digital-twin-ortho', BASEMAPS.cartoDark, 'Top-down map. Every record shown is also listed in the Details panel.')}
        </Panel>
        <Panel id="overhead" label={DIGITAL_TWIN_PANELS[2].label} maximized={maximized} onMaximize={maximize}>
          {mapPanel('digital-twin-overhead', IMAGERY_BASEMAPS.usgsImagery, 'Overhead orthoimagery. Every record shown is also listed in the Details panel.')}
        </Panel>
        <Panel id="details" label={DIGITAL_TWIN_PANELS[3].label} maximized={maximized} onMaximize={maximize}>
          <DetailsPanel
            selected={selected} point={point} visible={timed.visible} onSelect={setSelectedId} selectedId={selectedId}
            tilesRead={tilesRead} terrainError={terrainError} terrain={terrain}
            counts={{ visible: timed.visible.length, outside: timed.outside, undated: timed.undated }} timeRange={timeRange}
          />
        </Panel>
      </div>
    </div>
  );
}
