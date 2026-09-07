import React, { useEffect, useRef } from 'react';
import {
  Cartesian3,
  GeoJsonDataSource,
  Math as CesiumMath,
  Rectangle,
  SingleTileImageryProvider,
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
  const source = await GeoJsonDataSource.load(geojson, { clampToGround: false });
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

async function replaceRasterPreview(viewer, preview, layerRef, tokenRef) {
  const token = ++tokenRef.current;
  if (layerRef.current && !viewer.isDestroyed()) {
    viewer.imageryLayers.remove(layerRef.current, true);
    layerRef.current = null;
  }
  if (!preview?.imageUrl || !Array.isArray(preview.coordinates)) return;
  const [northWest, northEast, southEast] = preview.coordinates;
  const west = Number(northWest?.[0]);
  const north = Number(northWest?.[1]);
  const east = Number(northEast?.[0]);
  const south = Number(southEast?.[1]);
  if (![west, south, east, north].every(Number.isFinite)) throw new Error('invalid raster preview coordinates');
  const provider = await SingleTileImageryProvider.fromUrl(preview.imageUrl, {
    rectangle: Rectangle.fromDegrees(west, south, east, north),
  });
  if (token !== tokenRef.current || viewer.isDestroyed()) return;
  layerRef.current = viewer.imageryLayers.addImageryProvider(provider);
  layerRef.current.alpha = 0.72;
}

export default function CesiumRenderer({ canonicalState, layer, basemap, rasterPreview = null, onCanonicalViewChange }) {
  const containerRef = useRef(null);
  const viewerRef = useRef(null);
  const applyingCanonicalRef = useRef(false);
  const dataTokenRef = useRef(0);
  const rasterTokenRef = useRef(0);
  const rasterLayerRef = useRef(null);

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
    replaceRasterPreview(viewer, rasterPreview, rasterLayerRef, rasterTokenRef).catch(() => {});
    return () => {
      dataTokenRef.current += 1;
      rasterTokenRef.current += 1;
      viewer.camera.moveEnd.removeEventListener(publishView);
      viewer.destroy();
      viewerRef.current = null;
      rasterLayerRef.current = null;
    };
  }, []);

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
    replaceRasterPreview(viewer, rasterPreview, rasterLayerRef, rasterTokenRef).catch(() => {});
  }, [basemap.url]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    replaceRasterPreview(viewer, rasterPreview, rasterLayerRef, rasterTokenRef).catch(() => {});
  }, [rasterPreview]);

  return <div ref={containerRef} data-testid="cesium-renderer" className="h-full w-full" />;
}
