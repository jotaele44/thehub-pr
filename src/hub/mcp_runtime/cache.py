"""Response cache — a TTL memory cache for read-only MCP results.

Keyed by (project, capability, action, canonical params) so a cached result
is only ever served to an identical request from the same project (its
provenance already reflects that project). The router is responsible for
never caching writes and never consulting the cache for a policy-denied
request; the cache itself is policy-agnostic.

Time comes from an injected clock (default `time.monotonic`), mirroring
`auth.TokenCache`, so tests are deterministic.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, Optional, Tuple

from hub.mcp_runtime.sdk import AdapterResult, MCPRequest

_Key = Tuple[str, str, str, str]


def _canonical(params: Dict[str, Any]) -> str:
    return json.dumps(params, sort_keys=True, default=str)


class ResponseCache:
    def __init__(
        self,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        max_entries: int = 512,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._max = max_entries
        # insertion-ordered dict: key -> (stored_at, result)
        self._store: Dict[_Key, Tuple[float, AdapterResult]] = {}

    def _key(self, request: MCPRequest) -> _Key:
        return (
            request.project,
            request.capability,
            request.action,
            _canonical(request.params),
        )

    def get(self, request: MCPRequest) -> Optional[AdapterResult]:
        key = self._key(request)
        entry = self._store.get(key)
        if entry is None:
            return None
        stored_at, result = entry
        if self._clock() - stored_at >= self._ttl:
            self._store.pop(key, None)
            return None
        return result

    def put(self, request: MCPRequest, result: AdapterResult) -> None:
        key = self._key(request)
        # Refresh position on overwrite so recency reflects last write.
        self._store.pop(key, None)
        self._store[key] = (self._clock(), result)
        while len(self._store) > self._max:
            oldest = next(iter(self._store))
            self._store.pop(oldest, None)

    def clear(self) -> None:
        self._store.clear()
