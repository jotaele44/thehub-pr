"""OAuth2 client-credentials refresh for the credential layer.

`OAuth2ClientCredentials` is a refresh callable for `auth.TokenCache`: it
performs an OAuth2 client-credentials grant and returns the access token,
so an adapter that needs a bearer token gets it refreshed on TTL expiry
without the repo ever holding a long-lived secret.

Everything external is behind an injectable `poster`, so tests exercise the
whole flow offline. Pointing this at a real IdP `token_url` is operator
config; the live exchange is not verified in CI. The client id/secret come
from a `CredentialProvider` (environment by default), never the repo, and are
never logged.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Optional

from hub.mcp_runtime.auth import CredentialProvider, EnvCredentialProvider

# A poster takes (url, form-fields) and returns the parsed JSON response.
Poster = Callable[[str, Dict[str, str]], Dict[str, Any]]


def _urllib_poster(url: str, data: Dict[str, str]) -> Dict[str, Any]:
    body = urllib.parse.urlencode(data).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


class OAuth2ClientCredentials:
    """Refresh callable performing an OAuth2 client-credentials grant.

    Usage::

        refresh = OAuth2ClientCredentials(
            token_url="https://idp.example/oauth/token",
            client_id_key="MCP_FOO_CLIENT_ID",
            client_secret_key="MCP_FOO_CLIENT_SECRET",
        )
        cache = TokenCache(EnvCredentialProvider(), ttl_seconds=3000,
                           refresh=refresh)

    Fails closed (returns None) if the client id/secret are unresolved or the
    token exchange raises / omits an access token.
    """

    def __init__(
        self,
        token_url: str,
        client_id_key: str,
        client_secret_key: str,
        scope: Optional[str] = None,
        credentials: Optional[CredentialProvider] = None,
        poster: Optional[Poster] = None,
    ) -> None:
        self._token_url = token_url
        self._client_id_key = client_id_key
        self._client_secret_key = client_secret_key
        self._scope = scope
        self._credentials: CredentialProvider = (
            credentials if credentials is not None else EnvCredentialProvider()
        )
        self._poster: Poster = poster if poster is not None else _urllib_poster

    def __call__(self, name: str) -> Optional[str]:
        client_id = self._credentials.get(self._client_id_key)
        client_secret = self._credentials.get(self._client_secret_key)
        if not client_id or not client_secret:
            return None  # fail closed — no usable client credentials
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if self._scope:
            data["scope"] = self._scope
        try:
            response = self._poster(self._token_url, data)
        except Exception:
            return None
        token = response.get("access_token") if isinstance(response, dict) else None
        return token or None

    def __repr__(self) -> str:
        return (
            f"OAuth2ClientCredentials(token_url={self._token_url!r}, "
            f"client_id_key={self._client_id_key!r})"
        )
