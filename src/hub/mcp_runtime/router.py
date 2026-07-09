"""Router — resolve capability requests to adapters through the policy gate."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from hub.mcp_runtime.policy import PolicyEngine
from hub.mcp_runtime.registry import RuntimeRegistry
from hub.mcp_runtime.sdk import AdapterResult, MCPAdapter, MCPRequest


class Router:
    """Capability -> adapter resolution and gated execution.

    Every request traverses: manifest/policy check -> adapter resolution ->
    adapter validate/execute -> provenance-stamped result. An optional
    provenance_sink receives every result's provenance block (the runtime's
    audit hook).
    """

    def __init__(
        self,
        registry: RuntimeRegistry,
        policy: Optional[PolicyEngine] = None,
        provenance_sink: Optional[Callable[[Dict], None]] = None,
    ) -> None:
        self.registry = registry
        self.policy = policy or PolicyEngine(registry)
        self.provenance_sink = provenance_sink
        self._adapters: Dict[str, List[MCPAdapter]] = {}

    def register_adapter(self, adapter: MCPAdapter) -> None:
        if not adapter.health_check():
            raise ValueError(f"adapter {adapter.name()!r} failed health check")
        for capability in adapter.capabilities():
            self._adapters.setdefault(capability, []).append(adapter)

    def resolve(self, capability: str) -> MCPAdapter:
        adapters = self._adapters.get(capability, [])
        if not adapters:
            raise LookupError(f"no adapter registered for capability {capability!r}")
        return adapters[0]

    def route(self, request: MCPRequest) -> AdapterResult:
        self.policy.check(request)
        adapter = self.resolve(request.capability)
        result = adapter.run(request)
        capability = self.registry.capabilities.get(request.capability)
        if capability is not None:
            result.provenance["version_pin"] = capability.version_pin
        if self.provenance_sink is not None:
            self.provenance_sink(dict(result.provenance))
        return result
