# MCP Core Adapters

The first real `MCPAdapter` implementations (`src/hub/mcp_runtime/adapters/`).
Every adapter here is **read-only** (`write_actions()` returns `[]`, so the
policy engine's read-only default is never challenged) and **hermetic** —
backed by data already in this repo or supplied per-request, with no network
calls and no secrets. Adapters that would need credentials must source them
from the environment at runtime (`authenticate()`), never from the repo.

Requests reach an adapter only through the `Router`, which first enforces the
project's manifest (a project may invoke a capability only if it declares it)
and then stamps the registry `version_pin` onto the result's provenance.

| Adapter | Capability | Backing data | Actions |
|---|---|---|---|
| `ProvenanceAdapter` | `provenance` | an export package's `sources.jsonl` (via `params["package"]`) | `list_sources`, `get_source`, `stamp` |
| `GeospatialAdapter` | `geospatial` | none — pure computation (reuses `hub.correlate` geodesy) | `distance`, `nearest`, `normalize_municipality` |
| `DocumentsAdapter` | `documents` | a document root of `*.md`/`*.txt` (via `params["root"]`) | `search`, `get` |
| `GithubBridgeAdapter` | `github-bridge` | `registry/producers.yaml` | `list_producers`, `resolve_repo` |

## Notes

- **ProvenanceAdapter** reads source lineage rows from a federation export
  package; `stamp` mints a deterministic `prefix_<sha256[:32]>` provenance id.
- **GeospatialAdapter** reuses the correlator's haversine/`lat`/`lon` helpers
  so adapter distances match the cross-producer spatial correlation path.
- **DocumentsAdapter** `get` rejects any path that resolves outside its root
  (path-traversal guard); `search` is case-insensitive and result-capped.
- **GithubBridgeAdapter** is a read-only view of the producer registry.
  Live git operations (clone/pull via `hub.fetch.clone_or_pull`) are
  deliberately out of scope here and tracked as future work, preserving the
  read-only-default posture.

## Usage

```python
from hub.mcp_runtime import MCPRequest, Router, RuntimeRegistry
from hub.mcp_runtime.adapters import GeospatialAdapter

router = Router(RuntimeRegistry())
router.register_adapter(GeospatialAdapter())
result = router.route(MCPRequest(
    project="spiderweb", capability="geospatial", action="distance",
    params={"a": [18.4655, -66.1057], "b": [18.0111, -66.6141]},
))
# result.data["distance_km"], result.provenance["version_pin"] == "1.0.0"
```

Domain adapters (`flight`, `weather`, `contracts`, …) remain future work; see
`FEDERATION_MCP_TOPOLOGY.md`.
