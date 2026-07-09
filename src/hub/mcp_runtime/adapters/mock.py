"""Mock adapter — reference SDK implementation used by the runtime tests."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from hub.mcp_runtime.sdk import MCPAdapter, MCPRequest


class MockAdapter(MCPAdapter):
    """Serves any configured capabilities and echoes the request back."""

    def __init__(
        self,
        served_capabilities: List[str],
        adapter_name: str = "mock",
        healthy: bool = True,
        write_actions: Optional[List[str]] = None,
        authenticated: bool = True,
    ) -> None:
        self._capabilities = list(served_capabilities)
        self._name = adapter_name
        self._healthy = healthy
        self._write_actions = list(write_actions or [])
        self._authenticated = authenticated
        self.calls: List[MCPRequest] = []

    def name(self) -> str:
        return self._name

    def version(self) -> str:
        return "0.1.0"

    def capabilities(self) -> List[str]:
        return list(self._capabilities)

    def health_check(self) -> bool:
        return self._healthy

    def authenticate(self) -> bool:
        return self._authenticated

    def write_actions(self) -> List[str]:
        return list(self._write_actions)

    def execute(self, request: MCPRequest) -> Dict[str, Any]:
        self.calls.append(request)
        return {"echo": {"action": request.action, "params": request.params}}
