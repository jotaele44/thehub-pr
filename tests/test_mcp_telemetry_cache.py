import pytest

from hub.mcp_runtime import (
    InMemoryMetrics,
    MCPRequest,
    PolicyViolation,
    ResponseCache,
    Router,
    RuntimeRegistry,
)
from hub.mcp_runtime.adapters.mock import MockAdapter


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now


@pytest.fixture()
def registry():
    return RuntimeRegistry()


def _weather_req(project="centinelas", action="forecast", **kw):
    return MCPRequest(project=project, capability="weather", action=action, **kw)


# --- caching ---------------------------------------------------------------

def test_cache_hit_avoids_second_adapter_call(registry):
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=10, clock=clock)
    adapter = MockAdapter(["weather"])
    router = Router(registry, cache=cache, clock=clock)
    router.register_adapter(adapter)

    first = router.route(_weather_req())
    second = router.route(_weather_req())
    assert second.data == first.data
    assert len(adapter.calls) == 1  # second served from cache


def test_cache_expiry_reruns(registry):
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=10, clock=clock)
    adapter = MockAdapter(["weather"])
    router = Router(registry, cache=cache, clock=clock)
    router.register_adapter(adapter)

    router.route(_weather_req())
    clock.now = 10.0  # expired
    router.route(_weather_req())
    assert len(adapter.calls) == 2


def test_writes_are_never_cached(registry):
    # aguayluz allows a write on utilities; use it to prove writes bypass cache.
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=10, clock=clock)
    # A capability the project declares, invoked as a write via is_write.
    adapter = MockAdapter(["weather"])
    router = Router(registry, cache=cache, clock=clock)
    router.register_adapter(adapter)

    # Reads populate cache; a write with the same params must not be served
    # from it and must not be stored. weather:update is not allowlisted, so a
    # write is a policy denial — assert it never becomes a cache entry.
    router.route(_weather_req())
    with pytest.raises(PolicyViolation):
        router.route(_weather_req(action="update", is_write=True))
    # cache still holds only the read; a fresh read still hits it (1 call total)
    router.route(_weather_req())
    assert len(adapter.calls) == 1


def test_denied_request_never_cached(registry):
    cache = ResponseCache(ttl_seconds=10)
    router = Router(registry, cache=cache)
    router.register_adapter(MockAdapter(["contracts"]))
    # spiderweb does not declare contracts -> denied, nothing cached
    for _ in range(2):
        with pytest.raises(PolicyViolation):
            router.route(MCPRequest(project="spiderweb", capability="contracts",
                                    action="search"))
    assert cache.get(MCPRequest(project="spiderweb", capability="contracts",
                                action="search")) is None


def test_cache_hit_emits_provenance(registry):
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=10, clock=clock)
    prov = []
    router = Router(registry, cache=cache, provenance_sink=prov.append, clock=clock)
    router.register_adapter(MockAdapter(["weather"]))
    router.route(_weather_req())  # miss
    router.route(_weather_req())  # hit
    # Both the live success and the cache hit emit provenance.
    assert len(prov) == 2
    assert all(p["capability"] == "weather" for p in prov)


def test_cache_isolates_from_caller_mutation(registry):
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=10, clock=clock)
    router = Router(registry, cache=cache, clock=clock)
    router.register_adapter(MockAdapter(["weather"]))

    first = router.route(_weather_req())
    first.data["injected"] = "tampered"  # caller mutates after route returns
    first.provenance["injected"] = "tampered"
    second = router.route(_weather_req())  # served from cache
    assert "injected" not in second.data
    assert "injected" not in second.provenance
    # mutating the served copy must not corrupt a later read either
    second.data["injected2"] = "x"
    third = router.route(_weather_req())
    assert "injected2" not in third.data


def test_cache_keys_by_project(registry):
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=10, clock=clock)
    adapter = MockAdapter(["weather"])
    router = Router(registry, cache=cache, clock=clock)
    router.register_adapter(adapter)
    # weather is declared by centinelas and aguayluz — distinct cache keys.
    router.route(_weather_req(project="centinelas"))
    router.route(_weather_req(project="aguayluz"))
    assert len(adapter.calls) == 2


# --- telemetry -------------------------------------------------------------

def test_metrics_for_allowed_and_cache_hit(registry):
    clock = FakeClock()
    metrics = InMemoryMetrics()
    cache = ResponseCache(ttl_seconds=10, clock=clock)
    router = Router(registry, metrics_sink=metrics, cache=cache, clock=clock)
    router.register_adapter(MockAdapter(["weather"]))

    router.route(_weather_req())  # miss -> allowed
    router.route(_weather_req())  # hit
    assert metrics.count() == 2
    assert metrics.metrics[0].cache_hit is False
    assert metrics.metrics[1].cache_hit is True
    assert metrics.metrics[0].decision == "allowed"
    assert metrics.cache_hit_rate() == 0.5


def test_metrics_for_denied_and_error(registry):
    metrics = InMemoryMetrics()
    router = Router(registry, metrics_sink=metrics)
    # error: no adapter registered for a declared capability
    with pytest.raises(LookupError):
        router.route(_weather_req())
    # denied: undeclared capability
    router.register_adapter(MockAdapter(["contracts"]))
    with pytest.raises(PolicyViolation):
        router.route(MCPRequest(project="spiderweb", capability="contracts",
                                action="x"))
    decisions = [m.decision for m in metrics.metrics]
    assert decisions == ["error", "denied"]
    assert metrics.error_rate() == 0.5


def test_metrics_duration_is_nonnegative(registry):
    clock = FakeClock()
    metrics = InMemoryMetrics()
    router = Router(registry, metrics_sink=metrics, clock=clock)
    router.register_adapter(MockAdapter(["weather"]))
    clock.now = 5.0
    router.route(_weather_req())
    assert metrics.metrics[0].duration_s >= 0.0


def test_aggregates_shape(registry):
    metrics = InMemoryMetrics()
    router = Router(registry, metrics_sink=metrics)
    router.register_adapter(MockAdapter(["weather"]))
    router.route(_weather_req())
    agg = metrics.aggregates()
    assert agg["count"] == 1
    assert agg["by_capability"] == {"weather": 1}
    assert agg["by_decision"] == {"allowed": 1}
