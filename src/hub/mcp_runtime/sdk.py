"""Adapter SDK — the single contract every MCP adapter implements."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MCPRequest:
    """One capability invocation from a project, as seen by the runtime."""

    project: str
    capability: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    is_write: bool = False


@dataclass
class AdapterResult:
    """Standardized adapter response with mandatory provenance."""

    data: Any
    adapter: str
    adapter_version: str
    capability: str
    provenance: Dict[str, Any]
    status: str = "ok"


class MCPAdapter(abc.ABC):
    """Base contract for all MCP adapters.

    Adapters are bounded, versioned integrations — never authorities.
    Every adapter must be able to describe itself (name/version/
    capabilities), report health, validate a request before executing it,
    and stamp provenance on everything it returns.
    """

    @abc.abstractmethod
    def name(self) -> str:
        """Stable adapter identifier."""

    @abc.abstractmethod
    def version(self) -> str:
        """Adapter implementation version (semver string)."""

    @abc.abstractmethod
    def capabilities(self) -> List[str]:
        """Registry capability names this adapter serves."""

    def health_check(self) -> bool:
        """Cheap liveness probe; override for adapters with real backends."""
        return True

    def authenticate(self) -> bool:
        """Acquire/refresh credentials. Default: nothing to authenticate.

        Credential material is never read from the repository; adapters that
        need secrets must source them from the environment at runtime.
        """
        return True

    def validate(self, request: MCPRequest) -> Optional[str]:
        """Return an error message if the request is malformed, else None."""
        if request.capability not in self.capabilities():
            return (
                f"adapter {self.name()!r} does not serve capability "
                f"{request.capability!r}"
            )
        return None

    @abc.abstractmethod
    def execute(self, request: MCPRequest) -> Any:
        """Perform the request and return raw result data."""

    def provenance(self, request: MCPRequest) -> Dict[str, Any]:
        """Base provenance block; adapters extend with source-level lineage."""
        return {
            "adapter": self.name(),
            "adapter_version": self.version(),
            "capability": request.capability,
            "project": request.project,
            "action": request.action,
        }

    def run(self, request: MCPRequest) -> AdapterResult:
        """Validate, execute, and wrap with provenance."""
        error = self.validate(request)
        if error:
            raise ValueError(error)
        data = self.execute(request)
        return AdapterResult(
            data=data,
            adapter=self.name(),
            adapter_version=self.version(),
            capability=request.capability,
            provenance=self.provenance(request),
        )
