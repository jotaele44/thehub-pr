"""Policy engine — enforces the governance rules at request time."""

from __future__ import annotations

from typing import Optional, Set

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
    - Optional deployment-level allowlists further restrict which projects
      and capabilities are routable at all (None = allow all, the default).
    """

    def __init__(
        self,
        registry: RuntimeRegistry,
        capability_allowlist: Optional[Set[str]] = None,
        project_allowlist: Optional[Set[str]] = None,
    ) -> None:
        self.registry = registry
        self.capability_allowlist = capability_allowlist
        self.project_allowlist = project_allowlist

    def check_access(self, request: MCPRequest) -> None:
        """Declaration and lifecycle checks (independent of write status)."""
        if (
            self.project_allowlist is not None
            and request.project not in self.project_allowlist
        ):
            raise PolicyViolation(
                f"project {request.project!r} is not in the deployment "
                f"project allowlist"
            )
        if (
            self.capability_allowlist is not None
            and request.capability not in self.capability_allowlist
        ):
            raise PolicyViolation(
                f"capability {request.capability!r} is not in the deployment "
                f"capability allowlist"
            )

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

    def check_write(self, request: MCPRequest, is_write: bool) -> None:
        """Write-allowlist check.

        is_write is supplied by the router from the resolved adapter's own
        write_actions() declaration (OR-ed with the caller's flag), never
        from the request alone — a caller can escalate a request to write
        scrutiny but can never downgrade a declared write to a read.
        """
        if not is_write:
            return
        manifest = self.registry.manifest_for(request.project)
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

    def check(self, request: MCPRequest) -> None:
        """Full check using only request-carried write intent. Prefer the
        router path, which derives write status from adapter metadata."""
        self.check_access(request)
        self.check_write(request, request.is_write)
