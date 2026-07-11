"""Domain adapters — the seven domain/government capabilities.

Each is a thin `BaseHttpAdapter` subclass: it owns its request/return contract
(actions, params, the normalized shape it returns) and does a *defensive*
extraction from the upstream payload with ``.get`` so a schema drift degrades
to empty fields rather than a crash. Real endpoints are wired via `base_url`
and, where required, an environment-provided API key — those live paths must
be verified outside CI; the tests here drive every adapter through a fake
`HttpClient` and never touch the network.

Capability → declaring projects (see mcp/registry/capability_registry.yaml):
  flight       → skywatcher
  weather      → skywatcher, centinelas, aguayluz
  terrain      → skywatcher, aguayluz
  contracts    → moneysweep
  regulations  → spiderweb
  utilities    → aguayluz
  field-ops    → centinelas
"""

from __future__ import annotations

from typing import Any, Dict

from hub.mcp_runtime.adapters.http import BaseHttpAdapter
from hub.mcp_runtime.sdk import MCPRequest


class FlightAdapter(BaseHttpAdapter):
    capability_name = "flight"
    adapter_name = "flight-adsb"
    upstream = "opensky"
    base_url = "https://opensky-network.org/api"

    def execute(self, request: MCPRequest) -> Any:
        if request.action == "states":
            payload = self._get("/states/all", request.params or None)
            states = payload.get("states") or []
            return {"states": states, "count": len(states)}
        if request.action == "track":
            icao24 = request.params.get("icao24")
            if not icao24:
                raise ValueError("track requires an 'icao24' param")
            payload = self._get("/tracks/all", {"icao24": icao24})
            return {"icao24": icao24, "path": payload.get("path") or []}
        raise ValueError(f"unknown action {request.action!r}")


class WeatherAdapter(BaseHttpAdapter):
    capability_name = "weather"
    adapter_name = "weather-nws"
    upstream = "nws"
    base_url = "https://api.weather.gov"

    def execute(self, request: MCPRequest) -> Any:
        if request.action == "forecast":
            lat, lon = request.params.get("lat"), request.params.get("lon")
            if lat is None or lon is None:
                raise ValueError("forecast requires 'lat' and 'lon' params")
            # NWS flow: /points/{lat},{lon} yields a gridpoint forecast URL,
            # whose periods live under properties.periods.
            points = self._get(f"/points/{lat},{lon}")
            forecast_url = (points.get("properties") or {}).get("forecast")
            location = {"lat": lat, "lon": lon}
            if not forecast_url:
                return {"location": location, "periods": []}
            grid = self._request(forecast_url)
            periods = (grid.get("properties") or {}).get("periods") or []
            return {"location": location, "periods": periods}
        raise ValueError(f"unknown action {request.action!r}")


class TerrainAdapter(BaseHttpAdapter):
    capability_name = "terrain"
    adapter_name = "terrain-epqs"
    upstream = "usgs_epqs"
    base_url = "https://epqs.nationalmap.gov"

    def execute(self, request: MCPRequest) -> Any:
        if request.action == "elevation":
            lat, lon = request.params.get("lat"), request.params.get("lon")
            if lat is None or lon is None:
                raise ValueError("elevation requires 'lat' and 'lon' params")
            payload = self._get("/v1/json", {"x": lon, "y": lat, "units": "Meters"})
            return {"location": {"lat": lat, "lon": lon},
                    "elevation_m": payload.get("value")}
        raise ValueError(f"unknown action {request.action!r}")


class ContractsAdapter(BaseHttpAdapter):
    capability_name = "contracts"
    adapter_name = "contracts-sam"
    upstream = "sam_gov"
    base_url = "https://api.sam.gov"
    env_key = "MCP_CONTRACTS_API_KEY"
    auth_param_name = "api_key"

    def execute(self, request: MCPRequest) -> Any:
        if request.action == "search":
            keyword = request.params.get("keyword")
            if not keyword:
                raise ValueError("search requires a 'keyword' param")
            # SAM.gov Get Opportunities requires a posted-date window
            # (MM/dd/yyyy) and searches titles via `title` (no `q`).
            posted_from = request.params.get("posted_from")
            posted_to = request.params.get("posted_to")
            if not posted_from or not posted_to:
                raise ValueError(
                    "search requires 'posted_from' and 'posted_to' "
                    "(MM/dd/yyyy) date params"
                )
            query = {
                "title": keyword,
                "postedFrom": posted_from,
                "postedTo": posted_to,
                "limit": request.params.get("limit", 10),
            }
            payload = self._get("/opportunities/v2/search", query)
            records = payload.get("opportunitiesData") or []
            return {"keyword": keyword, "opportunities": records,
                    "count": len(records)}
        raise ValueError(f"unknown action {request.action!r}")


class RegulationsAdapter(BaseHttpAdapter):
    capability_name = "regulations"
    adapter_name = "regulations-gov"
    upstream = "regulations_gov"
    base_url = "https://api.regulations.gov"
    env_key = "MCP_REGULATIONS_API_KEY"
    auth_param_name = "api_key"

    def execute(self, request: MCPRequest) -> Any:
        if request.action == "search":
            keyword = request.params.get("keyword")
            if not keyword:
                raise ValueError("search requires a 'keyword' param")
            payload = self._get("/v4/documents", {"filter[searchTerm]": keyword})
            documents = payload.get("data") or []
            return {"keyword": keyword, "documents": documents,
                    "count": len(documents)}
        raise ValueError(f"unknown action {request.action!r}")


class UtilitiesAdapter(BaseHttpAdapter):
    capability_name = "utilities"
    adapter_name = "utilities-bridge"
    upstream = "utilities"
    base_url = ""  # site-specific PRASA/PREPA/LUMA endpoint, supplied at deploy
    env_key = "MCP_UTILITIES_API_KEY"
    auth_param_name = "api_key"

    def execute(self, request: MCPRequest) -> Any:
        if request.action == "status":
            system = request.params.get("system")
            if not system:
                raise ValueError("status requires a 'system' param")
            payload = self._get("/status", {"system": system})
            return {"system": system, "status": payload.get("status"),
                    "as_of": payload.get("as_of")}
        raise ValueError(f"unknown action {request.action!r}")


class FieldOpsAdapter(BaseHttpAdapter):
    capability_name = "field-ops"
    adapter_name = "field-ops-bridge"
    upstream = "field_ops"
    base_url = ""  # Centinelas field intake endpoint, supplied at deploy

    def execute(self, request: MCPRequest) -> Any:
        if request.action == "observations":
            params: Dict[str, Any] = {}
            since = request.params.get("since")
            if since:
                params["since"] = since
            payload = self._get("/observations", params or None)
            observations = payload.get("observations") or []
            return {"observations": observations, "count": len(observations)}
        raise ValueError(f"unknown action {request.action!r}")


DOMAIN_ADAPTERS = (
    FlightAdapter,
    WeatherAdapter,
    TerrainAdapter,
    ContractsAdapter,
    RegulationsAdapter,
    UtilitiesAdapter,
    FieldOpsAdapter,
)
