"""Bundled MCP adapters.

The mock adapter is the test reference; the core adapters are read-only,
hermetic (local-data-backed) implementations for the capabilities every
project inherits or commonly declares; the domain adapters cover the seven
domain/government capabilities via an injectable HTTP client (hermetic in
tests, live endpoints wired at deploy). See ``docs/federation/MCP_ADAPTERS.md``.
"""

from hub.mcp_runtime.adapters.documents import DocumentsAdapter
from hub.mcp_runtime.adapters.domain import (
    DOMAIN_ADAPTERS,
    ContractsAdapter,
    FieldOpsAdapter,
    FlightAdapter,
    OshaAdapter,
    RegulationsAdapter,
    TerrainAdapter,
    UtilitiesAdapter,
    WeatherAdapter,
)
from hub.mcp_runtime.adapters.geospatial import GeospatialAdapter
from hub.mcp_runtime.adapters.github_bridge import GithubBridgeAdapter
from hub.mcp_runtime.adapters.http import BaseHttpAdapter, EnvHttpClient, HttpClient
from hub.mcp_runtime.adapters.mock import MockAdapter
from hub.mcp_runtime.adapters.provenance import ProvenanceAdapter

__all__ = [
    "BaseHttpAdapter",
    "ContractsAdapter",
    "DOMAIN_ADAPTERS",
    "DocumentsAdapter",
    "EnvHttpClient",
    "FieldOpsAdapter",
    "FlightAdapter",
    "GeospatialAdapter",
    "GithubBridgeAdapter",
    "HttpClient",
    "MockAdapter",
    "OshaAdapter",
    "ProvenanceAdapter",
    "RegulationsAdapter",
    "TerrainAdapter",
    "UtilitiesAdapter",
    "WeatherAdapter",
]
