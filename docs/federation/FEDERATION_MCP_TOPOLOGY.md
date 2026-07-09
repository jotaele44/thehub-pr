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

## Future work (not implemented)

A federation **runtime** (a server that loads manifests/registry, resolves
adapters, enforces policy at request time, and routes calls) plus a full
adapter ecosystem, authentication/secrets layer, synchronization
automation, telemetry, caching, and deployment tooling is a natural next
phase of this program. None of that runtime exists yet — this document and
its companion registry/schema/validator files establish governance and
static validation only. Building the runtime is out of scope for this
change and is tracked as future work, not claimed as complete anywhere in
this repository.
