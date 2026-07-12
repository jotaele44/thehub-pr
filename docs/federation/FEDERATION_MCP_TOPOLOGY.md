# Federation MCP Topology

This document defines the governance topology for **MCP (Model Context
Protocol) adapters** across the PRII federation. It is a distinct layer from
the data federation described in `docs/FEDERATION_TOPOLOGY.md` and
`ARCHITECTURE.md` — that layer moves canonical export packages between
producers and the Hub; this layer governs which external tools/services
(MCPs) each repository is allowed to declare and call, and under what
policy.

## Control plane

**TheHub (`thehub-pr`) is the central MCP control plane.** It owns:

- the capability registry (`mcp/registry/capability_registry.yaml`) —
  the authoritative list of capabilities, their class, status, and pinned
  version;
- the external MCP candidate matrix
  (`mcp/registry/external_mcp_candidates.csv`) — scored evaluation of
  third-party MCP adapters before they are trusted by any project;
- the manifest schema (`schemas/federation/project_mcp_manifest.schema.json`)
  that every project's MCP manifest must satisfy;
- the validators (`tools/validate_mcp_manifests.py`,
  `tools/validate_mcp_candidates.py`) and CI gate
  (`.github/workflows/mcp-registry-validation.yml`) that enforce all of the
  rules below on every change.

## Project repos are declarative clients

Project repos (`skywatcher-pr`, `ovnis-pr`, `spiderweb-pr`, `centinelas-pr`,
`moneysweep-pr`, `aguayluz-pr`) do not implement or negotiate MCP access
themselves. Each declares its required capabilities in a single manifest
under `mcp/manifests/<project>.mcp.yaml`, listing:

- the capabilities it inherits from the federation core,
- the additional registry and project-local capabilities it needs, and
- its write policy.

TheHub validates every manifest against the schema and the capability
registry. A project repo cannot grant itself a capability, a write
permission, or an adapter that TheHub's registry does not already
recognize.

## Read-only default

Every project MCP manifest's `write_policy.default` **must** be
`read_only`. Any write action must be explicitly named under
`write_policy.allowed_writes` and is subject to policy-gate review (see
`MCP_REGISTRY_RELEASE_CHECKLIST.md`). There is no implicit or inherited
write permission.

## No secret commits, no raw sensitive data

No manifest, registry entry, or adapter candidate record may contain
literal credentials (`api_key:`, `token:`, `password:`, `secret:`, or
equivalent). Secrets are provisioned outside of version control at
runtime; this repository's federation layer never stores or transmits raw
credential material. Adapter outputs that could carry sensitive raw data
(e.g. personally identifiable field observations) are handled at the
project layer under its own data-handling policy — the MCP layer only
governs *which tool may run*, not the sensitivity classification of the
data it returns.

## No confirmed-anomaly language

Registry and manifest content must never assert a confirmed finding using
the terms "confirmed anomaly", "confirmed UAP", or "confirmed USO". MCP
adapters return raw or lightly-processed observations; classification of
those observations as confirmed findings is out of scope for this
governance layer and is never encoded here.

## External MCPs are adapters, not authorities

An external MCP (a government API, a geospatial service, a weather feed,
etc.) is always an **adapter** — a bounded, versioned, revocable
integration — never an authoritative source of truth in its own right.
TheHub's aggregation and correlation logic (`src/hub/correlate.py` and
friends) remains the authority on cross-producer relationships; adapters
only supply raw inputs, always carrying provenance back to their source.

## Implemented so far

- **Governance & static validation** — this document, the capability
  registry, project manifests, JSON schema, validators, tests, and CI.
- **Runtime core** — `src/hub/mcp_runtime/`: the `MCPAdapter` SDK contract,
  the registry loader, the request-time policy engine (declaration checks,
  read-only-default write gating, deprecation blocking), and the router
  (capability→adapter resolution with provenance stamping).
- **Core adapters** — `src/hub/mcp_runtime/adapters/`: read-only, hermetic
  (local-data-backed) adapters for `provenance`, `geospatial`, `documents`,
  and `github-bridge`. The `github-bridge` adapter also has a networked
  `fetch` action (live shallow clone / fast-forward pull via
  `hub.fetch.clone_or_pull` through its injectable runner — real git in
  production, a fake runner in tests). See `MCP_ADAPTERS.md`.
- **Domain adapters** — the seven domain/government capabilities (`flight`,
  `weather`, `terrain`, `contracts`, `regulations`, `utilities`,
  `field-ops`) as read-only, HTTP-backed adapters over an injectable client
  (hermetic in tests; live endpoints wired at deploy, credentials from the
  environment). See `MCP_ADAPTERS.md`.
- **Auth/secrets layer** — `hub.mcp_runtime.auth`: pluggable credential
  providers (env, static, chain) and a TTL `TokenCache` with an injected
  refresh hook and clock. Adapters resolve credentials through this layer
  and fail closed when a key cannot be resolved; secret values never appear
  in provenance, logs, or reprs. Key names are documented in
  `config/.env.example` (names only).
- **Secret-manager providers** — `hub.mcp_runtime.secrets.SecretManagerProvider`
  implements the `CredentialProvider` protocol over an injectable `fetcher`
  (the boundary to AWS Secrets Manager / Vault / GCP — the operator supplies
  the SDK call), with optional TTL caching and fail-closed on error;
  `HttpSecretManager` is a generic REST fetcher. Compose with
  `ChainCredentialProvider([SecretManagerProvider(...),
  EnvCredentialProvider()])`. Injection-tested; a live backend is operator
  config, not exercised in CI.
- **OAuth2 refresh** — `hub.mcp_runtime.oauth.OAuth2ClientCredentials` is a
  client-credentials refresh callable for `TokenCache`: it exchanges an
  env-sourced client id/secret for a bearer token on TTL expiry and fails
  closed on any error. The token exchange is behind an injectable `poster`
  (real IdP call in production, a fake in tests) — the code is
  injection-tested, but a live IdP `token_url` is operator config and is not
  exercised in CI. Secret-manager backends remain future work.
- **Deployment packaging** — `Dockerfile`, `docker-compose.yml`,
  `deploy/thehub-mcp.service`, and `MCP_DEPLOYMENT.md` run the hosted API via
  uvicorn (non-root, `/healthz` healthcheck). See `MCP_DEPLOYMENT.md`.
- **Router hardening** — priority-ordered fallback across multiple adapters
  for a capability, a per-adapter circuit breaker (injected clock), an audit
  sink recording every routing decision, and optional deployment-level
  capability/project allowlists in the policy engine. Governance is never
  bypassed: policy denials raise up front and never fall back.
- **Hosted MCP API** — `server/backend/mcp_api.py` mounts the router into the
  existing FastAPI app: `POST /mcp/route`, `GET /mcp/capabilities`,
  `GET /mcp/metrics`, and `GET /healthz` / `/readyz`. Runs in-process
  (`python -m uvicorn server.backend.main:app`); provenance is logged as
  structured JSON lines.
- **Telemetry & caching** — `hub.mcp_runtime.telemetry` (a `Metric` per
  routing decision + `InMemoryMetrics` aggregates) and
  `hub.mcp_runtime.cache` (a TTL `ResponseCache`, injected clock). The router
  emits a metric on every path and caches reads only, after policy passes.
  See `MCP_ADAPTERS.md`.
- **Registry drift detection & sync automation** —
  `tools/check_registry_drift.py` fails CI when a capability's `required_by`
  and the manifests that declare it disagree (either direction);
  `tools/registry_sync_report.py` emits the same state as JSON for dashboards;
  and `.github/workflows/mcp-registry-drift-schedule.yml` runs the check on a
  weekly cron and opens/updates a same-repo tracking issue on drift.
  `tools/generate_sync_artifacts.py` emits the per-producer capability
  contract (from `required_by`) that a sync job would propagate, and
  `.github/workflows/mcp-cross-repo-sync.yml` generates + uploads those
  artifacts. The actual *cross-repo write* to sibling producer repos is gated
  on an operator `SYNC_PAT` secret and is a documented, operator-activated hop
  that is **not exercised in CI**.

## Future work — operator-activated external hops only

The runtime and tooling are complete to the honest limit of a hermetic
environment. What remains is **not unbuilt code** but **live external hops**
this repository deliberately does not exercise in CI. In each case the in-repo
core is implemented and injection-tested; activating the live hop is the
operator's documented step, and none is faked or claimed as CI-verified:

- **Secret managers** — `SecretManagerProvider` + `HttpSecretManager` ship;
  wiring a specific cloud SDK (AWS/Vault/GCP) is the operator's `fetcher`.
- **OAuth2** — `OAuth2ClientCredentials` ships; a real IdP `token_url` is
  operator config.
- **Metrics/tracing backend** — `LoggingMetricsSink` is fully real;
  `HttpMetricsSink` ships behind an injectable poster — a live collector is
  operator config.
- **Networked `github-bridge fetch`** — ships behind an injectable runner; the
  real git/network call is the default runner in production.
- **Cross-repo sync write** — the drift check, JSON report, same-repo issue
  automation, and per-producer artifact generation all ship; the write to
  sibling producer repos is gated on an operator `SYNC_PAT`.
