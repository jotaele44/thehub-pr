import pytest

from hub.mcp_runtime import MCPRequest, PolicyViolation, Router, RuntimeRegistry
from hub.mcp_runtime.adapters import (
    DOMAIN_ADAPTERS,
    ContractsAdapter,
    FieldOpsAdapter,
    FlightAdapter,
    OshaAdapter,
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
        self.headers = []

    def get(self, url, params=None, headers=None):
        self.calls.append((url, dict(params or {})))
        self.headers.append(dict(headers or {}))
        return self.payload


class RoutingFakeClient:
    """Returns a payload chosen by the first matching URL substring."""

    def __init__(self, routes):
        self.routes = routes  # list of (substring, payload)
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append((url, dict(params or {})))
        for needle, payload in self.routes:
            if needle in url:
                return payload
        raise AssertionError(f"no fake route for {url}")


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


def test_weather_forecast_follows_nws_two_step(router):
    forecast_url = "https://api.weather.gov/gridpoints/SJU/40,50/forecast"
    client = RoutingFakeClient([
        ("/points/", {"properties": {"forecast": forecast_url}}),
        ("/gridpoints/", {"properties": {"periods": [{"name": "Today"}]}}),
    ])
    router.register_adapter(WeatherAdapter(client=client))
    result = router.route(
        MCPRequest(
            project="aguayluz", capability="weather", action="forecast",
            params={"lat": 18.2, "lon": -66.5},
        )
    )
    assert result.data["periods"] == [{"name": "Today"}]
    # first call resolves the point, second fetches the gridpoint forecast
    assert client.calls[0][0] == "https://api.weather.gov/points/18.2,-66.5"
    assert client.calls[1][0] == forecast_url


def test_weather_forecast_empty_when_point_unresolved(router):
    client = RoutingFakeClient([("/points/", {"properties": {}})])
    router.register_adapter(WeatherAdapter(client=client))
    result = router.route(
        MCPRequest(
            project="aguayluz", capability="weather", action="forecast",
            params={"lat": 18.2, "lon": -66.5},
        )
    )
    assert result.data["periods"] == []


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

CONTRACTS_WINDOW = {"posted_from": "01/01/2026", "posted_to": "03/01/2026"}


def test_contracts_requires_api_key(router, monkeypatch):
    monkeypatch.delenv("MCP_CONTRACTS_API_KEY", raising=False)
    router.register_adapter(ContractsAdapter(client=FakeClient({})))
    with pytest.raises(PermissionError, match="authenticate"):
        router.route(
            MCPRequest(
                project="moneysweep", capability="contracts", action="search",
                params={"keyword": "recovery", **CONTRACTS_WINDOW},
            )
        )


def test_contracts_requires_date_window(router, monkeypatch):
    monkeypatch.setenv("MCP_CONTRACTS_API_KEY", "SECRET123")
    router.register_adapter(ContractsAdapter(client=FakeClient({})))
    with pytest.raises(ValueError, match="posted_from"):
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
            params={"keyword": "recovery", **CONTRACTS_WINDOW},
        )
    )
    assert result.data["count"] == 1
    _, params = client.calls[0]
    # SAM.gov contract: title search + mandatory posted-date window + key.
    assert params["title"] == "recovery"
    assert params["postedFrom"] == "01/01/2026"
    assert params["postedTo"] == "03/01/2026"
    assert params["api_key"] == "SECRET123"
    # secret never leaks into the audit/provenance block.
    assert "SECRET123" not in str(result.provenance)


def test_osha_requires_api_key(router, monkeypatch):
    monkeypatch.delenv("MCP_OSHA_API_KEY", raising=False)
    router.register_adapter(OshaAdapter(client=FakeClient({})))
    with pytest.raises(PermissionError, match="authenticate"):
        router.route(
            MCPRequest(
                project="aguayluz", capability="osha", action="inspections",
                params={"state": "PR"},
            )
        )


def test_osha_defaults_to_pr_filter_and_injects_key(router, monkeypatch):
    monkeypatch.setenv("MCP_OSHA_API_KEY", "OSHAKEY")
    client = FakeClient({"data": [{"activity_nr": 1}, {"activity_nr": 2}]})
    router.register_adapter(OshaAdapter(client=client))
    result = router.route(
        MCPRequest(
            project="aguayluz", capability="osha", action="inspections",
        )
    )
    assert result.data["count"] == 2
    assert result.data["state"] == "PR"
    url, params = client.calls[0]
    # DOL v4 record endpoint for the OSHA inspection dataset.
    assert url == "https://apiprod.dol.gov/v4/get/OSHA/inspection/json"
    # PR jurisdiction filter defaulted on (a JSON string, not a repr'd list).
    assert '"value": "PR"' in params["filter_object"]
    # Free key injected on the X-API-KEY *header*, not the query string.
    assert client.headers[0]["X-API-KEY"] == "OSHAKEY"
    assert "X-API-KEY" not in params
    # secret never leaks into the audit/provenance block.
    assert "OSHAKEY" not in str(result.provenance)
    assert result.provenance["upstream"] == "dol_osha"


def test_osha_serializes_structured_filter_object(router, monkeypatch):
    monkeypatch.setenv("MCP_OSHA_API_KEY", "OSHAKEY")
    client = FakeClient({"data": []})
    router.register_adapter(OshaAdapter(client=client))
    router.route(
        MCPRequest(
            project="aguayluz", capability="osha", action="violations",
            params={"filter_object": [{"field": "naics_code", "operator": "eq", "value": "331110"}]},
        )
    )
    _, params = client.calls[0]
    # A caller-supplied list is JSON-serialized (valid JSON, double quotes), not repr'd.
    assert params["filter_object"] == '[{"field": "naics_code", "operator": "eq", "value": "331110"}]'


def test_osha_unknown_action_raises(router, monkeypatch):
    monkeypatch.setenv("MCP_OSHA_API_KEY", "OSHAKEY")
    router.register_adapter(OshaAdapter(client=FakeClient({"data": []})))
    with pytest.raises(ValueError, match="unknown action"):
        router.route(
            MCPRequest(
                project="aguayluz", capability="osha", action="citations",
            )
        )


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
        "regulations", "osha", "utilities", "field-ops",
    }
