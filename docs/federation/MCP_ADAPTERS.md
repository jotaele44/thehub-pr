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

## Domain adapters

The seven domain/government capabilities are HTTP-backed adapters
(`src/hub/mcp_runtime/adapters/domain.py`) built on a shared, **injectable**
`HttpClient` (`http.py`). `EnvHttpClient` is the only place network access
lives; tests inject a fake client, so CI runs fully offline. Adapters are
read-only. Where an upstream needs a credential, the adapter resolves the
named key at runtime through the **credential provider layer**
(`hub.mcp_runtime.auth`) — `EnvCredentialProvider` by default, with
`StaticCredentialProvider`, `ChainCredentialProvider`, and a TTL `TokenCache`
(injected refresh hook and clock) available for other wirings. The value is
appended to the outgoing request and kept out of the provenance block; a
declared key the provider cannot resolve makes the adapter fail closed
(`run()` raises before `execute()`). Key names (never values) are listed in
`config/.env.example`.

| Adapter | Capability | Upstream | Env key | Actions |
|---|---|---|---|---|
| `FlightAdapter` | `flight` | OpenSky | — | `states`, `track` |
| `WeatherAdapter` | `weather` | NWS | — | `forecast` |
| `TerrainAdapter` | `terrain` | USGS EPQS | — | `elevation` |
| `ContractsAdapter` | `contracts` | SAM.gov | `MCP_CONTRACTS_API_KEY` | `search` |
| `RegulationsAdapter` | `regulations` | Regulations.gov | `MCP_REGULATIONS_API_KEY` | `search` |
| `UtilitiesAdapter` | `utilities` | PRASA/PREPA/LUMA (deploy-configured) | `MCP_UTILITIES_API_KEY` | `status` |
| `FieldOpsAdapter` | `field-ops` | Centinelas field intake (deploy-configured) | — | `observations` |

Each adapter owns its request/return contract and extracts upstream fields
defensively (`.get`), so a schema drift degrades to empty fields rather than a
crash. Live endpoints must be verified outside CI. `DOMAIN_ADAPTERS` is a tuple
of all seven classes for bulk registration.

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

A domain adapter takes an injectable client (a fake in tests, `EnvHttpClient`
in production):

```python
from hub.mcp_runtime.adapters import WeatherAdapter
router.register_adapter(WeatherAdapter())  # EnvHttpClient by default
```

Remaining future work (auth/secrets layer, router/policy hardening, a hosted
server, telemetry, caching, sync, deployment) is tracked in
`FEDERATION_MCP_TOPOLOGY.md`.
