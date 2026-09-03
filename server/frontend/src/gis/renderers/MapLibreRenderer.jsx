import React, { useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { canonicalViewToMapLibre, mapLibreViewToCanonical } from '../rendererView';

const VECTOR_SOURCE_ID = 'canonical-vector-layer';
const VECTOR_LAYER_IDS = Object.freeze([
  'canonical-vector-fill',
  'canonical-vector-line',
  'canonical-vector-points',
]);

function baseStyle(basemap) {
  return {
    version: 8,
    sources: {
      basemap: {
        type: 'raster',
        tiles: [basemap.url],
        tileSize: 256,
        attribution: basemap.attribution || '',
      },
    },
    layers: [{ id: 'basemap', type: 'raster', source: 'basemap' }],
  };
}

function addGeoJsonLayer(map, geojson) {
  if (!geojson) return;
  if (map.getSource(VECTOR_SOURCE_ID)) {
    map.getSource(VECTOR_SOURCE_ID).setData(geojson);
    return;
  }
  map.addSource(VECTOR_SOURCE_ID, { type: 'geojson', data: geojson, generateId: true });
  map.addLayer({
    id: VECTOR_LAYER_IDS[0],
    type: 'fill',
    source: VECTOR_SOURCE_ID,
    filter: ['==', ['geometry-type'], 'Polygon'],
    paint: { 'fill-opacity': 0.28, 'fill-outline-color': '#e5e7eb' },
  });
  map.addLayer({
    id: VECTOR_LAYER_IDS[1],
    type: 'line',
    source: VECTOR_SOURCE_ID,
    filter: ['in', ['geometry-type'], ['literal', ['LineString', 'Polygon']]],
    paint: { 'line-width': 2 },
  });
  map.addLayer({
    id: VECTOR_LAYER_IDS[2],
    type: 'circle',
    source: VECTOR_SOURCE_ID,
    filter: ['==', ['geometry-type'], 'Point'],
    paint: { 'circle-radius': 5, 'circle-stroke-width': 1 },
  });
}

function mapView(map) {
  const center = map.getCenter();
  return mapLibreViewToCanonical({
    center: [center.lng, center.lat],
    zoom: map.getZoom(),
    bearing: map.getBearing(),
    pitch: map.getPitch(),
  });
}

export default function MapLibreRenderer({
  canonicalState,
  layer,
  basemap,
  rasterPreview = null,
  onCanonicalViewChange,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const applyingCanonicalRef = useRef(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;
    const view = canonicalViewToMapLibre(canonicalState.view);
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: baseStyle(basemap),
      center: view.center,
      zoom: view.zoom,
      bearing: view.bearing,
      pitch: view.pitch,
      attributionControl: true,
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    const publishView = () => {
      if (applyingCanonicalRef.current || !onCanonicalViewChange) return;
      onCanonicalViewChange(mapView(map), 'maplibre');
    };
    map.on('moveend', publishView);
    map.on('load', () => addGeoJsonLayer(map, layer?.geojson || null));
    mapRef.current = map;
    return () => {
      map.off('moveend', publishView);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const view = canonicalViewToMapLibre(canonicalState.view);
    applyingCanonicalRef.current = true;
    map.jumpTo({ center: view.center, zoom: view.zoom, bearing: view.bearing, pitch: view.pitch });
    queueMicrotask(() => { applyingCanonicalRef.current = false; });
  }, [canonicalState.view.center.lon, canonicalState.view.center.lat, canonicalState.view.groundResolutionM, canonicalState.view.bearing, canonicalState.view.requestedPitch]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => addGeoJsonLayer(map, layer?.geojson || null);
    if (map.isStyleLoaded()) apply(); else map.once('load', apply);
  }, [layer?.manifest?.layerId, layer?.geojson]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.setStyle(baseStyle(basemap));
    map.once('style.load', () => addGeoJsonLayer(map, layer?.geojson || null));
  }, [basemap.url]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const sourceId = 'canonical-raster-preview';
    const layerId = 'canonical-raster-preview';
    if (map.getLayer(layerId)) map.removeLayer(layerId);
    if (map.getSource(sourceId)) map.removeSource(sourceId);
    if (!rasterPreview?.imageUrl || !rasterPreview?.coordinates) return;
    map.addSource(sourceId, {
      type: 'image',
      url: rasterPreview.imageUrl,
      coordinates: rasterPreview.coordinates,
    });
    map.addLayer({ id: layerId, type: 'raster', source: sourceId, paint: { 'raster-opacity': 0.72 } });
  }, [rasterPreview]);

  return <div ref={containerRef} data-testid="maplibre-renderer" className="h-full w-full" />;
}
