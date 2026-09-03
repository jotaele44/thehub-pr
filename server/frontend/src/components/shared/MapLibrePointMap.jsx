import React, { useEffect, useMemo, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { loadMunicipiosGeoJSON, MUNICIPIOS_STYLE } from "./MunicipiosLayer";

const PR_CENTER = Object.freeze([-66.4, 18.22]);
const BASEMAP = Object.freeze({
  url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  attribution: "&copy; OpenStreetMap, &copy; CARTO",
});

function finiteCoordinate(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function normalizeMapPoints(points = []) {
  return points.filter((point) => finiteCoordinate(point?.lat) && finiteCoordinate(point?.lon));
}

function mapStyle() {
  return {
    version: 8,
    sources: {
      basemap: {
        type: "raster",
        tiles: [BASEMAP.url],
        tileSize: 256,
        attribution: BASEMAP.attribution,
      },
    },
    layers: [{ id: "basemap", type: "raster", source: "basemap", paint: { "raster-opacity": 0.85 } }],
  };
}

function addMunicipios(map, data) {
  if (!data || map.getSource("shared-municipios")) return;
  map.addSource("shared-municipios", { type: "geojson", data });
  map.addLayer({
    id: "shared-municipios-fill",
    type: "fill",
    source: "shared-municipios",
    paint: {
      "fill-color": MUNICIPIOS_STYLE.fillColor,
      "fill-opacity": MUNICIPIOS_STYLE.fillOpacity,
    },
  }, "basemap");
  map.addLayer({
    id: "shared-municipios-line",
    type: "line",
    source: "shared-municipios",
    paint: {
      "line-color": MUNICIPIOS_STYLE.color,
      "line-width": MUNICIPIOS_STYLE.weight,
    },
  }, "basemap");
}

function popupNode(point) {
  const root = document.createElement("div");
  const title = document.createElement("div");
  title.className = "text-sm font-medium";
  title.textContent = point.title || point.label || "";
  root.appendChild(title);
  if (point.subtitle) {
    const subtitle = document.createElement("div");
    subtitle.className = "text-xs text-muted-foreground mt-0.5";
    subtitle.textContent = point.subtitle;
    root.appendChild(subtitle);
  }
  return root;
}

export default function MapLibrePointMap({ points = [], height = 480, zoom = 9, scrollZoom = true, onPointSelect }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const valid = useMemo(() => normalizeMapPoints(points), [points]);
  const center = valid.length ? [valid[0].lon, valid[0].lat] : PR_CENTER;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: mapStyle(),
      center,
      zoom,
      attributionControl: true,
    });
    if (!scrollZoom) map.scrollZoom.disable();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", async () => {
      const municipios = await loadMunicipiosGeoJSON().catch(() => null);
      if (municipios && !map.isStyleLoaded()) return;
      if (municipios) addMunicipios(map, municipios);
    });
    mapRef.current = map;
    return () => {
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = valid.map((point) => {
      const popup = new maplibregl.Popup({ offset: 24 }).setDOMContent(popupNode(point));
      const marker = new maplibregl.Marker().setLngLat([point.lon, point.lat]).setPopup(popup).addTo(map);
      if (onPointSelect) marker.getElement().addEventListener("click", () => onPointSelect(point));
      return marker;
    });
  }, [valid, onPointSelect]);

  return <div className="rounded-lg overflow-hidden border border-border" style={{ height }}><div ref={containerRef} data-testid="shared-maplibre-map" style={{ height: "100%", width: "100%" }} /></div>;
}
