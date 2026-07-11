"""HTTP plumbing shared by the domain adapters.

`EnvHttpClient` is the *only* place network access lives; every domain adapter
takes an injectable `HttpClient` (mirroring `hub.fetch.clone_or_pull`'s
injectable `runner`) so tests and CI run fully offline with a fake client.

Credentials are sourced from environment variables at runtime, never from the
repo, and never appear in a result's provenance block.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Protocol

from hub.mcp_runtime.sdk import MCPAdapter, MCPRequest


class HttpClient(Protocol):
    """Minimal read-only HTTP contract the domain adapters depend on."""

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...


class EnvHttpClient:
    """Default client — performs a real JSON GET only when actually invoked.

    Construction touches no network; nothing here runs during import or in a
    hermetic test that injects its own client.
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query = "?" + urllib.parse.urlencode(params) if params else ""
        request = urllib.request.Request(
            url + query, headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            return json.loads(response.read().decode("utf-8"))


class BaseHttpAdapter(MCPAdapter):
    """Common base for read-only, HTTP-backed domain adapters.

    Subclasses set the class attributes below and implement `execute`, calling
    `self._get(path, params)`. All domain adapters are read-only
    (`write_actions()` stays empty).
    """

    capability_name: str = ""
    adapter_name: str = ""
    upstream: str = ""
    base_url: str = ""
    # Name of the env var holding a required credential, or None if the
    # upstream is keyless. When set, the value is appended to outgoing query
    # params under `auth_param_name` and the adapter fails closed if absent.
    env_key: Optional[str] = None
    auth_param_name: Optional[str] = None

    def __init__(
        self,
        client: Optional[HttpClient] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._client: HttpClient = client if client is not None else EnvHttpClient()
        if base_url is not None:
            self.base_url = base_url

    def name(self) -> str:
        return self.adapter_name

    def version(self) -> str:
        return "0.1.0"

    def capabilities(self) -> List[str]:
        return [self.capability_name]

    def authenticate(self) -> bool:
        # Credentials come from the environment, never the repo. A declared
        # env_key that is unset makes the adapter fail closed (run() raises).
        if self.env_key is None:
            return True
        return bool(os.environ.get(self.env_key))

    def _request(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """GET an absolute URL, injecting the credential when configured."""
        merged: Dict[str, Any] = dict(params or {})
        if self.env_key and self.auth_param_name:
            secret = os.environ.get(self.env_key)
            if secret:
                merged[self.auth_param_name] = secret
        return self._client.get(url, merged)

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET a path under this adapter's `base_url`."""
        return self._request(self.base_url + path, params)

    def provenance(self, request: MCPRequest) -> Dict[str, Any]:
        block = super().provenance(request)
        # upstream/endpoint only — never the outgoing params, which may carry
        # the injected credential.
        block["upstream"] = self.upstream
        block["endpoint"] = self.base_url
        return block
