import React, { Suspense, lazy, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { federation } from '@/api/federationClient';
import { acquireOnlineSource } from '@/gis/acquisitionFacade';
import { PROPERTY_MAP_BASEMAPS } from '@/gis/basemaps';
import { CUDEM_PR, elevationAt } from '@/gis/cudem';
import {
  DOCUMENTED_LAYERS, GROUP_STYLES, MODELLED_LABEL, buildProfile, crossings, haversineKm, interpretivePaint, modelledStatement,
  profileCsv, profilePath, profileSamples, profileStats, splitHubFeatures,
} from '@/gis/interpretive';
import { boundaryProvenance, categoryColors, featureCollection } from '@/gis/propertyMap';
import { getOnlineSourceDefinition, getProvider } from '@/gis/sourceRegistry';
import { describeStore } from '@/gis/storeBasis';
import { parseCoordinateQuery } from '@/lib/deepLinks';
import { downloadText } from '@/lib/download';

// Subsurface and interpretive layers (TWIN-075/076/077/146, FDX-024; directive §11).
// Documented geometry (what a source publishes) and modelled geometry (what a
// producer interpreted) are kept in separate groups with separate styling: a
// model never looks like observed underground geometry. No producer exports a
// subsurface model today, so the modelled group is empty and says why; the
// profile reads CUDEM heights along a line and draws nothing below the surface.
const PropertyMapCanvas = lazy(() => import('@/components/gis/PropertyMapCanvas'));

const PUERTO_RICO_EXTENT = Object.freeze([-67.3, 17.85, -65.2, 18.55]);
const INITIAL_VIEW = Object.freeze({ bounds: [[PUERTO_RICO_EXTENT[0], PUERTO_RICO_EXTENT[1]], [PUERTO_RICO_EXTENT[2], PUERTO_RICO_EXTENT[3]]] });
const PROFILE_SAMPLES = 100;
const READ_BATCH = 20;
const DATUM = 'PRVD02';
const button = 'min-h-[44px] rounded-md border border-border px-3 text-sm font-medium hover:bg-muted disabled:opacity-50';
const input = 'min-h-[44px] w-full rounded-md border border-border bg-background px-2 text-sm';

function Swatch({ style }) {
  const hatched = style.swatch === 'hatched';
  return (
    <span
      data-swatch={style.swatch} aria-hidden="true" className="inline-block h-4 w-6 rounded-sm border"
      style={{
        borderColor: style.color,
        background: hatched
          ? `repeating-linear-gradient(45deg, ${style.color} 0 2px, transparent 2px 5px)`
          : style.color,
      }}
    />
  );
}

function pointText(point) {
  return `${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`;
}

function DocumentedLayer({ layer, state, visible, onLoad, onToggle }) {
  const source = getOnlineSourceDefinition(layer.sourceId);
  const record = state?.status === 'loaded' ? boundaryProvenance(state.layer, source, getProvider(source.providerId)) : null;
  return (
    <li data-layer={layer.sourceId} className="space-y-1 rounded-md border border-border p-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{source.label}</span>
        <button type="button" className={button} onClick={onLoad} disabled={state?.status === 'loading'}>
          {state?.status === 'loading' ? 'Loading…' : `Load ${source.label}`}
        </button>
        {record ? (
          <label className="flex items-center gap-1.5 text-xs">
            <input type="checkbox" checked={visible} onChange={onToggle} /> Show on map
          </label>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground">{layer.role}</p>
      {state?.status === 'error' ? <p role="alert" className="text-xs text-destructive">Layer unavailable: {state.error}</p> : null}
      {record ? (
        <p className="text-xs" data-layer-provenance>
          {record.featureCount} feature{record.featureCount === 1 ? '' : 's'} · {record.provider} · registry certification {record.registryCertification}
          · acquisition {record.acquisitionStatus} · retrieved {record.retrievedAt} · snapshot SHA-256 {String(record.snapshotSha256).slice(0, 12)}…
        </p>
      ) : null}
    </li>
  );
}

function ProfileChart({ profile }) {
  const { path, min, max } = profilePath(profile, { width: 640, height: 200, pad: 8 });
  return (
    <svg
      data-profile-chart viewBox="0 0 640 200" role="img" className="h-48 w-full rounded-md border border-border bg-background"
      aria-label={`Terrain profile, ${DATUM} heights from CUDEM, ${profile.totalKm.toFixed(1)} km, ${min.toFixed(0)} to ${max.toFixed(0)} m`}
    >
      <path d={path} fill="none" stroke={GROUP_STYLES.documented.color} strokeWidth="2" />
    </svg>
  );
}

function ProfilePanel({ profile, status, error, tiles, found, onDownload }) {
  if (status === 'error') return <p role="alert" className="text-sm text-destructive">{error}</p>;
  if (status === 'reading') return <p role="status" className="text-sm text-muted-foreground">Reading CUDEM along the line…</p>;
  if (status === 'empty') return <p role="status" className="text-sm" data-profile-empty>CUDEM has no value along this line, so no profile is drawn (a gap is never drawn as zero).</p>;
  if (!profile) return <p className="text-sm text-muted-foreground">No profile yet. Give a start and an end, or click two points on the map.</p>;
  const stats = profileStats(profile);
  return (
    <div className="space-y-2">
      <ProfileChart profile={profile} />
      <p className="text-xs" data-profile-stats>
        {profile.samples.length} samples · {stats.withHeight} with a CUDEM height · {stats.gaps} without (gaps, not zero) ·
        {' '}{profile.totalKm.toFixed(2)} km, about {(profile.totalKm / (profile.samples.length - 1)).toFixed(2)} km between samples ·
        {' '}{stats.min.toFixed(1)} to {stats.max.toFixed(1)} m
      </p>
      <p className="text-xs text-muted-foreground" data-profile-datum>
        Heights: {DATUM} (EPSG:6641) from {CUDEM_PR.label}, tiles read: {tiles.join(', ') || 'none'}. One datum on one axis.
      </p>
      <p className="rounded-md border border-dashed border-border p-2 text-xs" data-profile-subsurface>
        No subsurface model supplied — nothing is drawn below the surface.
      </p>
      <section aria-label="Documented layers crossed" data-profile-crossings className="text-xs">
        <h4 className="font-semibold">Documented layers crossed (surface outlines only)</h4>
        {found.length ? (
          <ul className="list-disc pl-4">
            {found.map((item) => (
              <li key={`${item.layerId}-${item.startKm}`}>
                {item.label}: km {item.startKm.toFixed(2)} to {item.endKm.toFixed(2)} ({item.samples} sample{item.samples === 1 ? '' : 's'} inside)
              </li>
            ))}
          </ul>
        ) : <p className="text-muted-foreground">None of the loaded, shown layers is crossed by this line.</p>}
      </section>
      <button type="button" className={button} onClick={onDownload}>Download CSV</button>
    </div>
  );
}

export default function InterpretiveLayers() {
  const query = useQuery({ queryKey: ['spatial-features', false, null], queryFn: () => federation.spatial.features({}) });
  const data = query.data;
  const split = useMemo(() => splitHubFeatures(data?.features || []), [data]);
  const colors = useMemo(() => categoryColors(data?.categories || []), [data]);
  const paint = useMemo(() => interpretivePaint(colors), [colors]);
  const hubFeatures = useMemo(() => [...split.documented, ...split.modelled], [split]);

  const [layers, setLayers] = useState({});
  const [visible, setVisible] = useState({});
  const [startText, setStartText] = useState('');
  const [endText, setEndText] = useState('');
  const [profile, setProfile] = useState({ status: 'idle', value: null, error: null, tiles: [], line: null });
  const request = useRef(0);

  async function loadLayer(sourceId) {
    setLayers((previous) => ({ ...previous, [sourceId]: { status: 'loading' } }));
    try {
      const layer = await acquireOnlineSource(sourceId);
      setLayers((previous) => ({ ...previous, [sourceId]: { status: 'loaded', layer } }));
      setVisible((previous) => ({ ...previous, [sourceId]: true }));
    } catch (error) {
      setLayers((previous) => ({ ...previous, [sourceId]: { status: 'error', error: error.message } }));
    }
  }

  // Recomputed only when a layer loads or is shown or hidden, so typing a coordinate does not resend GeoJSON to the map.
  const shown = useMemo(() => DOCUMENTED_LAYERS
    .filter((layer) => layers[layer.sourceId]?.status === 'loaded' && visible[layer.sourceId])
    .map((layer) => ({
      id: layer.sourceId,
      label: getOnlineSourceDefinition(layer.sourceId).label,
      features: layers[layer.sourceId].layer.geojson.features,
    })), [layers, visible]);
  const outline = useMemo(() => featureCollection(shown.flatMap((layer) => layer.features.map((item) => (
    { ...item, properties: { ...item.properties, layer: layer.id } })))), [shown]);

  function pick(point) {
    if (!startText || endText) { setStartText(pointText(point)); setEndText(''); } else setEndText(pointText(point));
  }

  async function drawProfile(event) {
    event.preventDefault();
    const start = parseCoordinateQuery(startText);
    const end = parseCoordinateQuery(endText);
    const problem = (!start && 'Start is not a "lat, lon" pair.') || (!end && 'End is not a "lat, lon" pair.');
    if (problem) {
      setProfile({ status: 'error', value: null, error: problem, tiles: [], line: null });
      return;
    }
    const mine = request.current + 1;
    request.current = mine;
    const a = [start.lon, start.lat];
    const b = [end.lon, end.lat];
    const line = featureCollection([
      { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [a, b] } },
      { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: a } },
      { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: b } },
    ]);
    setProfile({ status: 'reading', value: null, error: null, tiles: [], line });
    try {
      const samples = profileSamples(a, b, PROFILE_SAMPLES);
      const heights = [];
      const tiles = new Set();
      for (let index = 0; index < samples.length; index += READ_BATCH) {
        const batch = await Promise.all(samples.slice(index, index + READ_BATCH).map((sample) => elevationAt(sample.lon, sample.lat)));
        for (const result of batch) {
          heights.push(result ? result.metres : null);
          if (result?.tile) tiles.add(result.tile);
        }
        if (request.current !== mine) return;
      }
      const value = buildProfile(samples, heights, DATUM);
      setProfile(profileStats(value)
        ? { status: 'ready', value, error: null, tiles: [...tiles].sort(), line }
        : { status: 'empty', value: null, error: null, tiles: [], line });
    } catch (error) {
      if (request.current === mine) setProfile({ status: 'error', value: null, error: `CUDEM could not be read: ${error.message}`, tiles: [], line });
    }
  }

  const found = profile.value ? crossings(profile.value, shown) : [];
  const modelledCount = split.modelled.length;
  return (
    <div className="space-y-4" data-interpretive-layers>
      <div>
        <h2 className="text-lg font-semibold">Subsurface and interpretive layers</h2>
        <p className="text-sm text-muted-foreground">
          What a source documents and what a producer modelled are kept apart, with different styling. A model never looks like
          observed underground geometry. Terrain heights are CUDEM, {DATUM}.
        </p>
      </div>
      {query.isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading Hub records…</p> : null}
      {query.isError ? (
        <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          The Hub could not return spatial features: {query.error?.message}
        </div>
      ) : null}
      {data ? (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)]">
          <div className="space-y-4">
            <div className="h-[420px] overflow-hidden rounded-xl border border-border">
              <Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading the map…</div>}>
                <PropertyMapCanvas
                  testId="interpretive-map" label="Map of documented layers and the profile line. Layers are also listed beside the map."
                  basemap={PROPERTY_MAP_BASEMAPS.cartoDark} initialView={INITIAL_VIEW} features={hubFeatures} paint={paint}
                  outline={outline} outlineStyle={{ color: GROUP_STYLES.documented.color, dashed: false }} profile={profile.line}
                  selectedId={null} intelPoint={null} radiusM={0} focusPoint={null} onSelectFeature={() => {}} onPickPoint={pick}
                />
              </Suspense>
            </div>
            <section aria-labelledby="il-profile" className="space-y-2 rounded-xl border border-border bg-card p-3">
              <h3 id="il-profile" className="font-semibold">Terrain profile</h3>
              <form className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]" onSubmit={drawProfile}>
                <label className="text-xs">
                  Start (lat, lon)
                  <input className={input} value={startText} onChange={(event) => setStartText(event.target.value)} inputMode="decimal" placeholder="18.17, -66.59" />
                </label>
                <label className="text-xs">
                  End (lat, lon)
                  <input className={input} value={endText} onChange={(event) => setEndText(event.target.value)} inputMode="decimal" placeholder="18.40, -66.10" />
                </label>
                <button type="submit" className={`${button} self-end`} disabled={profile.status === 'reading'}>Draw profile</button>
              </form>
              <ProfilePanel
                profile={profile.value} status={profile.status} error={profile.error} tiles={profile.tiles} found={found}
                onDownload={() => downloadText('terrain-profile.csv', profileCsv(profile.value), 'text/csv')}
              />
            </section>
          </div>
          <div className="space-y-4">
            <section aria-labelledby="il-documented" data-group="documented" className="space-y-2 rounded-xl border border-border bg-card p-3">
              <h3 id="il-documented" className="flex items-center gap-2 font-semibold">
                <Swatch style={GROUP_STYLES.documented} /> Documented
              </h3>
              <p className="text-xs text-muted-foreground">{GROUP_STYLES.documented.note} Outlines are surface geometry as published; none is a subsurface model.</p>
              <ul className="space-y-2">
                {DOCUMENTED_LAYERS.map((layer) => (
                  <DocumentedLayer
                    key={layer.sourceId} layer={layer} state={layers[layer.sourceId]} visible={Boolean(visible[layer.sourceId])}
                    onLoad={() => loadLayer(layer.sourceId)} onToggle={() => setVisible((previous) => ({ ...previous, [layer.sourceId]: !previous[layer.sourceId] }))}
                  />
                ))}
              </ul>
              <p className="text-xs text-muted-foreground" data-store-basis>{describeStore(data.store).text}</p>
              <p className="text-xs" data-hub-documented>
                {split.documented.length
                  ? `${split.documented.length} Hub-held documented record${split.documented.length === 1 ? '' : 's'} (USGS mineral occurrences, drawn at their declared precision).`
                  : 'No Hub-held documented geology record is held in the store.'}
              </p>
            </section>
            <section aria-labelledby="il-modelled" data-group="modelled" className="space-y-2 rounded-xl border border-border bg-card p-3">
              <h3 id="il-modelled" className="flex items-center gap-2 font-semibold">
                <Swatch style={GROUP_STYLES.modelled} /> {MODELLED_LABEL}
              </h3>
              <p className="text-xs" data-modelled-statement>
                <span data-modelled-count className="font-semibold">{modelledCount}</span> modelled records. {modelledStatement(modelledCount)}
              </p>
              {modelledCount ? (
                <ul className="list-disc pl-4 text-xs">
                  {split.modelled.map((item) => (
                    <li key={item.id}>MODELLED · {item.properties.title} · {item.properties.category} · {item.properties.producer}</li>
                  ))}
                </ul>
              ) : null}
            </section>
            <p className="text-xs text-muted-foreground">
              {split.other} other Hub-held record{split.other === 1 ? '' : 's'} are not geology layers and are not shown here (see the Property Map).
              Distances are great-circle ({haversineKm([0, 0], [0, 1]).toFixed(1)} km per degree on the reference sphere).
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
