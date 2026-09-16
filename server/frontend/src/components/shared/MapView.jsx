import React from "react";
import MapLibrePointMap from "./MapLibrePointMap";
import { buildSinglePointParityModel } from "./sharedMapParity";

// Simple single-coordinate display using the federation's canonical 2D engine.
export default function MapView({ lat, lon, label, height = 240 }) {
  const model = buildSinglePointParityModel(lat, lon, label);
  if (!model) return null;
  return (
    <MapLibrePointMap
      points={model.points}
      height={height}
      zoom={model.zoom}
      scrollZoom={model.scrollZoom}
    />
  );
}
