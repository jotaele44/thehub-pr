import pytest

from hub.mcp_runtime import (
    ChainCredentialProvider,
    EnvCredentialProvider,
    MCPRequest,
    Router,
    RuntimeRegistry,
    StaticCredentialProvider,
    TokenCache,
    redact,
)
from hub.mcp_runtime.adapters import ContractsAdapter


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append((url, dict(params or {})))
        return self.payload


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now


CONTRACTS_PARAMS = {
    "keyword": "recovery",
    "posted_from": "01/01/2026",
    "posted_to": "03/01/2026",
}


# --- providers --------------------------------------------------------------

def test_env_provider(monkeypatch):
    monkeypatch.setenv("MCP_TEST_KEY", "v1")
    assert EnvCredentialProvider().get("MCP_TEST_KEY") == "v1"
    monkeypatch.delenv("MCP_TEST_KEY")
    assert EnvCredentialProvider().get("MCP_TEST_KEY") is None


def test_static_provider():
    provider = StaticCredentialProvider({"A": "1", "EMPTY": ""})
    assert provider.get("A") == "1"
    assert provider.get("EMPTY") is None  # empty value is not a credential
    assert provider.get("MISSING") is None


def test_chain_provider_first_hit_wins():
    chain = ChainCredentialProvider([
        StaticCredentialProvider({"A": ""}),          # empty -> skipped
        StaticCredentialProvider({"A": "second"}),
        StaticCredentialProvider({"A": "third"}),
    ])
    assert chain.get("A") == "second"
    assert chain.get("B") is None


# --- token cache -------------------------------------------------------------

def test_token_cache_serves_within_ttl_then_refreshes():
    clock = FakeClock()
    refreshes = []

    def refresh(name):
        refreshes.append(name)
        return "refreshed"

    cache = TokenCache(
        StaticCredentialProvider({"K": "orig"}),
        ttl_seconds=10, refresh=refresh, clock=clock,
    )
    assert cache.get("K") == "orig"
    clock.now = 9.0
    assert cache.get("K") == "orig"
    assert refreshes == []
    clock.now = 10.0  # expired
    assert cache.get("K") == "refreshed"
    assert refreshes == ["K"]
    clock.now = 15.0  # refreshed value now cached
    assert cache.get("K") == "refreshed"
    assert refreshes == ["K"]


def test_token_cache_fails_closed_on_refresh_failure():
    clock = FakeClock()

    def bad_refresh(name):
        raise RuntimeError("upstream down")

    cache = TokenCache(
        StaticCredentialProvider({"K": "orig"}),
        ttl_seconds=5, refresh=bad_refresh, clock=clock,
    )
    assert cache.get("K") == "orig"
    clock.now = 6.0
    assert cache.get("K") is None  # stale value dropped, fail closed


def test_expired_cache_fails_adapter_closed_end_to_end():
    clock = FakeClock()
    cache = TokenCache(
        StaticCredentialProvider({"MCP_CONTRACTS_API_KEY": "tok"}),
        ttl_seconds=5, refresh=lambda name: None, clock=clock,
    )
    router = Router(RuntimeRegistry())
    router.register_adapter(
        ContractsAdapter(client=FakeClient({}), credentials=cache)
    )
    request = MCPRequest(
        project="moneysweep", capability="contracts", action="search",
        params=dict(CONTRACTS_PARAMS),
    )
    assert router.route(request).status == "ok"  # fresh token works
    clock.now = 6.0  # token expired, refresh yields nothing
    with pytest.raises(PermissionError, match="authenticate"):
        router.route(request)


# --- adapter wiring ----------------------------------------------------------

def test_adapter_uses_injected_provider_without_env(monkeypatch):
    monkeypatch.delenv("MCP_CONTRACTS_API_KEY", raising=False)
    client = FakeClient({"opportunitiesData": [{"noticeId": "x"}]})
    router = Router(RuntimeRegistry())
    router.register_adapter(
        ContractsAdapter(
            client=client,
            credentials=StaticCredentialProvider(
                {"MCP_CONTRACTS_API_KEY": "INJECTED"}
            ),
        )
    )
    result = router.route(
        MCPRequest(
            project="moneysweep", capability="contracts", action="search",
            params=dict(CONTRACTS_PARAMS),
        )
    )
    assert result.data["count"] == 1
    assert client.calls[0][1]["api_key"] == "INJECTED"
    assert "INJECTED" not in str(result.provenance)


# --- redaction ---------------------------------------------------------------

def test_redact_and_reprs_never_reveal_values():
    assert redact("supersecret") == "***"
    assert redact(None) == ""
    provider = StaticCredentialProvider({"K": "supersecret"})
    cache = TokenCache(provider, ttl_seconds=60)
    cache.get("K")
    assert "supersecret" not in repr(provider)
    assert "supersecret" not in repr(cache)
    assert "K" in repr(cache)  # key names are fine, values are not
