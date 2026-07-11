import pytest

from hub.mcp_runtime import MCPRequest, PolicyViolation, Router, RuntimeRegistry
from hub.mcp_runtime.adapters import (
    DOMAIN_ADAPTERS,
    ContractsAdapter,
    FieldOpsAdapter,
    FlightAdapter,
    RegulationsAdapter,
    TerrainAdapter,
    UtilitiesAdapter,
    WeatherAdapter,
)


class FakeClient:
    """Records outgoing calls and returns a canned payload — no network."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        return self.payload


@pytest.fixture()
def registry():
    return RuntimeRegistry()


@pytest.fixture()
def router(registry):
    return Router(registry)


# --- keyless adapters -----------------------------------------------------

def test_flight_states(router):
    client = FakeClient({"states": [["a"], ["b"], ["c"]]})
    router.register_adapter(FlightAdapter(client=client))
    result = router.route(
        MCPRequest(project="skywatcher", capability="flight", action="states")
    )
    assert result.data["count"] == 3
    assert result.provenance["upstream"] == "opensky"
    assert result.provenance["version_pin"] == "1.0.0"
    assert client.calls[0][0] == "https://opensky-network.org/api/states/all"


def test_weather_forecast_sends_coords(router):
    client = FakeClient({"periods": [{"name": "Today"}]})
    router.register_adapter(WeatherAdapter(client=client))
    result = router.route(
        MCPRequest(
            project="aguayluz", capability="weather", action="forecast",
            params={"lat": 18.2, "lon": -66.5},
        )
    )
    assert result.data["periods"] == [{"name": "Today"}]
    url, params = client.calls[0]
    assert url.endswith("/forecast")
    assert params == {"lat": 18.2, "lon": -66.5}


def test_terrain_elevation(router):
    client = FakeClient({"value": 123.4})
    router.register_adapter(TerrainAdapter(client=client))
    result = router.route(
        MCPRequest(
            project="skywatcher", capability="terrain", action="elevation",
            params={"lat": 18.2, "lon": -66.5},
        )
    )
    assert result.data["elevation_m"] == 123.4


def test_field_ops_observations(router):
    client = FakeClient({"observations": [{"id": 1}, {"id": 2}]})
    router.register_adapter(FieldOpsAdapter(client=client))
    result = router.route(
        MCPRequest(
            project="centinelas", capability="field-ops", action="observations",
            params={"since": "2026-01-01"},
        )
    )
    assert result.data["count"] == 2
    assert client.calls[0][1] == {"since": "2026-01-01"}


# --- keyed adapters (fail-closed + secret handling) -----------------------

def test_contracts_requires_api_key(router, monkeypatch):
    monkeypatch.delenv("MCP_CONTRACTS_API_KEY", raising=False)
    router.register_adapter(ContractsAdapter(client=FakeClient({})))
    with pytest.raises(PermissionError, match="authenticate"):
        router.route(
            MCPRequest(
                project="moneysweep", capability="contracts", action="search",
                params={"keyword": "recovery"},
            )
        )


def test_contracts_injects_key_but_keeps_it_out_of_provenance(router, monkeypatch):
    monkeypatch.setenv("MCP_CONTRACTS_API_KEY", "SECRET123")
    client = FakeClient({"opportunitiesData": [{"noticeId": "x"}]})
    router.register_adapter(ContractsAdapter(client=client))
    result = router.route(
        MCPRequest(
            project="moneysweep", capability="contracts", action="search",
            params={"keyword": "recovery"},
        )
    )
    assert result.data["count"] == 1
    # secret is sent to the upstream...
    assert client.calls[0][1]["api_key"] == "SECRET123"
    # ...but never leaks into the audit/provenance block.
    assert "SECRET123" not in str(result.provenance)


def test_regulations_search(router, monkeypatch):
    monkeypatch.setenv("MCP_REGULATIONS_API_KEY", "RK")
    client = FakeClient({"data": [{"id": "d1"}, {"id": "d2"}]})
    router.register_adapter(RegulationsAdapter(client=client))
    result = router.route(
        MCPRequest(
            project="spiderweb", capability="regulations", action="search",
            params={"keyword": "flood"},
        )
    )
    assert result.data["count"] == 2


def test_utilities_status(router, monkeypatch):
    monkeypatch.setenv("MCP_UTILITIES_API_KEY", "UK")
    client = FakeClient({"status": "degraded", "as_of": "2026-07-01"})
    router.register_adapter(UtilitiesAdapter(client=client))
    result = router.route(
        MCPRequest(
            project="aguayluz", capability="utilities", action="status",
            params={"system": "prepa"},
        )
    )
    assert result.data["status"] == "degraded"


# --- governance still enforced -------------------------------------------

def test_domain_write_blocked_by_read_only_default(router):
    router.register_adapter(WeatherAdapter(client=FakeClient({})))
    with pytest.raises(PolicyViolation, match="allowed_writes"):
        router.route(
            MCPRequest(
                project="centinelas", capability="weather", action="update",
                params={"lat": 18.2, "lon": -66.5}, is_write=True,
            )
        )


def test_domain_capability_gated_by_manifest(router):
    # spiderweb does not declare 'contracts'.
    router.register_adapter(ContractsAdapter(client=FakeClient({})))
    with pytest.raises(PolicyViolation, match="does not declare"):
        router.route(
            MCPRequest(
                project="spiderweb", capability="contracts", action="search",
                params={"keyword": "x"},
            )
        )


def test_domain_adapter_registry_is_complete():
    caps = {a.capability_name for a in DOMAIN_ADAPTERS}
    assert caps == {
        "flight", "weather", "terrain", "contracts",
        "regulations", "utilities", "field-ops",
    }
