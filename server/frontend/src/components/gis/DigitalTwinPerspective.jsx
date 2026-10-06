import React, { useEffect, useRef, useState } from 'react';
import {
  Cartesian2, Cartesian3, Color, CustomDataSource, EllipsoidTerrainProvider, HeadingPitchRange, HeightReference, Math as CesiumMath,
  ImageryLayer, Matrix4, UrlTemplateImageryProvider, Viewer, buildModuleUrl,
} from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import { BASEMAPS, IMAGERY_BASEMAPS } from '@/gis/basemaps';
import { CUDEM_PR } from '@/gis/cudem';
import { ORTHO_MINIMUM_TERRAIN_LEVEL, createCudemTerrainProvider } from '@/gis/cudemTerrainProvider';
import { terrainSource } from '@/gis/advanced3dSourceRegistry';
import { cesiumHeightFromGroundResolution, groundResolutionFromCesiumHeight, groundResolutionFromMapLibreZoom, mapLibreZoomFromGroundResolution } from '@/gis/rendererView';

// Perspective panel of the Digital Twin: Cesium with the uniform-datum CUDEM
// terrain (bound only when the 3D gate certifies it), USGS orthoimagery draped
// over it (CARTO below zoom 11, where the imagery has no Puerto Rico tiles) and
// the Hub's records clamped to the ground, styled by declared precision.
const PITCH = CesiumMath.toRadians(-40);
const FALLBACK = Color.fromCssColorString('#9ca3af');

function cesiumBaseUrl() {
  const base = String(import.meta.env.BASE_URL || '/');
  return `${base.endsWith('/') ? base : `${base}/`}cesium/`;
}

function imagery(viewer) {
  viewer.imageryLayers.removeAll(true);
  viewer.imageryLayers.addImageryProvider(new UrlTemplateImageryProvider({ url: BASEMAPS.cartoDark.url, credit: 'OpenStreetMap, CARTO' }));
  const ortho = IMAGERY_BASEMAPS.usgsImagery;
  viewer.imageryLayers.add(new ImageryLayer(
    new UrlTemplateImageryProvider({ url: ortho.url, minimumLevel: ortho.minzoom, credit: ortho.attribution }),
    { minimumTerrainLevel: ORTHO_MINIMUM_TERRAIN_LEVEL },
  ));
}

function pointStyle(precision, color, selected) {
  const size = selected ? 14 : 9;
  if (precision === 'OBSERVED_POINT') return { color, outlineColor: Color.WHITE, outlineWidth: 1, pixelSize: size };
  if (precision === 'INTERPRETED_POINT') return { color: color.withAlpha(0.55), outlineColor: Color.WHITE, outlineWidth: 3, pixelSize: size };
  return { color: Color.TRANSPARENT, outlineColor: color, outlineWidth: 2, pixelSize: size + 2 };
}

function cameraTo(viewer, view) {
  const resolution = groundResolutionFromMapLibreZoom(view.zoom, view.center[1]);
  const height = cesiumHeightFromGroundResolution(resolution, viewer.scene.canvas.clientHeight || 480);
  const target = Cartesian3.fromDegrees(view.center[0], view.center[1], 0);
  viewer.camera.lookAt(target, new HeadingPitchRange(CesiumMath.toRadians(view.bearing || 0), PITCH, height / Math.sin(-PITCH)));
  viewer.camera.lookAtTransform(Matrix4.IDENTITY);
}

function angleApart(a, b) {
  return Math.abs(((((a - b) % 360) + 540) % 360) - 180);
}

// Views this close are one camera for every panel.
function sameView(a, b) {
  return Math.abs(a.center[0] - b.center[0]) < 1e-5 && Math.abs(a.center[1] - b.center[1]) < 1e-5
    && Math.abs(a.zoom - b.zoom) < 0.05 && angleApart(a.bearing || 0, b.bearing || 0) < 0.5;
}

function viewOf(viewer) {
  const canvas = viewer.scene.canvas;
  const centre = viewer.camera.pickEllipsoid(new Cartesian2(canvas.clientWidth / 2, canvas.clientHeight / 2));
  if (!centre) return null;
  const cartographic = viewer.scene.globe.ellipsoid.cartesianToCartographic(centre);
  const lat = CesiumMath.toDegrees(cartographic.latitude);
  const height = Cartesian3.distance(viewer.camera.positionWC, centre) * Math.sin(-PITCH);
  return {
    center: [CesiumMath.toDegrees(cartographic.longitude), lat],
    zoom: mapLibreZoomFromGroundResolution(groundResolutionFromCesiumHeight(height, canvas.clientHeight || 480), lat),
    bearing: CesiumMath.toDegrees(viewer.camera.heading) % 360,
  };
}

export default function DigitalTwinPerspective({ features, colors, selectedId, view, onViewChange, onSelectFeature, onTerrainTiles, onTerrainError }) {
  const containerRef = useRef(null);
  const viewerRef = useRef(null);
  const recordsRef = useRef(null);
  const applyingRef = useRef(false);
  const handlers = useRef({ view, onViewChange, onSelectFeature, onTerrainTiles, onTerrainError });
  const [terrain] = useState(() => terrainSource(CUDEM_PR.sourceId));
  const [ready, setReady] = useState(false);
  handlers.current = { view, onViewChange, onSelectFeature, onTerrainTiles, onTerrainError };
  const terrainBound = terrain?.status === 'READY_FOR_RUNTIME_BINDING';

  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return undefined;
    buildModuleUrl.setBaseUrl(cesiumBaseUrl());
    const viewer = new Viewer(containerRef.current, {
      animation: false, baseLayer: false, baseLayerPicker: false, fullscreenButton: false, geocoder: false, homeButton: false,
      infoBox: false, navigationHelpButton: false, sceneModePicker: false, selectionIndicator: true, timeline: false,
      shouldAnimate: false,
      // Render only when something changes (camera, data, tiles) instead of every frame.
      requestRenderMode: true,
      maximumRenderTimeChange: Infinity,
      terrainProvider: terrainBound
        ? createCudemTerrainProvider({
          onTiles: (names) => handlers.current.onTerrainTiles?.(names),
          onError: (error) => handlers.current.onTerrainError?.(error),
        })
        : new EllipsoidTerrainProvider(),
    });
    imagery(viewer);
    const records = new CustomDataSource('hub-records');
    viewer.dataSources.add(records);
    recordsRef.current = records;
    viewer.selectedEntityChanged.addEventListener((entity) => {
      if (entity?.id) handlers.current.onSelectFeature?.(entity.id);
    });
    viewer.camera.moveEnd.addEventListener(() => {
      if (applyingRef.current) { applyingRef.current = false; return; }
      const next = viewOf(viewer);
      // Loading terrain nudges the camera; only a view the panels do not already share is published.
      const shared = handlers.current.view;
      if (next && !(shared && sameView(next, shared))) handlers.current.onViewChange?.(next);
    });
    viewerRef.current = viewer;
    setReady(true);
    return () => {
      viewer.destroy();
      viewerRef.current = null;
      recordsRef.current = null;
    };
  }, []);

  useEffect(() => {
    const records = recordsRef.current;
    if (!ready || !records) return;
    records.entities.suspendEvents();
    records.entities.removeAll();
    for (const item of features) {
      const props = item.properties;
      const color = colors[props.category] ? Color.fromCssColorString(colors[props.category]) : FALLBACK;
      records.entities.add({
        id: item.id,
        name: props.title,
        position: Cartesian3.fromDegrees(item.geometry.coordinates[0], item.geometry.coordinates[1]),
        point: {
          ...pointStyle(props.geometry_precision, color, item.id === selectedId),
          heightReference: HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
    }
    records.entities.resumeEvents();
    viewerRef.current?.scene.requestRender();
  }, [ready, features, colors, selectedId]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!ready || !viewer || !view) return;
    const current = viewOf(viewer);
    if (current && sameView(current, view)) return;
    applyingRef.current = true;
    cameraTo(viewer, view);
  }, [ready, view]);

  return (
    <div
      ref={containerRef}
      data-testid="digital-twin-perspective"
      data-ready={ready ? 'true' : 'false'}
      data-terrain={terrainBound ? terrain.sourceId : 'ellipsoid'}
      data-entity-count={features.length}
      role="region"
      aria-label="Perspective view with terrain. Every record shown is also listed in the Details panel."
      className="h-full w-full"
    />
  );
}
