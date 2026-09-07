import React from "react";
import MapLibrePointMap from "./MapLibrePointMap";
import { buildMultiMarkerParityModel, selectOriginalMapRecord } from "./sharedMapParity";

// Renders many geolocated records as pins while preserving the certified
// Leaflet-era filtering/centering/selection behavior through a renderer-neutral model.
export default function MultiMarkerMap({ points = [], height = 480, onPointSelect }) {
  const model = buildMultiMarkerParityModel(points);
  return (
    <MapLibrePointMap
      points={model.points}
      height={height}
      zoom={model.zoom}
      scrollZoom={model.scrollZoom}
      onPointSelect={onPointSelect ? (point) => selectOriginalMapRecord(point, onPointSelect) : undefined}
    />
  );
}
