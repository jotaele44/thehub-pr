"""Credential provisioning for MCP adapters.

Adapters never read secrets from the repository; they resolve them at
runtime through a `CredentialProvider`. The production default is the
process environment; tests and local wiring inject other providers. A
`TokenCache` adds TTL/refresh semantics with an injected refresh callable
and clock, so nothing here performs a live OAuth flow — that callable is
the seam a real flow plugs into later.

Fail-closed is the rule end to end: a provider that cannot resolve a name
returns None, `BaseHttpAdapter.authenticate()` then returns False, and
`MCPAdapter.run()` raises before `execute()` is ever reached. Secret values
never appear in provenance blocks, logs, or reprs.
"""

from __future__ import annotations

import os
import time
from typing import Callable, Dict, Iterable, List, Optional, Protocol

REDACTED = "***"


def redact(value: Optional[str]) -> str:
    """Constant-shape masking for any log/diagnostic path."""
    return REDACTED if value else ""


class CredentialProvider(Protocol):
    """Resolve a named credential to its value, or None if unavailable."""

    def get(self, name: str) -> Optional[str]:
        ...


class EnvCredentialProvider:
    """Reads credentials from the process environment (production default)."""

    def get(self, name: str) -> Optional[str]:
        value = os.environ.get(name)
        return value if value else None

    def __repr__(self) -> str:
        return "EnvCredentialProvider()"


class StaticCredentialProvider:
    """In-memory provider for tests and local development wiring.

    Values must be injected at runtime (constructed from env/config the
    caller controls) — never committed to the repository.
    """

    def __init__(self, mapping: Dict[str, str]) -> None:
        self._mapping = dict(mapping)

    def get(self, name: str) -> Optional[str]:
        value = self._mapping.get(name)
        return value if value else None

    def __repr__(self) -> str:
        keys = ", ".join(sorted(self._mapping))
        return f"StaticCredentialProvider(keys=[{keys}], values={REDACTED})"


class ChainCredentialProvider:
    """Asks each provider in order; the first non-empty answer wins."""

    def __init__(self, providers: Iterable[CredentialProvider]) -> None:
        self._providers: List[CredentialProvider] = list(providers)

    def get(self, name: str) -> Optional[str]:
        for provider in self._providers:
            value = provider.get(name)
            if value:
                return value
        return None

    def __repr__(self) -> str:
        return f"ChainCredentialProvider({self._providers!r})"


class TokenCache:
    """TTL cache over a provider, with an injected refresh hook.

    Serves the resolved value until `ttl_seconds` elapses on the injected
    `clock` (default `time.monotonic`), then calls `refresh(name)` for a new
    value — the seam a real OAuth/rotation flow implements. A refresh that
    raises or returns empty fails closed: the stale value is dropped and
    None is returned.
    """

    def __init__(
        self,
        provider: CredentialProvider,
        ttl_seconds: float,
        refresh: Optional[Callable[[str], Optional[str]]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._provider = provider
        self._ttl = ttl_seconds
        self._refresh = refresh
        self._clock = clock
        self._values: Dict[str, str] = {}
        self._fetched_at: Dict[str, float] = {}

    def _store(self, name: str, value: Optional[str]) -> Optional[str]:
        if value:
            self._values[name] = value
            self._fetched_at[name] = self._clock()
            return value
        self._values.pop(name, None)
        self._fetched_at.pop(name, None)
        return None

    def get(self, name: str) -> Optional[str]:
        now = self._clock()
        if name in self._values and now - self._fetched_at[name] < self._ttl:
            return self._values[name]
        if name in self._values:
            # Expired: refresh if we can, otherwise fail closed.
            if self._refresh is None:
                return self._store(name, self._provider.get(name))
            try:
                return self._store(name, self._refresh(name))
            except Exception:
                return self._store(name, None)
        return self._store(name, self._provider.get(name))

    def __repr__(self) -> str:
        keys = ", ".join(sorted(self._values))
        return f"TokenCache(ttl={self._ttl}, keys=[{keys}], values={REDACTED})"
