import React from "react";
import MapLibrePointMap from "./MapLibrePointMap";

// Simple single-coordinate display using the federation's canonical 2D engine.
export default function MapView({ lat, lon, label, height = 240 }) {
  if (lat === undefined || lat === null || lon === undefined || lon === null) return null;
  return (
    <MapLibrePointMap
      points={[{ id: "single-point", lat: Number(lat), lon: Number(lon), title: label || "" }]}
      height={height}
      zoom={10}
      scrollZoom={false}
    />
  );
}
