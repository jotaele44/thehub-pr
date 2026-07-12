"""Secret-manager credential providers.

`SecretManagerProvider` implements the `auth.CredentialProvider` protocol over
an injectable `fetcher` — the boundary to a real backend (AWS Secrets Manager,
Vault, GCP Secret Manager: the operator supplies the SDK call). Tests inject a
fake fetcher, so the whole path runs offline; a live backend is operator
config and is not exercised in CI.

Fail-closed is preserved end to end: a fetcher that errors or returns nothing
yields None, so an adapter whose key can't be resolved refuses to run. Secret
values never appear in logs or reprs.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Callable, Dict, Optional, Tuple

from hub.mcp_runtime.auth import REDACTED

# A fetcher resolves a secret name to its value (or None if absent).
SecretFetcher = Callable[[str], Optional[str]]


class SecretManagerProvider:
    """CredentialProvider backed by an injectable secret-manager fetcher.

    With `ttl_seconds` set, resolved values are cached on the injected clock
    (same pattern as `auth.TokenCache`) to avoid hammering the backend; a
    fetcher error is never cached.
    """

    def __init__(
        self,
        fetcher: SecretFetcher,
        ttl_seconds: Optional[float] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetcher = fetcher
        self._ttl = ttl_seconds
        self._clock = clock
        self._cache: Dict[str, Tuple[float, str]] = {}

    def get(self, name: str) -> Optional[str]:
        if self._ttl is not None:
            entry = self._cache.get(name)
            if entry is not None and self._clock() - entry[0] < self._ttl:
                return entry[1]
        try:
            value = self._fetcher(name)
        except Exception:
            return None  # fail closed — never cache a failure
        if not value:
            return None
        if self._ttl is not None:
            self._cache[name] = (self._clock(), value)
        return value

    def __repr__(self) -> str:
        return f"SecretManagerProvider(cached_keys={sorted(self._cache)}, values={REDACTED})"


class HttpSecretManager:
    """Generic REST fetcher: GET `<base_url>/<name>` -> {"value": "..."}.

    The HTTP call is behind an injectable `getter` (real `urllib` by default),
    so tests run offline; the live `base_url` is operator config. Suitable as
    the `fetcher` for `SecretManagerProvider`.
    """

    def __init__(
        self,
        base_url: str,
        getter: Optional[Callable[[str], Dict]] = None,
        value_field: str = "value",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._getter = getter if getter is not None else self._urllib_getter
        self._value_field = value_field

    @staticmethod
    def _urllib_getter(url: str) -> Dict:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def __call__(self, name: str) -> Optional[str]:
        response = self._getter(f"{self._base_url}/{name}")
        if not isinstance(response, dict):
            return None
        value = response.get(self._value_field)
        return value if value else None

    def __repr__(self) -> str:
        return f"HttpSecretManager(base_url={self._base_url!r})"
