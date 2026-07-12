"""MCP federation runtime — capability routing over the governance registry.

This package is the execution counterpart to the static governance layer
(mcp/registry, mcp/manifests, schemas/federation): it loads the capability
registry and project manifests, resolves capabilities to registered
adapters, enforces the read-only/write policy at request time, and stamps
provenance on every result.

Scope: registry loading, adapter SDK contract, policy engine, and router.
Authentication/secrets management, telemetry dashboards, caching, project
synchronization, and deployment tooling are future work (see
docs/federation/FEDERATION_MCP_TOPOLOGY.md).
"""

from hub.mcp_runtime.auth import (
    ChainCredentialProvider,
    CredentialProvider,
    EnvCredentialProvider,
    StaticCredentialProvider,
    TokenCache,
    redact,
)
from hub.mcp_runtime.cache import ResponseCache
from hub.mcp_runtime.oauth import OAuth2ClientCredentials
from hub.mcp_runtime.policy import PolicyEngine, PolicyViolation
from hub.mcp_runtime.registry import RuntimeRegistry
from hub.mcp_runtime.router import Router
from hub.mcp_runtime.sdk import AdapterResult, MCPAdapter, MCPRequest
from hub.mcp_runtime.telemetry import InMemoryMetrics, Metric, MetricsSink

__all__ = [
    "AdapterResult",
    "ChainCredentialProvider",
    "CredentialProvider",
    "EnvCredentialProvider",
    "InMemoryMetrics",
    "MCPAdapter",
    "MCPRequest",
    "Metric",
    "MetricsSink",
    "OAuth2ClientCredentials",
    "PolicyEngine",
    "PolicyViolation",
    "ResponseCache",
    "Router",
    "RuntimeRegistry",
    "StaticCredentialProvider",
    "TokenCache",
    "redact",
]
