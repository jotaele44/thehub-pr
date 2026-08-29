import React, { useMemo, useState } from 'react';
import { GeoJSON, MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Database, HardDrive, Layers, RefreshCw, ShieldCheck, Upload } from 'lucide-react';
import { ingestGeoJSONFile } from '@/gis/ingestGeoJSON';
import { acquireOnlineSource } from '@/gis/remoteAcquisition';
import { createCanonicalMapState } from '@/gis/contracts';
import {
  GEOSPATIAL_PROVIDERS,
  GIS_RUNTIME_RESPONSIBILITIES,
  ONLINE_SOURCE_CATALOG,
  listOnlineSourceDefinitions,
} from '@/gis/sourceRegistry';

const BASEMAPS = Object.freeze({
  cartoDark: {
    label: 'CARTO Dark',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; OpenStreetMap, &copy; CARTO',
  },
  osm: {
    label: 'OpenStreetMap',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors',
  },
});

const INITIAL_STATE = createCanonicalMapState({
  mode: '2d',
  view: { center: { lon: -66.4, lat: 18.22 }, groundResolutionM: 1000, bearing: 0, requestedPitch: 0 },
});

const DEFAULT_PROVIDER_ID = 'pr-sige';
const DEFAULT_SOURCE_ID = 'pr-sige-municipios';

function statusLabel(source) {
  if (source.runtimeStatus === 'IMPLEMENTED') return 'Implemented · provider runtime provisional';
  return `Registry only · ${source.runtimeStatus}`;
}

export default function GISWorkspace() {
  const [layer, setLayer] = useState(null);
  const [error, setError] = useState(null);
  const [basemapId, setBasemapId] = useState('cartoDark');
  const [mapState] = useState(INITIAL_STATE);
  const [acquisitionMode, setAcquisitionMode] = useState('device');
  const [onlineProviderId, setOnlineProviderId] = useState(DEFAULT_PROVIDER_ID);
  const [onlineSourceId, setOnlineSourceId] = useState(DEFAULT_SOURCE_ID);
  const [fetching, setFetching] = useState(false);
  const basemap = BASEMAPS[basemapId];

  const providerSources = useMemo(() => listOnlineSourceDefinitions(onlineProviderId), [onlineProviderId]);
  const selectedOnlineSource = ONLINE_SOURCE_CATALOG.find((item) => item.sourceId === onlineSourceId) || providerSources[0] || null;

  const canonicalState = useMemo(() => {
    const provenanceRefs = [];
    if (layer?.manifest?.byteSha256) provenanceRefs.push(`layer-sha256:${layer.manifest.byteSha256}`);
    if (layer?.snapshotSha256) provenanceRefs.push(`source-snapshot-sha256:${layer.snapshotSha256}`);
    if (layer?.queryReceiptSha256) provenanceRefs.push(`query-receipt-sha256:${layer.queryReceiptSha256}`);
    return createCanonicalMapState({
      ...mapState,
      activeLayerIds: layer ? [layer.manifest.layerId] : [],
      layerState: layer ? { [layer.manifest.layerId]: { visible: true, opacity: 1 } } : {},
      provenanceRefs,
    });
  }, [layer, mapState]);

  async function onUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    try {
      setLayer(await ingestGeoJSONFile(file));
    } catch (ingestError) {
      setLayer(null);
      setError(ingestError.message);
    } finally {
      event.target.value = '';
    }
  }

  function onProviderChange(event) {
    const nextProviderId = event.target.value;
    const nextSources = listOnlineSourceDefinitions(nextProviderId);
    setOnlineProviderId(nextProviderId);
    setOnlineSourceId(nextSources[0]?.sourceId || '');
  }

  async function onFetchOnline() {
    if (!selectedOnlineSource) return;
    setFetching(true);
    setError(null);
    try {
      setLayer(await acquireOnlineSource(selectedOnlineSource.sourceId));
    } catch (fetchError) {
      setLayer(null);
      setError(fetchError.message);
    } finally {
      setFetching(false);
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2"><Layers className="h-5 w-5" /><h1 className="text-xl font-semibold">Federation GIS Workspace</h1></div>
          <p className="mt-1 text-sm text-muted-foreground">Unified acquisition: device RAW or authoritative online source → integrity/provenance gates → canonical layer → map.</p>
        </div>
        <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs">
          <div className="flex items-center gap-1.5 font-medium"><ShieldCheck className="h-3.5 w-3.5" />Renderer state</div>
          <div className="mt-1 text-muted-foreground">2D: {GIS_RUNTIME_RESPONSIBILITIES.leaflet.status} · MapLibre target · Cesium 3D target</div>
        </div>
      </header>

      <section className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="space-y-4 rounded-xl border border-border bg-card p-4">
          <div>
            <label className="text-xs font-medium" htmlFor="gis-basemap">Basemap</label>
            <select id="gis-basemap" className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-sm" value={basemapId} onChange={(event) => setBasemapId(event.target.value)}>
              {Object.entries(BASEMAPS).map(([id, item]) => <option key={id} value={id}>{item.label}</option>)}
            </select>
          </div>

          <div>
            <div className="text-xs font-medium">Add data</div>
            <div className="mt-1 grid grid-cols-2 gap-1 rounded-md border border-border bg-muted/30 p-1">
              <button type="button" className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-xs ${acquisitionMode === 'device' ? 'bg-background font-medium shadow-sm' : 'text-muted-foreground'}`} onClick={() => setAcquisitionMode('device')}>
                <HardDrive className="h-3.5 w-3.5" /> Device
              </button>
              <button type="button" className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-xs ${acquisitionMode === 'online' ? 'bg-background font-medium shadow-sm' : 'text-muted-foreground'}`} onClick={() => setAcquisitionMode('online')}>
                <Database className="h-3.5 w-3.5" /> Online
              </button>
            </div>
          </div>

          {acquisitionMode === 'device' ? (
            <div>
              <label className="flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-border px-3 py-2 text-sm hover:bg-muted/50">
                <Upload className="h-4 w-4" /> Choose GeoJSON from device
                <input className="sr-only" type="file" accept=".geojson,.json,application/geo+json,application/json" onChange={onUpload} />
              </label>
              <p className="mt-1.5 text-[11px] text-muted-foreground">Device path is bounded to FeatureCollection GeoJSON. RAW text is preserved before canonicalization.</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium" htmlFor="gis-provider">Provider</label>
                <select id="gis-provider" className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-sm" value={onlineProviderId} onChange={onProviderChange}>
                  {GEOSPATIAL_PROVIDERS.map((provider) => <option key={provider.providerId} value={provider.providerId}>{provider.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium" htmlFor="gis-online-source">Dataset / catalog</label>
                <select id="gis-online-source" className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-sm" value={selectedOnlineSource?.sourceId || ''} onChange={(event) => setOnlineSourceId(event.target.value)}>
                  {providerSources.map((source) => <option key={source.sourceId} value={source.sourceId}>{source.label}</option>)}
                </select>
              </div>
              {selectedOnlineSource ? (
                <div className="rounded-md border border-border bg-muted/20 p-2 text-[11px] text-muted-foreground">
                  <div>{statusLabel(selectedOnlineSource)}</div>
                  <div className="mt-1 break-all font-mono text-[10px]">{selectedOnlineSource.endpoint}</div>
                </div>
              ) : null}
              <button type="button" className="flex min-h-10 w-full items-center justify-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50" disabled={!selectedOnlineSource || selectedOnlineSource.runtimeStatus !== 'IMPLEMENTED' || fetching} onClick={onFetchOnline}>
                <RefreshCw className={`h-4 w-4 ${fetching ? 'animate-spin' : ''}`} /> {fetching ? 'Fetching + validating…' : 'Fetch and add layer'}
              </button>
              <p className="text-[11px] text-muted-foreground">Only provider paths with an implemented protocol adapter are executable. Registry-only STAC/WFS/raster entries remain visible but disabled rather than being falsely certified.</p>
            </div>
          )}

          {error ? <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">{error}</div> : null}

          <div className="space-y-1 border-t border-border pt-3 text-xs">
            <div className="font-medium">Canonical state</div>
            <div className="text-muted-foreground">Mode: {canonicalState.mode}</div>
            <div className="text-muted-foreground">CRS: {canonicalState.displayCrs}</div>
            <div className="text-muted-foreground">Active layers: {canonicalState.activeLayerIds.length}</div>
            <div className="text-muted-foreground">Provenance refs: {canonicalState.provenanceRefs.length}</div>
          </div>

          {layer ? (
            <div className="space-y-1 border-t border-border pt-3 text-xs">
              <div className="font-medium break-words">{layer.manifest.titleRaw}</div>
              <div className="text-muted-foreground">Acquisition: {layer.acquisitionMethod || 'device'}</div>
              <div className="text-muted-foreground">Features: {layer.manifest.featureCount}</div>
              <div className="text-muted-foreground">Geometry: {layer.manifest.geometryTypes.join(', ') || 'NULL/empty'}</div>
              <div className="text-muted-foreground">Z: {String(layer.manifest.preservesZ)} · M: {String(layer.manifest.preservesM)}</div>
              <div className="text-muted-foreground">Validation: {layer.manifest.validationStatus}</div>
              {layer.certification ? <div className="text-muted-foreground">Bounded gates: {layer.certification.status} · provider runtime {layer.certification.providerRuntimeCertification}</div> : null}
              {layer.sourceManifest ? <div className="text-muted-foreground">Identity: {layer.sourceManifest.canonicalIdentityStatus}</div> : null}
              <div className="break-all font-mono text-[10px] text-muted-foreground">Layer SHA256 {layer.manifest.byteSha256 || 'UNAVAILABLE'}</div>
              {layer.snapshotSha256 ? <div className="break-all font-mono text-[10px] text-muted-foreground">Source snapshot SHA256 {layer.snapshotSha256}</div> : null}
              {layer.queryReceiptSha256 ? <div className="break-all font-mono text-[10px] text-muted-foreground">Query receipt SHA256 {layer.queryReceiptSha256}</div> : null}
            </div>
          ) : null}
        </aside>

        <div className="h-[640px] overflow-hidden rounded-xl border border-border bg-card">
          <MapContainer center={[canonicalState.view.center.lat, canonicalState.view.center.lon]} zoom={9} style={{ height: '100%', width: '100%' }} scrollWheelZoom>
            <TileLayer key={basemapId} url={basemap.url} attribution={basemap.attribution} />
            {layer ? <GeoJSON key={layer.manifest.layerId} data={layer.geojson} /> : null}
          </MapContainer>
        </div>
      </section>
    </div>
  );
}
