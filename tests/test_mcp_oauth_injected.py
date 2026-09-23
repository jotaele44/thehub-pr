import pytest

from hub.mcp_runtime import (
    MCPRequest,
    OAuth2ClientCredentials,
    Router,
    RuntimeRegistry,
    StaticCredentialProvider,
    TokenCache,
)
from hub.mcp_runtime.adapters import GithubBridgeAdapter


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now


# --- OAuth2 client-credentials refresh -------------------------------------

def test_oauth_returns_access_token():
    posts = []

    def poster(url, data):
        posts.append((url, data))
        return {"access_token": "tok-123", "expires_in": 3600}

    refresh = OAuth2ClientCredentials(
        token_url="https://idp.example/token",
        client_id_key="CID", client_secret_key="CSECRET",
        scope="mcp.read",
        credentials=StaticCredentialProvider({"CID": "id", "CSECRET": "sh"}),
        poster=poster,
    )
    assert refresh("anything") == "tok-123"
    url, data = posts[0]
    assert url == "https://idp.example/token"
    assert data["grant_type"] == "client_credentials"
    assert data["client_id"] == "id" and data["client_secret"] == "sh"
    assert data["scope"] == "mcp.read"


def test_oauth_fails_closed_without_client_credentials():
    refresh = OAuth2ClientCredentials(
        token_url="https://idp.example/token",
        client_id_key="CID", client_secret_key="CSECRET",
        credentials=StaticCredentialProvider({}),  # nothing configured
        poster=lambda url, data: {"access_token": "should-not-happen"},
    )
    assert refresh("x") is None


def test_oauth_fails_closed_on_poster_error():
    def boom(url, data):
        raise RuntimeError("idp down")

    refresh = OAuth2ClientCredentials(
        token_url="https://idp.example/token",
        client_id_key="CID", client_secret_key="CSECRET",
        credentials=StaticCredentialProvider({"CID": "id", "CSECRET": "sh"}),
        poster=boom,
    )
    assert refresh("x") is None


def test_oauth_through_token_cache_refreshes_on_expiry():
    clock = FakeClock()
    calls = {"n": 0}

    def poster(url, data):
        calls["n"] += 1
        return {"access_token": f"tok-{calls['n']}"}

    refresh = OAuth2ClientCredentials(
        token_url="https://idp.example/token",
        client_id_key="CID", client_secret_key="CSECRET",
        credentials=StaticCredentialProvider({"CID": "id", "CSECRET": "sh"}),
        poster=poster,
    )
    # Base provider seeds an initial token; on TTL expiry the cache calls the
    # OAuth refresh for a new one.
    cache = TokenCache(
        StaticCredentialProvider({"BEARER": "initial"}),
        ttl_seconds=100, refresh=refresh, clock=clock,
    )
    assert cache.get("BEARER") == "initial"  # cold miss seeds from provider
    assert calls["n"] == 0
    clock.now = 100.0  # expired -> OAuth refresh runs
    assert cache.get("BEARER") == "tok-1"
    assert calls["n"] == 1


def test_oauth_repr_has_no_secret():
    refresh = OAuth2ClientCredentials(
        token_url="https://idp.example/token",
        client_id_key="CID", client_secret_key="CSECRET",
        credentials=StaticCredentialProvider({"CID": "id", "CSECRET": "supersecret"}),
        poster=lambda u, d: {"access_token": "t"},
    )
    assert "supersecret" not in repr(refresh)


# --- networked github-bridge fetch -----------------------------------------

@pytest.fixture()
def router():
    return Router(RuntimeRegistry())


def test_github_fetch_clones_via_injected_runner(router, tmp_path):
    ran = []

    def fake_runner(cmd, cwd=None):
        ran.append(list(cmd))

    router.register_adapter(GithubBridgeAdapter(runner=fake_runner))
    dest = tmp_path / "checkout"
    result = router.route(MCPRequest(
        project="skywatcher", capability="github-bridge", action="fetch",
        params={"program_id": "ovnis-pr", "dest": str(dest)},
    ))
    assert result.data["result"] == "cloned"
    assert result.data["repo"] == "jotaele44/ovnis-pr"
    # the injected runner saw a real git clone argv — no network touched
    assert ran and ran[0][0] == "git" and ran[0][1] == "clone"
    assert "https://github.com/jotaele44/ovnis-pr.git" in ran[0]


def test_github_fetch_pulls_when_checkout_exists(router, tmp_path):
    ran = []
    dest = tmp_path / "checkout"
    (dest / ".git").mkdir(parents=True)  # looks like an existing clone

    router.register_adapter(GithubBridgeAdapter(runner=lambda cmd, cwd=None: ran.append(list(cmd))))
    result = router.route(MCPRequest(
        project="skywatcher", capability="github-bridge", action="fetch",
        params={"program_id": "ovnis-pr", "dest": str(dest)},
    ))
    assert result.data["result"] == "pulled"
    assert ran[0][:3] == ["git", "-C", str(dest)]


def test_github_fetch_unknown_program_id(router, tmp_path):
    router.register_adapter(GithubBridgeAdapter(runner=lambda cmd, cwd=None: None))
    with pytest.raises(LookupError, match="no producer"):
        router.route(MCPRequest(
            project="skywatcher", capability="github-bridge", action="fetch",
            params={"program_id": "nope-pr", "dest": str(tmp_path / "x")},
        ))


def test_github_fetch_requires_params(router):
    router.register_adapter(GithubBridgeAdapter(runner=lambda cmd, cwd=None: None))
    with pytest.raises(ValueError, match="requires"):
        router.route(MCPRequest(
            project="skywatcher", capability="github-bridge", action="fetch",
            params={"program_id": "ovnis-pr"},  # missing dest
        ))
