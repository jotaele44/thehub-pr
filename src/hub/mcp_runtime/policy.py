"""Policy engine — enforces the governance rules at request time."""

from __future__ import annotations

from hub.mcp_runtime.registry import RuntimeRegistry
from hub.mcp_runtime.sdk import MCPRequest


class PolicyViolation(Exception):
    """Raised when a request breaks a federation governance rule."""


class PolicyEngine:
    """Runtime enforcement of the rules the static validators check in CI.

    - A project may only invoke capabilities its manifest declares.
    - Write actions are denied unless explicitly allowlisted in the
      project's write_policy.allowed_writes (read_only default).
    - Deprecated capabilities are never routable.
    """

    def __init__(self, registry: RuntimeRegistry) -> None:
        self.registry = registry

    def check(self, request: MCPRequest) -> None:
        manifest = self.registry.manifest_for(request.project)

        if request.capability not in manifest.declared:
            raise PolicyViolation(
                f"project {request.project!r} does not declare capability "
                f"{request.capability!r}"
            )

        capability = self.registry.capabilities.get(request.capability)
        if capability is not None and capability.status == "deprecated":
            raise PolicyViolation(
                f"capability {request.capability!r} is deprecated and not "
                f"routable"
            )

        if request.is_write:
            if manifest.write_default == "write_disabled":
                raise PolicyViolation(
                    f"project {request.project!r} has writes disabled"
                )
            write_key = f"{request.capability}:{request.action}"
            if write_key not in manifest.allowed_writes:
                raise PolicyViolation(
                    f"write action {write_key!r} is not in "
                    f"{request.project!r}'s allowed_writes (default is "
                    f"{manifest.write_default!r})"
                )
