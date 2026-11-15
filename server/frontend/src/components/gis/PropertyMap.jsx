import React, { Suspense, lazy, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { federation } from '@/api/federationClient';
import { acquireOnlineSource } from '@/gis/acquisitionFacade';
import { PROPERTY_MAP_BASEMAPS } from '@/gis/basemaps';
import {
  MUNICIPIO_BOUNDARY_SOURCE_ID, PRECISION_STYLES, SPATIAL_CONTRACT, areaReferenceGroups, bboxAreaM2, boundaryProvenance,
  categoryColors, circleAreaM2, featurePaint, formatArea, joinAreaReferences, municipalityAt, objectTypesOf,
  parseBboxText, precisionStyle, visibleFeatures,
} from '@/gis/propertyMap';
import { getOnlineSourceDefinition, getProvider } from '@/gis/sourceRegistry';
import { parseCoordinateQuery } from '@/lib/deepLinks';
import { cn } from '@/lib/utils';

// Property Map (TWIN-006/132..149, FDX-021/022/027; directive §10). Hub-held
// records are placed only where their producer declared a point precision and
// are styled by that precision; everything else is counted and listed, never
// drawn as a point. Municipality-level references (OVNIS cases, per the
// 2026-10-03 decision) are outlined on TIGERweb municipio boundaries by exact
// folded name; values that name no municipio are listed as recorded.
const PropertyMapCanvas = lazy(() => import('@/components/gis/PropertyMapCanvas'));

const RADII = [250, 500, 1000, 2000, 5000];
// Without a map link the Property Map opens fitted to Puerto Rico, Vieques and Culebra.
const PUERTO_RICO_EXTENT = Object.freeze([-67.3, 17.85, -65.2, 18.55]);
const DEFAULT_GROUP = 'ovnis-pr|observations|uap_case';
const LIST_LIMIT = 100;
const NEARBY_LIMIT = 25;
const POINT_PRECISIONS = ['OBSERVED_POINT', 'INTERPRETED_POINT', 'REPRESENTATIVE_POINT'];
const panel = 'space-y-2 rounded-xl border border-border bg-card p-4 text-sm';
const control = 'min-h-[44px] rounded-md border border-border bg-background px-2 text-sm';
const button = 'min-h-[44px] rounded-md border border-border px-3 text-sm font-medium hover:bg-muted disabled:opacity-50';

// Drawn on the map's dark backdrop so the legend and list show each marker as the map does.
export function PrecisionMarker({ marker, color = '#cbd5e1' }) {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" className="shrink-0">
      <rect width="18" height="18" rx="3" fill="#1e293b" />
      {marker === 'solid' ? <circle cx="9" cy="9" r="5" fill={color} stroke="#ffffff" strokeWidth="1" /> : null}
      {marker === 'ringed' ? <circle cx="9" cy="9" r="5" fill={color} fillOpacity="0.55" stroke="#ffffff" strokeWidth="3" /> : null}
      {marker === 'hollow' ? <circle cx="9" cy="9" r="6" fill="none" stroke={color} strokeWidth="2" /> : null}
      {marker === 'outline' ? <rect x="2" y="3" width="14" height="12" fill="#a78bfa" fillOpacity="0.18" stroke="#a78bfa" strokeWidth="1.5" strokeDasharray="3 2" /> : null}
    </svg>
  );
}

function plainAttribution(text) {
  return String(text || '').replace(/&copy;/g, '©');
}

function formatDistance(metres) {
  return metres >= 1000 ? `${(metres / 1000).toFixed(2)} km` : `${Math.round(metres)} m`;
}

function formatPoint(point) {
  return `${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`;
}

function groupLabel(group) {
  return `${group.producer} · ${group.category} ${group.stream}`;
}

function UncertaintyLegend({ data, outlinedTotal }) {
  const unplaced = Object.entries(data.coordinates_without_point_precision || {});
  return (
    <section className={panel} aria-labelledby="pm-uncertainty" data-uncertainty-legend>
      <h3 id="pm-uncertainty" className="font-semibold">Geometry precision</h3>
      <ul className="space-y-2">
        {[...POINT_PRECISIONS, 'AREA_REFERENCE'].map((precision) => {
          const style = PRECISION_STYLES[precision];
          const count = precision === 'AREA_REFERENCE' ? outlinedTotal : (data.precision_counts?.[precision] || 0);
          return (
            <li key={precision} className="flex gap-2" data-precision-legend={precision}>
              <PrecisionMarker marker={style.marker} />
              <div>
                <div className="font-medium">{style.label} <span className="text-muted-foreground">({count})</span></div>
                <div className="text-xs text-muted-foreground">{style.description}</div>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="text-xs text-muted-foreground" data-unplaced-coordinates>
        {unplaced.length
          ? `Not drawn: ${unplaced.map(([producer, n]) => `${n} ${producer}`).join(', ')} rows carry coordinates without a declared point precision.`
          : 'Every row with coordinates declares its point precision.'}
      </p>
    </section>
  );
}

function CategoryLegend({ categories, colors, hidden, onToggle }) {
  const byCategory = new Map();
  for (const entry of categories) {
    const item = byCategory.get(entry.category) || { category: entry.category, count: 0, producers: new Set() };
    item.count += entry.count;
    item.producers.add(entry.producer);
    byCategory.set(entry.category, item);
  }
  return (
    <section className={panel} aria-labelledby="pm-categories" data-category-legend>
      <h3 id="pm-categories" className="font-semibold">Categories</h3>
      <p className="text-xs text-muted-foreground">The record types the producers exported, as recorded.</p>
      {byCategory.size === 0 ? <p className="text-xs text-muted-foreground">No mapped records in view.</p> : null}
      <ul className="space-y-1">
        {[...byCategory.values()].sort((a, b) => a.category.localeCompare(b.category)).map((item) => (
          <li key={item.category}>
            <label className="flex min-h-[32px] items-center gap-2">
              <input type="checkbox" checked={!hidden.has(item.category)} onChange={() => onToggle(item.category)} />
              <span aria-hidden="true" className="inline-block h-3 w-3 rounded-full" style={{ background: colors[item.category] }} />
              <span className="font-medium">{item.category}</span>
              <span className="text-xs text-muted-foreground">{item.count} · {[...item.producers].join(', ')}</span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

function AreaReferences({ data, boundary, onLoadBoundary, groupKey, onGroupChange, objectType, onObjectTypeChange, join }) {
  const groups = areaReferenceGroups(data.area_references);
  const group = groups.find((item) => item.key === groupKey);
  const account = group && (data.not_drawn || []).find((item) => (
    item.producer === group.producer && item.stream === group.stream && item.category === group.category));
  const recorded = group ? group.references.reduce((sum, ref) => sum + (objectType ? (ref.object_type_counts?.[objectType] || 0) : ref.count), 0) : 0;
  const total = account ? (objectType ? (account.object_type_counts?.[objectType] || 0) : account.count) : 0;
  const loaded = boundary.status === 'loaded';
  return (
    <section className={panel} aria-labelledby="pm-area-refs" data-area-references>
      <h3 id="pm-area-refs" className="font-semibold">Municipality-level records</h3>
      <p className="text-xs text-muted-foreground">
        Records that name a municipality but declare no point. Each is outlined on its municipio, never placed as a point.
      </p>
      {groups.length === 0 ? <p className="text-xs text-muted-foreground">No record in view names a municipality.</p> : (
        <>
          <label className="block text-xs font-medium" htmlFor="pm-area-group">Records</label>
          <select id="pm-area-group" className={cn(control, 'w-full')} value={groupKey || ''} onChange={(event) => onGroupChange(event.target.value)}>
            {groups.map((item) => <option key={item.key} value={item.key}>{groupLabel(item)}</option>)}
          </select>
          {group && objectTypesOf(group.references).length ? (
            <>
              <label className="block text-xs font-medium" htmlFor="pm-object-type">Object type (as recorded)</label>
              <select id="pm-object-type" className={cn(control, 'w-full')} value={objectType || ''} onChange={(event) => onObjectTypeChange(event.target.value || null)}>
                <option value="">All object types</option>
                {objectTypesOf(group.references).map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
            </>
          ) : null}
          {account ? (
            <p data-area-reference-counter className="text-xs">
              {total - recorded} of {total} record no municipality and are not mapped; {recorded} record a place value.
            </p>
          ) : null}
          {loaded ? (
            <p className="text-xs" data-outlined-total>{join.matchedTotal} outlined on {join.matched.length} municipio{join.matched.length === 1 ? '' : 's'}.</p>
          ) : (
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground" data-boundary-needed>Map outlines need the municipio boundary layer.</p>
              <button type="button" className={button} onClick={onLoadBoundary} disabled={boundary.status === 'loading'}>
                {boundary.status === 'loading' ? 'Loading municipio boundaries…' : 'Load municipio boundaries (TIGERweb 2025)'}
              </button>
              {boundary.status === 'error' ? <p role="alert" className="text-xs text-destructive">Boundary layer unavailable: {boundary.error}</p> : null}
            </div>
          )}
          {join.matched.length ? (
            <ul className="space-y-1 text-xs" aria-label="Outlined municipios">
              {join.matched.map((row) => (
                <li key={row.name} data-outlined-municipio={row.name}>
                  <span className="font-medium">{row.name}</span>: {row.count} (recorded as {[...new Set(row.recordedAs)].join(', ')})
                </li>
              ))}
            </ul>
          ) : null}
          {join.unmatched.length ? (
            <div className="space-y-1 text-xs" data-unmatched-values>
              <div className="font-medium">
                {loaded ? 'Recorded values that name no municipio (listed as recorded, not mapped)' : 'Recorded place values (not joined yet)'}
              </div>
              <ul className="space-y-0.5">
                {join.unmatched.map((row) => <li key={row.value}>“{row.value}”: {row.count}</li>)}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

function LayerProvenance({ data, basemap, boundary }) {
  const source = getOnlineSourceDefinition(MUNICIPIO_BOUNDARY_SOURCE_ID);
  const record = boundaryProvenance(boundary.layer, source, getProvider(source.providerId));
  return (
    <section className={panel} aria-labelledby="pm-provenance" data-layer-provenance>
      <h3 id="pm-provenance" className="font-semibold">Layer provenance</h3>
      <dl className="space-y-2 text-xs">
        <div>
          <dt className="font-medium">Hub records</dt>
          <dd className="text-muted-foreground">
            {SPATIAL_CONTRACT} · read from the Hub store as ingested from producer exports; no producer is called and nothing is geocoded.
            Point precision is the producer's own declaration. {data ? `${data.loaded} loaded, ${data.matched} drawn.` : ''}
          </dd>
        </div>
        <div>
          <dt className="font-medium">Basemap</dt>
          <dd className="text-muted-foreground">
            {basemap.label} · {plainAttribution(basemap.attribution)}. {basemap.note || 'Display context, not an evidence layer; not certified.'}
          </dd>
        </div>
        <div data-boundary-provenance>
          <dt className="font-medium">Municipio boundaries</dt>
          {record ? (
            <dd className="space-y-0.5 text-muted-foreground">
              <div>{record.provider} ({record.authority}) · {record.sourceId}</div>
              <div>Registry certification {record.registryCertification} · this acquisition {record.acquisitionStatus || 'not reported'}</div>
              <div>{record.featureCount} features · {record.crs} · retrieved {record.retrievedAt || 'time not recorded'}</div>
              <div className="break-all font-mono text-[10px]">Snapshot SHA-256 {record.snapshotSha256}</div>
              <div className="break-all font-mono text-[10px]">Query receipt SHA-256 {record.queryReceiptSha256}</div>
            </dd>
          ) : <dd className="text-muted-foreground">Not loaded. {source.label}, registry certification {source.certification}.</dd>}
        </div>
        <div>
          <dt className="font-medium">Elevation</dt>
          <dd className="text-muted-foreground">No elevation model is used in this view.</dd>
        </div>
      </dl>
    </section>
  );
}

export function SelectedRecord({ feature }) {
  if (!feature) return null;
  const props = feature.properties;
  const style = precisionStyle(props.geometry_precision);
  const [lon, lat] = feature.geometry.coordinates;
  return (
    <section className={panel} aria-labelledby="pm-selected" data-selected-record={props.evidence_id}>
      <h3 id="pm-selected" className="font-semibold">{props.title}</h3>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="text-muted-foreground">Category</dt><dd>{props.category}{props.object_type ? ` · ${props.object_type}` : ''}</dd>
        <dt className="text-muted-foreground">Producer</dt><dd>{props.producer}</dd>
        <dt className="text-muted-foreground">Precision</dt>
        <dd data-selected-precision={props.geometry_precision}>{style?.label}{props.geometry_basis ? ` · basis ${props.geometry_basis}` : ''}. {style?.description}</dd>
        <dt className="text-muted-foreground">Coordinates</dt><dd>{lat.toFixed(5)}, {lon.toFixed(5)} (WGS84, as recorded)</dd>
        <dt className="text-muted-foreground">Municipality</dt><dd>{props.municipality || 'Not recorded'}</dd>
        {props.synthetic ? <><dt className="text-muted-foreground">Synthetic</dt><dd>Yes, a test row</dd></> : null}
      </dl>
      <div className="flex gap-3 text-xs">
        <Link className="underline" to={props.evidence_href}>Provenance</Link>
        {props.entity_href ? <Link className="underline" to={props.entity_href}>Entity</Link> : null}
      </div>
    </section>
  );
}

function LocationIntel({ point, radiusM, onRadiusChange, onSubmitPoint, municipio, boundaryLoaded, includeSynthetic }) {
  const [text, setText] = useState('');
  const [inputError, setInputError] = useState(null);
  const intel = useQuery({
    queryKey: ['spatial-intel', point?.lat, point?.lon, radiusM, municipio, includeSynthetic],
    queryFn: () => federation.spatial.intel({ lat: point.lat, lon: point.lon, radiusM, municipality: municipio || undefined, includeSynthetic }),
    enabled: Boolean(point),
  });
  function submit(event) {
    event.preventDefault();
    const parsed = parseCoordinateQuery(text);
    if (!parsed) {
      setInputError('Enter a latitude and longitude, for example 18.2, -66.5.');
      return;
    }
    setInputError(null);
    onSubmitPoint({ lat: parsed.lat, lon: parsed.lon });
  }
  const body = intel.data;
  return (
    <section className={panel} aria-labelledby="pm-intel" data-location-intel>
      <h3 id="pm-intel" className="font-semibold">Location Intel</h3>
      <form className="flex flex-wrap items-end gap-2" onSubmit={submit}>
        <div>
          <label className="block text-xs font-medium" htmlFor="pm-intel-point">Location (lat, lon)</label>
          <input id="pm-intel-point" className={control} value={text} placeholder="18.2, -66.5" onChange={(event) => setText(event.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-medium" htmlFor="pm-intel-radius">Radius</label>
          <select id="pm-intel-radius" className={control} value={radiusM} onChange={(event) => onRadiusChange(Number(event.target.value))}>
            {RADII.map((value) => <option key={value} value={value}>{formatDistance(value)}</option>)}
          </select>
        </div>
        <button type="submit" className={button}>Show intel</button>
      </form>
      {inputError ? <p role="alert" className="text-xs text-destructive">{inputError}</p> : null}
      {!point ? <p className="text-xs text-muted-foreground">Click the map, select a record, or enter a location.</p> : (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-muted-foreground">Point</dt><dd data-intel-point>{formatPoint(point)} (WGS84)</dd>
          <dt className="text-muted-foreground">Municipio</dt>
          <dd data-intel-municipio>
            {!boundaryLoaded ? 'Not determined: the municipio boundary layer is not loaded.'
              : municipio ? `${municipio} (TIGERweb municipios 2025, point in polygon)`
                : 'Outside every municipio boundary (offshore or outside Puerto Rico).'}
          </dd>
          <dt className="text-muted-foreground">Radius area</dt><dd data-intel-area>{formatArea(circleAreaM2(radiusM))}</dd>
        </dl>
      )}
      {intel.isLoading && point ? <p role="status" className="text-xs text-muted-foreground">Reading what the Hub holds here…</p> : null}
      {intel.isError ? <p role="alert" className="text-xs text-destructive">Location Intel failed: {intel.error?.message}</p> : null}
      {body ? (
        <div className="space-y-2" data-intel-results>
          <p className="text-xs" data-intel-total>
            {body.nearby_total} mapped record{body.nearby_total === 1 ? '' : 's'} within {formatDistance(body.radius_m)}
            {body.nearby_total ? `: ${Object.entries(body.category_counts).map(([name, n]) => `${name} ${n}`).join(', ')}` : '.'}
          </p>
          <ul className="space-y-1 text-xs">
            {body.nearby.slice(0, NEARBY_LIMIT).map((row) => (
              <li key={row.evidence_id} data-intel-row={row.evidence_id}>
                <Link className="font-medium underline" to={row.evidence_href}>{row.title}</Link>
                {' '}· {row.category} · {formatDistance(row.distance_m)} · {precisionStyle(row.geometry_precision)?.label}
                {row.geometry_precision === 'REPRESENTATIVE_POINT' ? <span className="text-muted-foreground"> ({row.distance_basis})</span> : null}
              </li>
            ))}
          </ul>
          {body.nearby_total > NEARBY_LIMIT ? <p className="text-xs text-muted-foreground">Showing the nearest {NEARBY_LIMIT} of {body.nearby_total}.</p> : null}
          {body.municipality_area_references?.length ? (
            <div className="text-xs" data-intel-area-references>
              <div className="font-medium">Records that name {municipio} (not placed at this point)</div>
              <ul>{body.municipality_area_references.map((ref) => (
                <li key={`${ref.producer}|${ref.stream}|${ref.category}|${ref.municipality_as_recorded}`}>
                  {ref.producer} · {ref.category}: {ref.count} (recorded as “{ref.municipality_as_recorded}”)
                </li>
              ))}</ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export default function PropertyMap({ initialView, initialPoint = null }) {
  const [origin] = useState(() => (initialPoint ? initialView : {
    center: [(PUERTO_RICO_EXTENT[0] + PUERTO_RICO_EXTENT[2]) / 2, (PUERTO_RICO_EXTENT[1] + PUERTO_RICO_EXTENT[3]) / 2],
    bounds: PUERTO_RICO_EXTENT,
  }));
  const [basemapId, setBasemapId] = useState('cartoDark');
  const [includeSynthetic, setIncludeSynthetic] = useState(false);
  const [aoiText, setAoiText] = useState('');
  const [aoi, setAoi] = useState(null);
  const [aoiError, setAoiError] = useState(null);
  const [hidden, setHidden] = useState(() => new Set());
  const [selectedId, setSelectedId] = useState(null);
  const [intelPoint, setIntelPoint] = useState(initialPoint);
  const [focusPoint, setFocusPoint] = useState(null);
  const [radiusM, setRadiusM] = useState(1000);
  const [boundary, setBoundary] = useState({ status: 'idle', layer: null, error: null });
  const [groupChoice, setGroupChoice] = useState(null);
  const [objectType, setObjectType] = useState(null);
  const basemap = PROPERTY_MAP_BASEMAPS[basemapId];

  const query = useQuery({
    queryKey: ['spatial-features', includeSynthetic, aoi?.join(',') || null],
    queryFn: () => federation.spatial.features({ includeSynthetic, bbox: aoi }),
  });
  const data = query.data;
  const colors = useMemo(() => categoryColors(data?.categories || []), [data]);
  const paint = useMemo(() => featurePaint(colors), [colors]);
  const shown = useMemo(() => visibleFeatures(data?.features || [], hidden), [data, hidden]);
  const groups = useMemo(() => areaReferenceGroups(data?.area_references || []), [data]);
  const groupKey = groups.some((item) => item.key === groupChoice) ? groupChoice
    : (groups.find((item) => item.key === DEFAULT_GROUP) || groups[0])?.key || null;
  const group = groups.find((item) => item.key === groupKey);
  const boundaries = boundary.status === 'loaded' ? boundary.layer.geojson : null;
  const join = useMemo(() => joinAreaReferences(group?.references || [], boundaries, { objectType }), [group, boundaries, objectType]);
  const municipio = intelPoint && boundaries ? municipalityAt(boundaries, intelPoint.lon, intelPoint.lat) : null;
  const selected = shown.find((item) => item.id === selectedId) || null;

  function toggleCategory(name) {
    setHidden((previous) => {
      const next = new Set(previous);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  }

  function selectFeature(evidenceId, { focus = false } = {}) {
    const item = (data?.features || []).find((candidate) => candidate.id === evidenceId);
    if (!item) return;
    const [lon, lat] = item.geometry.coordinates;
    setSelectedId(evidenceId);
    setIntelPoint({ lon, lat });
    if (focus) setFocusPoint({ lon, lat });
  }

  function pickPoint(point) {
    setSelectedId(null);
    setIntelPoint(point);
  }

  function applyAoi(event) {
    event.preventDefault();
    if (!aoiText.trim()) {
      setAoi(null);
      setAoiError(null);
      return;
    }
    try {
      setAoi(parseBboxText(aoiText));
      setAoiError(null);
    } catch (error) {
      setAoiError(error.message);
    }
  }

  async function loadBoundary() {
    setBoundary({ status: 'loading', layer: null, error: null });
    try {
      setBoundary({ status: 'loaded', layer: await acquireOnlineSource(MUNICIPIO_BOUNDARY_SOURCE_ID), error: null });
    } catch (error) {
      setBoundary({ status: 'error', layer: null, error: error.message });
    }
  }

  const notDrawn = (data?.not_drawn || []).reduce((sum, item) => sum + item.count, 0);
  return (
    <div className="space-y-4" data-property-map>
      <div>
        <h2 className="text-lg font-semibold">Property Map</h2>
        <p className="text-sm text-muted-foreground">
          Hub-held records placed where their producer declared a point, styled by that precision. Nothing is geocoded;
          records without a declared point are counted, not drawn.
        </p>
      </div>
      {query.isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading mapped records…</p> : null}
      {query.isError ? (
        <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          The Hub could not return spatial features: {query.error?.message}
        </div>
      ) : null}
      {data ? (
        <p role="status" className="text-sm" data-property-map-summary>
          {data.matched} of {data.loaded} loaded records drawn · {notDrawn} not drawn · {data.excluded_synthetic} synthetic excluded
          {aoi ? ` · ${data.outside_bbox} outside the AOI` : ''}{data.truncated ? ` · showing the first ${data.features.length}` : ''}
        </p>
      ) : null}
      <section className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <section className={panel} aria-labelledby="pm-view">
            <h3 id="pm-view" className="font-semibold">View</h3>
            <label className="block text-xs font-medium" htmlFor="pm-basemap">Basemap</label>
            <select id="pm-basemap" className={cn(control, 'w-full')} value={basemapId} onChange={(event) => setBasemapId(event.target.value)}>
              {Object.entries(PROPERTY_MAP_BASEMAPS).map(([id, item]) => <option key={id} value={id}>{item.label}</option>)}
            </select>
            <button type="button" aria-pressed={includeSynthetic} className={cn(button, includeSynthetic && 'border-primary')} onClick={() => setIncludeSynthetic((value) => !value)}>
              {includeSynthetic ? 'Synthetic rows included' : 'Include synthetic rows'}
            </button>
            <form className="space-y-1" onSubmit={applyAoi}>
              <label className="block text-xs font-medium" htmlFor="pm-aoi">AOI (minLon,minLat,maxLon,maxLat)</label>
              <div className="flex gap-2">
                <input id="pm-aoi" className={cn(control, 'w-full')} value={aoiText} placeholder="-66.6,18.1,-66.3,18.3" onChange={(event) => setAoiText(event.target.value)} />
                <button type="submit" className={button}>Apply</button>
              </div>
              {aoiError ? <p role="alert" className="text-xs text-destructive">{aoiError}</p> : null}
              {aoi ? <p className="text-xs" data-aoi-area>AOI area {formatArea(bboxAreaM2(aoi))} (on the reference sphere)</p> : null}
            </form>
          </section>
          {data ? <UncertaintyLegend data={data} outlinedTotal={join.matchedTotal} /> : null}
          {data ? <CategoryLegend categories={data.categories} colors={colors} hidden={hidden} onToggle={toggleCategory} /> : null}
          {data ? (
            <AreaReferences
              data={data} boundary={boundary} onLoadBoundary={loadBoundary} groupKey={groupKey}
              onGroupChange={(key) => { setGroupChoice(key); setObjectType(null); }}
              objectType={objectType} onObjectTypeChange={setObjectType} join={join}
            />
          ) : null}
          <LayerProvenance data={data} basemap={basemap} boundary={boundary} />
        </aside>
        <div className="space-y-4">
          <div className="text-xs text-muted-foreground" data-map-origin>
            Map origin {origin.center[1].toFixed(4)}, {origin.center[0].toFixed(4)}
            {origin.bounds ? ' · fitted to Puerto Rico, Vieques and Culebra' : ` · zoom ${origin.zoom.toFixed(1)} from the map link`}
          </div>
          <div className="relative h-[560px] overflow-hidden rounded-xl border border-border bg-card">
            <Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading the map…</div>}>
              <PropertyMapCanvas
                key={basemapId}
                basemap={basemap} initialView={origin} features={shown} paint={paint}
                outline={boundaries ? join.outline : null} selectedId={selectedId}
                intelPoint={intelPoint} radiusM={radiusM} focusPoint={focusPoint}
                onSelectFeature={(id) => selectFeature(id)} onPickPoint={pickPoint}
              />
            </Suspense>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-4">
              <SelectedRecord feature={selected} />
              <LocationIntel
                point={intelPoint} radiusM={radiusM} onRadiusChange={setRadiusM}
                onSubmitPoint={(point) => { pickPoint(point); setFocusPoint(point); }}
                municipio={municipio} boundaryLoaded={Boolean(boundaries)} includeSynthetic={includeSynthetic}
              />
            </div>
            <section className={panel} aria-labelledby="pm-records" data-mapped-records>
              <h3 id="pm-records" className="font-semibold">Mapped records</h3>
              {data && shown.length === 0 ? <p className="text-xs text-muted-foreground">No mapped record matches these filters.</p> : null}
              <ul className="max-h-[520px] space-y-1 overflow-y-auto">
                {shown.slice(0, LIST_LIMIT).map((item) => {
                  const props = item.properties;
                  return (
                    <li key={item.id}>
                      <button
                        type="button" aria-pressed={item.id === selectedId} data-record-button={item.id}
                        className={cn('flex min-h-[44px] w-full items-center gap-2 rounded-md px-2 text-left text-xs hover:bg-muted', item.id === selectedId && 'bg-muted')}
                        onClick={() => selectFeature(item.id, { focus: true })}
                      >
                        <PrecisionMarker marker={precisionStyle(props.geometry_precision)?.marker} color={colors[props.category]} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">{props.title}</span>
                          <span className="block text-muted-foreground">
                            {props.category} · {precisionStyle(props.geometry_precision)?.label}
                            {props.municipality ? ` · ${props.municipality}` : ''}{props.synthetic ? ' · synthetic' : ''}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
              {shown.length > LIST_LIMIT ? <p className="text-xs text-muted-foreground">Showing {LIST_LIMIT} of {shown.length}; narrow by category or AOI.</p> : null}
            </section>
          </div>
        </div>
      </section>
    </div>
  );
}
