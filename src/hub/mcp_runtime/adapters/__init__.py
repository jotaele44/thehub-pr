"""Bundled MCP adapters.

The mock adapter is the test reference; the core adapters are read-only,
hermetic (local-data-backed) implementations of the SDK contract for the
capabilities every project inherits or commonly declares. Domain adapters
(flight, weather, contracts, …) remain future work.
"""

from hub.mcp_runtime.adapters.documents import DocumentsAdapter
from hub.mcp_runtime.adapters.geospatial import GeospatialAdapter
from hub.mcp_runtime.adapters.github_bridge import GithubBridgeAdapter
from hub.mcp_runtime.adapters.mock import MockAdapter
from hub.mcp_runtime.adapters.provenance import ProvenanceAdapter

__all__ = [
    "DocumentsAdapter",
    "GeospatialAdapter",
    "GithubBridgeAdapter",
    "MockAdapter",
    "ProvenanceAdapter",
]
