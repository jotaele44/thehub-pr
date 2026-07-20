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
| `GithubBridgeAdapter` | `github-bridge` | `registry/producers.yaml` (+ live git for `fetch`) | `list_producers`, `resolve_repo`, `fetch` |

## Notes

- **ProvenanceAdapter** reads source lineage rows from a federation export
  package; `stamp` mints a deterministic `prefix_<sha256[:32]>` provenance id.
- **GeospatialAdapter** reuses the correlator's haversine/`lat`/`lon` helpers
  so adapter distances match the cross-producer spatial correlation path.
- **DocumentsAdapter** `get` rejects any path that resolves outside its root
  (path-traversal guard); `search` is case-insensitive and result-capped.
- **GithubBridgeAdapter** is a read-only view of the producer registry.
  The `fetch` action performs a live shallow clone / fast-forward pull
  (params `program_id`, `dest`) via `hub.fetch.clone_or_pull` through the
  adapter's injectable `runner` — real git in production, a fake runner in
  tests. It reads remote state (still read-only for the federation); the
  network hop is not exercised in CI.

## Credentials & OAuth

Adapters resolve API keys through the credential provider layer
(`hub.mcp_runtime.auth`). For upstreams that use OAuth2 client-credentials,
`hub.mcp_runtime.oauth.OAuth2ClientCredentials` is a refresh callable for
`TokenCache`:

```python
from hub.mcp_runtime import OAuth2ClientCredentials, TokenCache, EnvCredentialProvider
refresh = OAuth2ClientCredentials(
    token_url="https://idp.example/oauth/token",
    client_id_key="MCP_FOO_CLIENT_ID", client_secret_key="MCP_FOO_CLIENT_SECRET",
)
creds = TokenCache(EnvCredentialProvider(), ttl_seconds=3000, refresh=refresh)
```

The token exchange is behind an injectable `poster` (real IdP call in
production, a fake in tests); client id/secret come from the environment,
never the repo, and it fails closed on any error.

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
| `OshaAdapter` | `osha` | DOL Open Data v4 (OSHA) | `MCP_OSHA_API_KEY` | `inspections`, `violations`, `accidents` |
| `UtilitiesAdapter` | `utilities` | PRASA/PREPA/LUMA (deploy-configured) | `MCP_UTILITIES_API_KEY` | `status` |
| `FieldOpsAdapter` | `field-ops` | Centinelas field intake (deploy-configured) | — | `observations` |

Each adapter owns its request/return contract and extracts upstream fields
defensively (`.get`), so a schema drift degrades to empty fields rather than a
crash. Live endpoints must be verified outside CI. `DOMAIN_ADAPTERS` is a tuple
of all eight classes for bulk registration.

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

## Hosted API

`server/backend/mcp_api.py` mounts the router into the existing FastAPI app
(`server/backend/main.py`), so the runtime is reachable over HTTP in-process:

```
python -m uvicorn server.backend.main:app --port 8000
```

- `POST /mcp/route` — body `{project, capability, action, params?, is_write?}`
  → `{status, data, provenance}`. Runtime exceptions map to status codes:
  policy denial → 403, missing/expired credential → 401, unknown
  capability/adapter → 404, bad action/params → 400.
- `GET /mcp/capabilities` — the registry (capability → class/status/
  version_pin/required_by) plus project manifests, for operator introspection.
- `GET /mcp/metrics` — telemetry aggregates (count, error rate, cache-hit
  rate, per-capability/adapter/decision tallies). Names and counts only —
  never params or credentials.
- `GET /healthz` (liveness) and `GET /readyz` (registry loaded + at least one
  adapter registered).

## Telemetry & caching

The router accepts an optional `metrics_sink` and `cache`
(`hub.mcp_runtime.telemetry` / `hub.mcp_runtime.cache`), both off by default:

- **Telemetry** — one `Metric` per `route()` call (capability, action,
  adapter, decision, `duration_s`, `cache_hit`, status). `InMemoryMetrics`
  collects them and computes aggregates. Backends:
  `LoggingMetricsSink` (structured JSON per metric — fully real, no external
  dependency), `HttpMetricsSink` (push to a collector via an injectable
  poster; live collector = operator config), and `MultiMetricsSink` to fan
  out. The hosted router uses `MultiMetricsSink([InMemoryMetrics(),
  LoggingMetricsSink()])` so `/mcp/metrics` keeps working while metrics are
  also logged.
- **Response caching** — `ResponseCache` is a TTL memory cache (injected
  clock, size cap) keyed by `(project, capability, action, params)`. The
  router only consults it for **reads and only after policy passes**, so a
  denied request is never served from or written to the cache, and writes are
  never cached. The hosted router wires both (30s cache TTL); metrics surface
  at `/mcp/metrics`.

FastAPI is the optional `[server]` extra; the API mount is guarded so a
failure there never takes down the entity API, and the server tests skip when
the extra is absent.

Remaining future work (live OAuth/secret-manager integrations, telemetry,
caching, sync automation, deployment packaging) is tracked in
`FEDERATION_MCP_TOPOLOGY.md`.
