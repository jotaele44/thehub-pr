import React, { useMemo, useState } from 'react';
import { Database, Globe2, HardDrive, Image as ImageIcon, Layers, Map as MapIcon, RefreshCw, ShieldCheck, Upload } from 'lucide-react';
import { ingestGeoJSONFile } from '@/gis/ingestGeoJSON';
import { acquireOnlineSource, acquireRasterAsset } from '@/gis/acquisitionFacade';
import { compareRendererEquivalence, createCanonicalMapState, switchRenderMode } from '@/gis/contracts';
import { buildRasterPreview } from '@/gis/rasterPreview';
import RendererSurface from '@/gis/renderers/RendererSurface';
import { GEOSPATIAL_PROVIDERS, GIS_RUNTIME_RESPONSIBILITIES, ONLINE_SOURCE_CATALOG, listOnlineSourceDefinitions, preferredOnlineSourceDefinition } from '@/gis/sourceRegistry';

const BASEMAPS = Object.freeze({
  cartoDark: { label: 'CARTO Dark', url: 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png', attribution: '&copy; OpenStreetMap, &copy; CARTO' },
  osm: { label: 'OpenStreetMap', url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '&copy; OpenStreetMap contributors' },
});
const INITIAL_STATE = createCanonicalMapState({ mode: '2d', view: { center: { lon: -66.4, lat: 18.22 }, groundResolutionM: 1000, bearing: 0, requestedPitch: 0 } });
const DEFAULT_PROVIDER_ID = 'pr-sige';
const DEFAULT_SOURCE_ID = 'pr-sige-municipios';

function statusLabel(source) {
  if (source.runtimeStatus === 'IMPLEMENTED') return `Implemented · ${source.certification}`;
  if (source.runtimeStatus.startsWith('SUPERSEDED')) return `Superseded · ${source.runtimeStatus}`;
  return `Registry only · ${source.runtimeStatus}`;
}

function firstRasterAsset(candidate) {
  const entries = Object.entries(candidate.assets || {});
  return entries.find(([, asset]) => asset?.href && (/tiff?/i.test(asset.type || '') || /\.tiff?(?:$|\?)/i.test(asset.href))) || entries.find(([, asset]) => asset?.href) || null;
}

export default function GISWorkspace() {
  const [layer, setLayer] = useState(null);
  const [discovery, setDiscovery] = useState(null);
  const [error, setError] = useState(null);
  const [renderNotice, setRenderNotice] = useState(null);
  const [rasterPreview, setRasterPreview] = useState(null);
  const [basemapId, setBasemapId] = useState('cartoDark');
  const [mapState, setMapState] = useState(INITIAL_STATE);
  const [lastEquivalence, setLastEquivalence] = useState(null);
  const [acquisitionMode, setAcquisitionMode] = useState('device');
  const [onlineProviderId, setOnlineProviderId] = useState(DEFAULT_PROVIDER_ID);
  const [onlineSourceId, setOnlineSourceId] = useState(DEFAULT_SOURCE_ID);
  const [fetching, setFetching] = useState(false);
  const [bboxText, setBboxText] = useState('-67.4,17.8,-65.2,18.6');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const basemap = BASEMAPS[basemapId];
  const providerSources = useMemo(() => listOnlineSourceDefinitions(onlineProviderId), [onlineProviderId]);
  const selectedOnlineSource = ONLINE_SOURCE_CATALOG.find((item) => item.sourceId === onlineSourceId) || preferredOnlineSourceDefinition(onlineProviderId);

  const canonicalState = useMemo(() => {
    const provenanceRefs = [];
    if (layer?.manifest?.byteSha256) provenanceRefs.push(`layer-sha256:${layer.manifest.byteSha256}`);
    if (layer?.snapshotSha256) provenanceRefs.push(`source-snapshot-sha256:${layer.snapshotSha256}`);
    if (layer?.queryReceiptSha256) provenanceRefs.push(`query-receipt-sha256:${layer.queryReceiptSha256}`);
    if (discovery?.snapshotSha256) provenanceRefs.push(`discovery-snapshot-sha256:${discovery.snapshotSha256}`);
    const rendered = Boolean(layer?.geojson || rasterPreview);
    const activeLayerIds = rendered && layer?.manifest?.layerId ? [layer.manifest.layerId] : [];
    return createCanonicalMapState({
      ...mapState,
      activeLayerIds,
      layerState: rendered ? { [layer.manifest.layerId]: { visible: true, opacity: rasterPreview ? 0.72 : 1 } } : {},
      provenanceRefs,
    });
  }, [layer, discovery, rasterPreview, mapState]);

  function clearRenderedData() {
    setLayer(null);
    setRasterPreview(null);
    setRenderNotice(null);
  }

  async function onUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    setDiscovery(null);
    setRasterPreview(null);
    setRenderNotice(null);
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
    const preferredSource = nextSources.find((item) => item.runtimeStatus === 'IMPLEMENTED') || nextSources[0] || null;
    setOnlineProviderId(nextProviderId);
    setOnlineSourceId(preferredSource?.sourceId || '');
    setDiscovery(null);
  }

  function parsedBbox() {
    const values = bboxText.split(',').map((value) => Number(value.trim()));
    if (values.length !== 4 || values.some((value) => !Number.isFinite(value)) || values[0] >= values[2] || values[1] >= values[3]) throw new Error('AOI bbox requires minLon,minLat,maxLon,maxLat');
    return values;
  }

  async function onFetchOnline() {
    if (!selectedOnlineSource) return;
    setFetching(true);
    setError(null);
    clearRenderedData();
    setDiscovery(null);
    try {
      const options = selectedOnlineSource.protocol.includes('stac') ? { bbox: parsedBbox(), start: startDate || null, end: endDate || null } : {};
      const result = await acquireOnlineSource(selectedOnlineSource.sourceId, options);
      if (result.candidates) setDiscovery(result); else setLayer(result);
    } catch (fetchError) {
      setError(fetchError.message);
    } finally {
      setFetching(false);
    }
  }

  async function onAcquireAsset(candidate) {
    const pair = firstRasterAsset(candidate);
    if (!pair || !selectedOnlineSource) return;
    setFetching(true);
    setError(null);
    setRasterPreview(null);
    setRenderNotice(null);
    try {
      const [assetKey] = pair;
      const acquired = await acquireRasterAsset(selectedOnlineSource.sourceId, candidate, assetKey);
      setLayer(acquired);
      try {
        const preview = await buildRasterPreview(acquired);
        setRasterPreview(preview);
        setRenderNotice(`Raster preview rendered · ${preview.alignmentStatus}`);
      } catch (previewError) {
        setRenderNotice(`Raster acquisition preserved; preview OPEN: ${previewError.message}`);
      }
    } catch (fetchError) {
      setError(fetchError.message);
    } finally {
      setFetching(false);
    }
  }

  function onRendererViewChange(view) {
    setMapState((previous) => createCanonicalMapState({
      ...previous,
      view: { ...previous.view, ...view },
    }));
  }

  function switchMode(nextMode) {
    if (nextMode === canonicalState.mode) return;
    const next = switchRenderMode(canonicalState, nextMode);
    const report = compareRendererEquivalence(canonicalState, next);
    setLastEquivalence(report);
    if (report.status !== 'PASS') {
      setError(`Renderer switch blocked: ${report.failures.join(', ')}`);
      return;
    }
    setError(null);
    setMapState(next);
  }

  const sourceIsDiscovery = selectedOnlineSource && ['stac', 'static-stac-item-collection'].includes(selectedOnlineSource.protocol);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2"><Layers className="h-5 w-5" /><h1 className="text-xl font-semibold">Federation GIS Workspace</h1></div>
          <p className="mt-1 text-sm text-muted-foreground">Device or authoritative online acquisition → RAW/query/snapshot provenance → renderer-independent canonical state.</p>
        </div>
        <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs">
          <div className="flex items-center gap-1.5 font-medium"><ShieldCheck className="h-3.5 w-3.5" />Renderer state</div>
          <div className="mt-1 text-muted-foreground">MapLibre: {GIS_RUNTIME_RESPONSIBILITIES.maplibre.status} · Cesium: {GIS_RUNTIME_RESPONSIBILITIES.cesium.status}</div>
        </div>
      </header>

      <section className="grid gap-4 xl:grid-cols-[390px_minmax(0,1fr)]">
        <aside className="space-y-4 rounded-xl border border-border bg-card p-4">
          <div>
            <div className="text-xs font-medium">View</div>
            <div className="mt-1 grid grid-cols-2 gap-1 rounded-md border border-border bg-muted/30 p-1">
              <button type="button" className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-xs ${canonicalState.mode === '2d' ? 'bg-background font-medium shadow-sm' : 'text-muted-foreground'}`} onClick={() => switchMode('2d')}><MapIcon className="h-3.5 w-3.5" />2D MapLibre</button>
              <button type="button" className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-xs ${canonicalState.mode === '3d' ? 'bg-background font-medium shadow-sm' : 'text-muted-foreground'}`} onClick={() => switchMode('3d')}><Globe2 className="h-3.5 w-3.5" />3D Cesium</button>
            </div>
            {lastEquivalence ? <div className="mt-1 text-[11px] text-muted-foreground">Last 2D↔3D gate: {lastEquivalence.status} · pixel equivalence not claimed</div> : null}
          </div>

          <div><label className="text-xs font-medium" htmlFor="gis-basemap">Basemap</label><select id="gis-basemap" className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-sm" value={basemapId} onChange={(event) => setBasemapId(event.target.value)}>{Object.entries(BASEMAPS).map(([id, item]) => <option key={id} value={id}>{item.label}</option>)}</select></div>

          <div><div className="text-xs font-medium">Add data</div><div className="mt-1 grid grid-cols-2 gap-1 rounded-md border border-border bg-muted/30 p-1">
            <button type="button" className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-xs ${acquisitionMode === 'device' ? 'bg-background font-medium shadow-sm' : 'text-muted-foreground'}`} onClick={() => setAcquisitionMode('device')}><HardDrive className="h-3.5 w-3.5" /> Device</button>
            <button type="button" className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-xs ${acquisitionMode === 'online' ? 'bg-background font-medium shadow-sm' : 'text-muted-foreground'}`} onClick={() => setAcquisitionMode('online')}><Database className="h-3.5 w-3.5" /> Online</button>
          </div></div>

          {acquisitionMode === 'device' ? (
            <div><label className="flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-border px-3 py-2 text-sm hover:bg-muted/50"><Upload className="h-4 w-4" /> Choose GeoJSON from device<input className="sr-only" type="file" accept=".geojson,.json,application/geo+json,application/json" onChange={onUpload} /></label><p className="mt-1.5 text-[11px] text-muted-foreground">FeatureCollection GeoJSON only; RAW text remains preserved before canonicalization.</p></div>
          ) : (
            <div className="space-y-3">
              <div><label className="text-xs font-medium" htmlFor="gis-provider">Provider</label><select id="gis-provider" className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-sm" value={onlineProviderId} onChange={onProviderChange}>{GEOSPATIAL_PROVIDERS.map((provider) => <option key={provider.providerId} value={provider.providerId}>{provider.label}</option>)}</select></div>
              <div><label className="text-xs font-medium" htmlFor="gis-online-source">Dataset / collection</label><select id="gis-online-source" className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-sm" value={selectedOnlineSource?.sourceId || ''} onChange={(event) => { setOnlineSourceId(event.target.value); setDiscovery(null); }}>{providerSources.map((source) => <option key={source.sourceId} value={source.sourceId}>{source.label}</option>)}</select></div>
              {sourceIsDiscovery ? <div className="space-y-2 rounded-md border border-border p-2"><label className="block text-[11px] font-medium" htmlFor="gis-bbox">AOI bbox · WGS84</label><input id="gis-bbox" value={bboxText} onChange={(event) => setBboxText(event.target.value)} className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-[11px]"/><div className="grid grid-cols-2 gap-2"><input aria-label="Start date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className="rounded border border-border bg-background px-2 py-1 text-xs"/><input aria-label="End date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className="rounded border border-border bg-background px-2 py-1 text-xs"/></div></div> : null}
              {selectedOnlineSource ? <div className="rounded-md border border-border bg-muted/20 p-2 text-[11px] text-muted-foreground"><div>{statusLabel(selectedOnlineSource)}</div><div>Transport: {selectedOnlineSource.transport}</div><div className="mt-1 break-all font-mono text-[10px]">{selectedOnlineSource.endpoint}</div></div> : null}
              <button type="button" className="flex min-h-10 w-full items-center justify-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50" disabled={!selectedOnlineSource || selectedOnlineSource.runtimeStatus !== 'IMPLEMENTED' || fetching} onClick={onFetchOnline}><RefreshCw className={`h-4 w-4 ${fetching ? 'animate-spin' : ''}`} /> {fetching ? 'Fetching + validating…' : sourceIsDiscovery ? 'Discover imagery' : 'Fetch and add layer'}</button>
            </div>
          )}

          {error ? <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">{error}</div> : null}
          {renderNotice ? <div className="rounded-md border border-border bg-muted/20 p-2 text-[11px] text-muted-foreground">{renderNotice}</div> : null}

          <div className="space-y-1 border-t border-border pt-3 text-xs"><div className="font-medium">Canonical state</div><div className="text-muted-foreground">Mode: {canonicalState.mode}</div><div className="text-muted-foreground">CRS: {canonicalState.displayCrs}</div><div className="text-muted-foreground">Ground resolution: {canonicalState.view.groundResolutionM.toFixed(2)} m/px</div><div className="text-muted-foreground">Active rendered layers: {canonicalState.activeLayerIds.length}</div><div className="text-muted-foreground">Provenance refs: {canonicalState.provenanceRefs.length}</div></div>

          {discovery ? <div className="space-y-2 border-t border-border pt-3 text-xs"><div className="font-medium">Imagery candidates: {discovery.candidates.length}</div><div className="text-muted-foreground">Discovery gates: {discovery.certification.status}</div><div className="break-all font-mono text-[10px] text-muted-foreground">Snapshot {discovery.snapshotSha256}</div>{discovery.candidates.slice(0, 12).map((candidate) => { const asset = firstRasterAsset(candidate); return <div key={candidate.itemId} className="rounded border border-border p-2"><div className="break-words font-medium">{candidate.itemId}</div><div className="text-muted-foreground">{candidate.datetime || 'datetime unavailable'}</div><div className="text-muted-foreground">Assets: {Object.keys(candidate.assets || {}).length}</div>{asset ? <button type="button" className="mt-1 flex items-center gap-1 rounded border border-border px-2 py-1 text-[11px]" disabled={fetching} onClick={() => onAcquireAsset(candidate)}><ImageIcon className="h-3 w-3"/>Acquire + preview {asset[0]}</button> : null}</div>; })}{discovery.candidates.length > 12 ? <div className="text-muted-foreground">Showing first 12 candidates; full candidate set remains in acquisition state.</div> : null}</div> : null}

          {layer ? <div className="space-y-1 border-t border-border pt-3 text-xs"><div className="font-medium break-words">{layer.manifest.titleRaw}</div><div className="text-muted-foreground">Acquisition: {layer.acquisitionMethod || 'device'}</div>{layer.manifest.featureCount !== null ? <div className="text-muted-foreground">Features: {layer.manifest.featureCount}</div> : null}<div className="text-muted-foreground">Format: {layer.manifest.rawFormat}</div><div className="text-muted-foreground">Validation: {layer.manifest.validationStatus}</div>{layer.assetClassification ? <div className="text-muted-foreground">Raster classification: {layer.assetClassification}</div> : null}{rasterPreview ? <div className="text-muted-foreground">Raster alignment: {rasterPreview.alignmentStatus}</div> : null}{layer.certification ? <div className="text-muted-foreground">Bounded gates: {layer.certification.status}{layer.certification.residue ? ` · residue ${layer.certification.residue}` : ''}</div> : null}{layer.sourceManifest ? <div className="text-muted-foreground">Identity: {layer.sourceManifest.canonicalIdentityStatus}</div> : null}<div className="break-all font-mono text-[10px] text-muted-foreground">Layer SHA256 {layer.manifest.byteSha256 || 'NOT FULLY HASHED'}</div>{layer.snapshotSha256 ? <div className="break-all font-mono text-[10px] text-muted-foreground">Snapshot/range SHA256 {layer.snapshotSha256}</div> : null}{layer.queryReceiptSha256 ? <div className="break-all font-mono text-[10px] text-muted-foreground">Query receipt SHA256 {layer.queryReceiptSha256}</div> : null}</div> : null}
        </aside>

        <div className="relative h-[640px] overflow-hidden rounded-xl border border-border bg-card">
          <RendererSurface canonicalState={canonicalState} layer={layer} basemap={basemap} rasterPreview={rasterPreview} onCanonicalViewChange={onRendererViewChange} />
          {rasterPreview ? <div className="pointer-events-none absolute bottom-3 left-3 max-w-[70%] rounded bg-background/90 px-2 py-1 text-[10px] text-muted-foreground">Raster visualization is a bounded STAC-footprint rectification preview; full-file byte identity and pixel-level reprojection remain OPEN.</div> : null}
        </div>
      </section>
    </div>
  );
}
