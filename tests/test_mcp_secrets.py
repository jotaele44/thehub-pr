from hub.mcp_runtime import (
    ChainCredentialProvider,
    EnvCredentialProvider,
    HttpSecretManager,
    SecretManagerProvider,
)


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now


def test_provider_resolves_and_misses():
    provider = SecretManagerProvider(lambda name: {"A": "1"}.get(name))
    assert provider.get("A") == "1"
    assert provider.get("MISSING") is None


def test_provider_fails_closed_on_fetcher_error():
    def boom(name):
        raise RuntimeError("backend down")

    assert SecretManagerProvider(boom).get("A") is None


def test_provider_ttl_cache_hit_then_expiry():
    clock = FakeClock()
    calls = {"n": 0}

    def fetcher(name):
        calls["n"] += 1
        return f"v{calls['n']}"

    provider = SecretManagerProvider(fetcher, ttl_seconds=10, clock=clock)
    assert provider.get("A") == "v1"
    clock.now = 9.0
    assert provider.get("A") == "v1"  # cached
    assert calls["n"] == 1
    clock.now = 10.0
    assert provider.get("A") == "v2"  # expired -> refetched
    assert calls["n"] == 2


def test_error_is_not_cached():
    clock = FakeClock()
    state = {"fail": True}

    def fetcher(name):
        if state["fail"]:
            raise RuntimeError("transient")
        return "ok"

    provider = SecretManagerProvider(fetcher, ttl_seconds=100, clock=clock)
    assert provider.get("A") is None
    state["fail"] = False
    assert provider.get("A") == "ok"  # not stuck on a cached failure


def test_repr_has_no_values():
    provider = SecretManagerProvider(lambda n: "supersecret", ttl_seconds=100)
    provider.get("A")
    assert "supersecret" not in repr(provider)
    assert "A" in repr(provider)


def test_chain_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("MY_KEY", "from-env")
    chain = ChainCredentialProvider([
        SecretManagerProvider(lambda name: None),  # backend has nothing
        EnvCredentialProvider(),
    ])
    assert chain.get("MY_KEY") == "from-env"


def test_http_secret_manager_via_fake_getter():
    seen = []

    def getter(url):
        seen.append(url)
        return {"value": "sekret"}

    fetcher = HttpSecretManager("https://vault.example/v1/", getter=getter)
    provider = SecretManagerProvider(fetcher)
    assert provider.get("db/password") == "sekret"
    assert seen == ["https://vault.example/v1/db/password"]
