import React from "react";
import MapLibrePointMap from "./MapLibrePointMap";

// Renders many geolocated records as pins.
// points: [{ id, lat, lon, title, subtitle }]
// onPointSelect preserves the existing record-selection callback without using
// position, title, or renderer state as identity proof.
export default function MultiMarkerMap({ points = [], height = 480, onPointSelect }) {
  return (
    <MapLibrePointMap
      points={points}
      height={height}
      zoom={9}
      scrollZoom
      onPointSelect={onPointSelect}
    />
  );
}
