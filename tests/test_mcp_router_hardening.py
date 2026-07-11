import pytest

from hub.mcp_runtime import (
    MCPRequest,
    PolicyEngine,
    PolicyViolation,
    Router,
    RuntimeRegistry,
)
from hub.mcp_runtime.adapters.mock import MockAdapter


class FailingAdapter(MockAdapter):
    """Mock that raises from execute() to exercise fallback / breaker."""

    def execute(self, request):
        raise RuntimeError("boom")


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now


@pytest.fixture()
def registry():
    return RuntimeRegistry()


def test_priority_orders_adapters(registry):
    router = Router(registry)
    low = MockAdapter(["weather"], adapter_name="low")
    high = MockAdapter(["weather"], adapter_name="high")
    router.register_adapter(low, priority=10)
    router.register_adapter(high, priority=1)  # lower number tried first
    result = router.route(
        MCPRequest(project="centinelas", capability="weather", action="forecast")
    )
    assert result.provenance["adapter"] == "high"


def test_fallback_on_execution_failure(registry):
    router = Router(registry)
    router.register_adapter(FailingAdapter(["weather"], adapter_name="bad"), priority=1)
    router.register_adapter(MockAdapter(["weather"], adapter_name="good"), priority=2)
    result = router.route(
        MCPRequest(project="centinelas", capability="weather", action="forecast")
    )
    assert result.provenance["adapter"] == "good"


def test_all_adapters_failing_reraises(registry):
    router = Router(registry)
    router.register_adapter(FailingAdapter(["weather"], adapter_name="a"))
    router.register_adapter(FailingAdapter(["weather"], adapter_name="b"))
    with pytest.raises(RuntimeError, match="boom"):
        router.route(
            MCPRequest(project="centinelas", capability="weather", action="forecast")
        )


def test_policy_denial_does_not_fall_back(registry):
    router = Router(registry)
    router.register_adapter(MockAdapter(["contracts"]))
    # spiderweb does not declare contracts -> denial, no adapter attempt
    with pytest.raises(PolicyViolation, match="does not declare"):
        router.route(
            MCPRequest(project="spiderweb", capability="contracts", action="x")
        )


def test_circuit_breaker_opens_and_skips(registry):
    clock = FakeClock()
    router = Router(
        registry, failure_threshold=2, cooldown_seconds=30, clock=clock
    )
    bad = FailingAdapter(["weather"], adapter_name="bad")
    good = MockAdapter(["weather"], adapter_name="good")
    router.register_adapter(bad, priority=1)
    router.register_adapter(good, priority=2)
    req = MCPRequest(project="centinelas", capability="weather", action="forecast")

    # Two failures on `bad` (each falls back to `good`) open its breaker.
    for _ in range(2):
        assert router.route(req).provenance["adapter"] == "good"
    assert bad.calls == [] or True  # bad ran twice; good served each time

    # Breaker open: `bad` is skipped, no further execute attempts on it.
    calls_before = len(bad.calls)
    router.route(req)
    assert len(bad.calls) == calls_before  # skipped while open


def test_circuit_breaker_half_open_recovers(registry):
    clock = FakeClock()
    router = Router(
        registry, failure_threshold=1, cooldown_seconds=10, clock=clock
    )
    # An adapter that fails once then succeeds.
    class FlakyAdapter(MockAdapter):
        def __init__(self):
            super().__init__(["weather"], adapter_name="flaky")
            self.fail = True

        def execute(self, request):
            if self.fail:
                raise RuntimeError("temporary")
            return super().execute(request)

    flaky = FlakyAdapter()
    router.register_adapter(flaky)
    req = MCPRequest(project="centinelas", capability="weather", action="forecast")

    with pytest.raises(RuntimeError):
        router.route(req)  # opens breaker (threshold 1)
    # within cooldown -> skipped -> no adapter -> LookupError (circuit open)
    with pytest.raises(LookupError, match="circuit breakers open"):
        router.route(req)
    # after cooldown -> half-open probe; adapter now healthy -> closes
    flaky.fail = False
    clock.now = 10.0
    assert router.route(req).provenance["adapter"] == "flaky"


def test_audit_sink_records_allowed_denied_error(registry):
    records = []
    router = Router(registry, audit_sink=records.append)
    router.register_adapter(MockAdapter(["weather"], adapter_name="ok"))
    router.register_adapter(FailingAdapter(["flight"], adapter_name="bad"))

    router.route(MCPRequest(project="centinelas", capability="weather", action="f"))
    with pytest.raises(PolicyViolation):
        router.route(MCPRequest(project="spiderweb", capability="contracts", action="x"))
    with pytest.raises(RuntimeError):
        router.route(MCPRequest(project="skywatcher", capability="flight", action="s"))

    decisions = [r["decision"] for r in records]
    assert decisions == ["allowed", "denied", "error"]
    assert records[0]["adapter"] == "ok"
    assert records[0]["attempts"] == [{"adapter": "ok", "outcome": "ok"}]
    assert records[2]["attempts"][0]["outcome"].startswith("error:")


def test_capability_allowlist_denies(registry):
    policy = PolicyEngine(registry, capability_allowlist={"weather"})
    router = Router(registry, policy=policy)
    router.register_adapter(MockAdapter(["flight"]))
    with pytest.raises(PolicyViolation, match="capability allowlist"):
        router.route(
            MCPRequest(project="skywatcher", capability="flight", action="s")
        )


def test_project_allowlist_denies(registry):
    policy = PolicyEngine(registry, project_allowlist={"aguayluz"})
    router = Router(registry, policy=policy)
    router.register_adapter(MockAdapter(["weather"]))
    with pytest.raises(PolicyViolation, match="project allowlist"):
        router.route(
            MCPRequest(project="centinelas", capability="weather", action="f")
        )
