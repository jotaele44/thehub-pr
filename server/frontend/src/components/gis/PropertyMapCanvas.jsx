import React, { useEffect, useRef, useState } from 'react';
import { maplibregl } from '@/gis/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { circlePolygon, featureCollection } from '@/gis/propertyMap';

// MapLibre surface for the Property Map. It only draws what it is given: Hub
// points styled by declared precision, municipio outlines for area references
// (dashed, never a point) and the Location Intel radius. Clicking a point
// selects it; clicking elsewhere picks a location for Location Intel.
const FEATURES = 'pm-features';
const SELECTED = 'pm-selected';
const OUTLINE = 'pm-area-references';
const INTEL = 'pm-intel';

function rasterSource(basemap) {
  return { type: 'raster', tiles: [basemap.url], tileSize: 256, attribution: basemap.attribution || '' };
}

// An imagery basemap with a coverage floor is drawn over its underlay, so the
// map is never blank where the imagery has no tiles.
function baseStyle(basemap) {
  const sources = { basemap: rasterSource(basemap) };
  const layers = [{ id: 'basemap', type: 'raster', source: 'basemap', ...(basemap.minzoom ? { minzoom: basemap.minzoom } : {}) }];
  if (basemap.underlay) {
    sources.underlay = rasterSource(basemap.underlay);
    layers.unshift({ id: 'underlay', type: 'raster', source: 'underlay' });
  }
  return { version: 8, sources, layers };
}

function intelData(point, radiusM) {
  if (!point) return featureCollection([]);
  return featureCollection([
    circlePolygon(point.lon, point.lat, radiusM),
    { type: 'Feature', geometry: { type: 'Point', coordinates: [point.lon, point.lat] }, properties: {} },
  ]);
}

function addLayers(map) {
  const empty = featureCollection([]);
  map.addSource(OUTLINE, { type: 'geojson', data: empty });
  map.addLayer({ id: `${OUTLINE}-fill`, type: 'fill', source: OUTLINE, paint: { 'fill-color': '#a78bfa', 'fill-opacity': 0.18 } });
  map.addLayer({
    id: `${OUTLINE}-line`, type: 'line', source: OUTLINE,
    paint: { 'line-color': '#a78bfa', 'line-width': 2, 'line-dasharray': [3, 2] },
  });
  map.addSource(INTEL, { type: 'geojson', data: empty });
  map.addLayer({
    id: `${INTEL}-radius`, type: 'line', source: INTEL, filter: ['==', ['geometry-type'], 'Polygon'],
    paint: { 'line-color': '#f8fafc', 'line-width': 1.5, 'line-dasharray': [2, 2] },
  });
  map.addLayer({
    id: `${INTEL}-point`, type: 'circle', source: INTEL, filter: ['==', ['geometry-type'], 'Point'],
    paint: { 'circle-radius': 4, 'circle-color': '#f8fafc', 'circle-stroke-color': '#0f172a', 'circle-stroke-width': 2 },
  });
  map.addSource(FEATURES, { type: 'geojson', data: empty });
  map.addLayer({ id: FEATURES, type: 'circle', source: FEATURES });
  map.addLayer({
    id: SELECTED, type: 'circle', source: FEATURES, filter: ['==', ['get', 'evidence_id'], ''],
    paint: { 'circle-radius': 11, 'circle-opacity': 0, 'circle-stroke-width': 3, 'circle-stroke-color': '#f43f5e' },
  });
}

export default function PropertyMapCanvas({
  basemap, initialView, features, paint, outline, selectedId, intelPoint, radiusM, focusPoint, onSelectFeature, onPickPoint,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const handlers = useRef({ onSelectFeature, onPickPoint });
  const [ready, setReady] = useState(false);
  const [drawn, setDrawn] = useState(0);
  handlers.current = { onSelectFeature, onPickPoint };

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: baseStyle(basemap),
      ...(initialView.bounds
        ? { bounds: initialView.bounds, fitBoundsOptions: { padding: 24 } }
        : { center: initialView.center, zoom: initialView.zoom }),
      attributionControl: true,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');
    map.on('load', () => {
      addLayers(map);
      setReady(true);
    });
    // What MapLibre actually drew, not what it was handed: a failed worker or a
    // rejected style draws nothing while the data still looks loaded.
    map.on('idle', () => {
      if (map.getLayer(FEATURES)) setDrawn(map.queryRenderedFeatures({ layers: [FEATURES] }).length);
    });
    map.on('click', (event) => {
      const hit = map.getLayer(FEATURES) ? map.queryRenderedFeatures(event.point, { layers: [FEATURES] })[0] : null;
      if (hit?.properties?.evidence_id) handlers.current.onSelectFeature(hit.properties.evidence_id);
      else handlers.current.onPickPoint({ lon: event.lngLat.lng, lat: event.lngLat.lat });
    });
    map.on('mouseenter', FEATURES, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', FEATURES, () => { map.getCanvas().style.cursor = ''; });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.getSource(FEATURES).setData(featureCollection(features));
    Object.entries(paint).forEach(([property, value]) => map.setPaintProperty(FEATURES, property, value));
  }, [ready, features, paint]);

  useEffect(() => {
    if (ready) mapRef.current?.getSource(OUTLINE).setData(outline || featureCollection([]));
  }, [ready, outline]);

  useEffect(() => {
    if (ready) mapRef.current?.setFilter(SELECTED, ['==', ['get', 'evidence_id'], selectedId || '']);
  }, [ready, selectedId]);

  useEffect(() => {
    if (ready) mapRef.current?.getSource(INTEL).setData(intelData(intelPoint, radiusM));
  }, [ready, intelPoint, radiusM]);

  useEffect(() => {
    if (ready && focusPoint) mapRef.current?.easeTo({ center: [focusPoint.lon, focusPoint.lat] });
  }, [ready, focusPoint]);

  return (
    <div
      ref={containerRef}
      data-testid="property-map-canvas"
      data-map-ready={ready ? 'true' : 'false'}
      data-feature-count={features.length}
      data-drawn-count={drawn}
      role="region"
      aria-label="Property Map. Every mapped record is also listed under Mapped records."
      className="h-full w-full"
    />
  );
}
