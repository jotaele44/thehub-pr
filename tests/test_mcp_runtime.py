import pytest

from hub.mcp_runtime import (
    MCPRequest,
    PolicyEngine,
    PolicyViolation,
    Router,
    RuntimeRegistry,
)
from hub.mcp_runtime.adapters.mock import MockAdapter


@pytest.fixture()
def registry():
    return RuntimeRegistry()


@pytest.fixture()
def router(registry):
    return Router(registry)


def test_registry_loads_capabilities_and_manifests(registry):
    assert "federation-core" in registry.capabilities
    assert registry.capabilities["weather"].version_pin == "1.0.0"
    assert set(registry.manifests) == {
        "skywatcher",
        "ovnis",
        "spiderweb",
        "centinelas",
        "moneysweep",
        "aguayluz",
    }
    assert registry.project_declares("skywatcher", "flight")
    assert registry.project_declares("skywatcher", "satellite")
    assert not registry.project_declares("skywatcher", "contracts")


def test_route_declared_capability_returns_provenance(router):
    adapter = MockAdapter(["weather"])
    router.register_adapter(adapter)
    request = MCPRequest(
        project="centinelas",
        capability="weather",
        action="current_conditions",
        params={"municipality": "Ponce"},
    )
    result = router.route(request)
    assert result.status == "ok"
    assert result.data["echo"]["params"] == {"municipality": "Ponce"}
    assert result.provenance["adapter"] == "mock"
    assert result.provenance["version_pin"] == "1.0.0"
    assert adapter.calls == [request]


def test_route_undeclared_capability_is_policy_violation(router):
    router.register_adapter(MockAdapter(["contracts"]))
    request = MCPRequest(
        project="centinelas", capability="contracts", action="lookup"
    )
    with pytest.raises(PolicyViolation, match="does not declare"):
        router.route(request)


def test_write_denied_by_read_only_default(router):
    router.register_adapter(MockAdapter(["weather"]))
    request = MCPRequest(
        project="centinelas",
        capability="weather",
        action="update_station",
        is_write=True,
    )
    with pytest.raises(PolicyViolation, match="allowed_writes"):
        router.route(request)


def test_project_local_capability_routes(router):
    router.register_adapter(MockAdapter(["offline-cache"]))
    request = MCPRequest(
        project="centinelas", capability="offline-cache", action="get"
    )
    result = router.route(request)
    assert result.capability == "offline-cache"
    # project-local capabilities have no registry version_pin
    assert "version_pin" not in result.provenance


def test_unregistered_capability_raises_lookup_error(router):
    request = MCPRequest(project="skywatcher", capability="flight", action="track")
    with pytest.raises(LookupError, match="no adapter registered"):
        router.route(request)


def test_unhealthy_adapter_rejected_at_registration(router):
    with pytest.raises(ValueError, match="failed health check"):
        router.register_adapter(MockAdapter(["weather"], healthy=False))


def test_adapter_rejects_capability_it_does_not_serve():
    adapter = MockAdapter(["weather"])
    request = MCPRequest(project="centinelas", capability="field-ops", action="x")
    with pytest.raises(ValueError, match="does not serve"):
        adapter.run(request)


def test_provenance_sink_receives_audit_records(registry):
    audit = []
    router = Router(registry, provenance_sink=audit.append)
    router.register_adapter(MockAdapter(["weather"]))
    router.route(
        MCPRequest(project="aguayluz", capability="weather", action="forecast")
    )
    assert len(audit) == 1
    assert audit[0]["project"] == "aguayluz"
    assert audit[0]["capability"] == "weather"


def test_unknown_project_raises(registry):
    policy = PolicyEngine(registry)
    request = MCPRequest(project="nonexistent", capability="weather", action="x")
    with pytest.raises(ValueError, match="no manifest"):
        policy.check(request)
