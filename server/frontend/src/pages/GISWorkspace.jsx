import React, { useMemo, useState } from 'react';
import { GeoJSON, MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Layers, Upload, ShieldCheck } from 'lucide-react';
import { ingestGeoJSONFile } from '@/gis/ingestGeoJSON';
import { createCanonicalMapState } from '@/gis/contracts';
import { GIS_RUNTIME_RESPONSIBILITIES } from '@/gis/sourceRegistry';

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

export default function GISWorkspace() {
  const [layer, setLayer] = useState(null);
  const [error, setError] = useState(null);
  const [basemapId, setBasemapId] = useState('cartoDark');
  const [mapState] = useState(INITIAL_STATE);
  const basemap = BASEMAPS[basemapId];

  const canonicalState = useMemo(() => createCanonicalMapState({
    ...mapState,
    activeLayerIds: layer ? [layer.manifest.layerId] : [],
    layerState: layer ? { [layer.manifest.layerId]: { visible: true, opacity: 1 } } : {},
    provenanceRefs: layer?.manifest.byteSha256 ? [`sha256:${layer.manifest.byteSha256}`] : [],
  }), [layer, mapState]);

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

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2"><Layers className="h-5 w-5" /><h1 className="text-xl font-semibold">Federation GIS Workspace</h1></div>
          <p className="mt-1 text-sm text-muted-foreground">Canonical-state vertical slice: RAW GeoJSON upload → validation + SHA-256 → layer manifest → map visualization.</p>
        </div>
        <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs">
          <div className="flex items-center gap-1.5 font-medium"><ShieldCheck className="h-3.5 w-3.5" />Renderer state</div>
          <div className="mt-1 text-muted-foreground">2D: {GIS_RUNTIME_RESPONSIBILITIES.leaflet.status} · MapLibre target · Cesium 3D target</div>
        </div>
      </header>

      <section className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="space-y-4 rounded-xl border border-border bg-card p-4">
          <div>
            <label className="text-xs font-medium" htmlFor="gis-basemap">Basemap</label>
            <select id="gis-basemap" className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-sm" value={basemapId} onChange={(event) => setBasemapId(event.target.value)}>
              {Object.entries(BASEMAPS).map(([id, item]) => <option key={id} value={id}>{item.label}</option>)}
            </select>
          </div>

          <div>
            <div className="text-xs font-medium">Layer upload</div>
            <label className="mt-1 flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-border px-3 py-2 text-sm hover:bg-muted/50">
              <Upload className="h-4 w-4" /> Upload GeoJSON
              <input className="sr-only" type="file" accept=".geojson,.json,application/geo+json,application/json" onChange={onUpload} />
            </label>
            <p className="mt-1.5 text-[11px] text-muted-foreground">This first slice accepts FeatureCollection GeoJSON only. Other formats remain contract-defined, not falsely marked implemented.</p>
          </div>

          {error ? <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">{error}</div> : null}

          <div className="space-y-1 border-t border-border pt-3 text-xs">
            <div className="font-medium">Canonical state</div>
            <div className="text-muted-foreground">Mode: {canonicalState.mode}</div>
            <div className="text-muted-foreground">CRS: {canonicalState.displayCrs}</div>
            <div className="text-muted-foreground">Active layers: {canonicalState.activeLayerIds.length}</div>
          </div>

          {layer ? (
            <div className="space-y-1 border-t border-border pt-3 text-xs">
              <div className="font-medium break-words">{layer.manifest.titleRaw}</div>
              <div className="text-muted-foreground">Features: {layer.manifest.featureCount}</div>
              <div className="text-muted-foreground">Geometry: {layer.manifest.geometryTypes.join(', ') || 'NULL/empty'}</div>
              <div className="text-muted-foreground">Z: {String(layer.manifest.preservesZ)} · M: {String(layer.manifest.preservesM)}</div>
              <div className="text-muted-foreground">Validation: {layer.manifest.validationStatus}</div>
              <div className="break-all font-mono text-[10px] text-muted-foreground">SHA256 {layer.manifest.byteSha256 || 'UNAVAILABLE'}</div>
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
