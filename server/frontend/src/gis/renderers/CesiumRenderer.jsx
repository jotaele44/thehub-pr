import React, { useEffect, useRef } from 'react';
import {
  Cartesian3,
  CesiumMath,
  GeoJsonDataSource,
  UrlTemplateImageryProvider,
  Viewer,
  buildModuleUrl,
} from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import { canonicalViewToCesium, cesiumViewToCanonical } from '../rendererView';

function cesiumBaseUrl() {
  const base = String(import.meta.env.BASE_URL || '/');
  return `${base.endsWith('/') ? base : `${base}/`}cesium/`;
}

function canvasHeight(viewer) {
  return Math.max(1, viewer?.scene?.canvas?.clientHeight || viewer?.scene?.canvas?.height || 640);
}

function verticalFov(viewer) {
  const frustum = viewer?.camera?.frustum;
  return Number.isFinite(frustum?.fov) ? frustum.fov : Math.PI / 3;
}

function cameraCanonicalView(viewer) {
  const cartographic = viewer.camera.positionCartographic;
  return cesiumViewToCanonical({
    longitude: CesiumMath.toDegrees(cartographic.longitude),
    latitude: CesiumMath.toDegrees(cartographic.latitude),
    height: cartographic.height,
    heading: viewer.camera.heading,
    pitch: viewer.camera.pitch,
  }, canvasHeight(viewer), verticalFov(viewer));
}

async function replaceGeoJson(viewer, geojson, tokenRef) {
  const token = ++tokenRef.current;
  viewer.dataSources.removeAll(true);
  if (!geojson) return;
  const source = await GeoJsonDataSource.load(geojson, {
    clampToGround: false,
  });
  if (token !== tokenRef.current || viewer.isDestroyed()) return;
  await viewer.dataSources.add(source);
}

function replaceBasemap(viewer, basemap) {
  viewer.imageryLayers.removeAll(true);
  const provider = new UrlTemplateImageryProvider({
    url: basemap.url,
    subdomains: ['a', 'b', 'c'],
    credit: basemap.attribution || undefined,
  });
  viewer.imageryLayers.addImageryProvider(provider);
}

export default function CesiumRenderer({ canonicalState, layer, basemap, onCanonicalViewChange }) {
  const containerRef = useRef(null);
  const viewerRef = useRef(null);
  const applyingCanonicalRef = useRef(false);
  const dataTokenRef = useRef(0);

  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return undefined;
    buildModuleUrl.setBaseUrl(cesiumBaseUrl());
    const viewer = new Viewer(containerRef.current, {
      animation: false,
      baseLayer: false,
      baseLayerPicker: false,
      fullscreenButton: false,
      geocoder: false,
      homeButton: false,
      infoBox: true,
      navigationHelpButton: false,
      sceneModePicker: false,
      selectionIndicator: true,
      timeline: false,
      shouldAnimate: false,
    });
    replaceBasemap(viewer, basemap);
    const publishView = () => {
      if (applyingCanonicalRef.current || !onCanonicalViewChange || viewer.isDestroyed()) return;
      onCanonicalViewChange(cameraCanonicalView(viewer), 'cesium');
    };
    viewer.camera.moveEnd.addEventListener(publishView);
    viewerRef.current = viewer;
    replaceGeoJson(viewer, layer?.geojson || null, dataTokenRef).catch(() => {});
    return () => {
      dataTokenRef.current += 1;
      viewer.camera.moveEnd.removeEventListener(publishView);
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []); // renderer lifetime intentionally independent from canonical-state updates

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    const view = canonicalViewToCesium(canonicalState.view, canvasHeight(viewer), verticalFov(viewer));
    applyingCanonicalRef.current = true;
    viewer.camera.setView({
      destination: Cartesian3.fromDegrees(view.longitude, view.latitude, view.height),
      orientation: { heading: view.heading, pitch: view.pitch, roll: view.roll },
    });
    queueMicrotask(() => { applyingCanonicalRef.current = false; });
  }, [canonicalState.view.center.lon, canonicalState.view.center.lat, canonicalState.view.groundResolutionM, canonicalState.view.bearing, canonicalState.view.requestedPitch]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    replaceGeoJson(viewer, layer?.geojson || null, dataTokenRef).catch(() => {});
  }, [layer?.manifest?.layerId, layer?.geojson]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    replaceBasemap(viewer, basemap);
  }, [basemap.url]);

  return <div ref={containerRef} data-testid="cesium-renderer" className="h-full w-full" />;
}
