"""Geospatial adapter — point math over the Hub's existing PR-domain helpers.

Pure computation (no data files, no network). Reuses the correlator's
lat/lon helpers so distance semantics stay identical to the aggregate
correlation path.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Deliberate reuse of the correlator's geodesy so the adapter and the
# cross-producer spatial correlation agree to the metre. If a future change
# wants these public, promote them to a hub/geo.py module.
from hub.correlate import _coerce_latlon, _haversine_km
from hub.mcp_runtime.sdk import MCPAdapter, MCPRequest


class GeospatialAdapter(MCPAdapter):
    """Read-only geospatial computation.

    Actions:
      - ``distance``:  haversine km between params ``a`` and ``b``
                       (each ``[lat, lon]``).
      - ``nearest``:   closest of params ``candidates`` to params ``point``.
      - ``normalize_municipality``: upper/trim of params ``municipality``.
    """

    def name(self) -> str:
        return "geospatial-pr"

    def version(self) -> str:
        return "0.1.0"

    def capabilities(self) -> List[str]:
        return ["geospatial"]

    @staticmethod
    def _coord(value: Any, label: str) -> Tuple[float, float]:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError(f"{label} must be a [lat, lon] pair")
        coord = _coerce_latlon(value[0], value[1])
        if coord is None:
            raise ValueError(f"{label} is not a valid lat/lon: {value!r}")
        return coord

    def execute(self, request: MCPRequest) -> Any:
        params = request.params

        if request.action == "distance":
            lat1, lon1 = self._coord(params.get("a"), "a")
            lat2, lon2 = self._coord(params.get("b"), "b")
            return {"distance_km": _haversine_km(lat1, lon1, lat2, lon2)}

        if request.action == "nearest":
            lat, lon = self._coord(params.get("point"), "point")
            candidates = params.get("candidates") or []
            if not candidates:
                raise ValueError("nearest requires a non-empty 'candidates' list")
            best_index = -1
            best_km = float("inf")
            for index, candidate in enumerate(candidates):
                clat, clon = self._coord(candidate, f"candidates[{index}]")
                km = _haversine_km(lat, lon, clat, clon)
                if km < best_km:
                    best_km, best_index = km, index
            return {
                "index": best_index,
                "candidate": candidates[best_index],
                "distance_km": best_km,
            }

        if request.action == "normalize_municipality":
            muni = params.get("municipality")
            if not isinstance(muni, str) or not muni.strip():
                raise ValueError("normalize_municipality requires 'municipality'")
            return {"municipality": muni.strip().upper()}

        raise ValueError(f"unknown action {request.action!r}")

    def provenance(self, request: MCPRequest) -> Dict[str, Any]:
        block = super().provenance(request)
        block["method"] = "haversine/WGS84-sphere"
        return block
