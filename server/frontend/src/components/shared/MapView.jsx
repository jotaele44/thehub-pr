import React from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
// Bundle Leaflet's marker images through Vite (asset URLs) instead of fetching
// them from unpkg at runtime — keeps the app offline-safe / no third-party request.
import iconUrl from "leaflet/dist/images/marker-icon.png";
import iconRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import shadowUrl from "leaflet/dist/images/marker-shadow.png";
import MunicipiosLayer from "./MunicipiosLayer";

const icon = new L.Icon({
  iconUrl,
  iconRetinaUrl,
  shadowUrl,
  iconSize: [25, 41], iconAnchor: [12, 41],
});

// Simple pin map. No heavy GIS — single coordinate display only.
export default function MapView({ lat, lon, label, height = 240 }) {
  if (lat === undefined || lat === null || lon === undefined || lon === null) return null;
  return (
    <div className="rounded-lg overflow-hidden border border-border" style={{ height }}>
      <MapContainer center={[lat, lon]} zoom={10} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          opacity={0.85}
          attribution='&copy; OpenStreetMap, &copy; CARTO'
        />
        <MunicipiosLayer />
        <Marker position={[lat, lon]} icon={icon}>
          {label && <Popup>{label}</Popup>}
        </Marker>
      </MapContainer>
    </div>
  );
}