# Backend Assessment & Development Plan — thehub-pr

## Scope & method

Read-only assessment of the backend at `main` (`d509b78`, "Add deterministic federation
completion runner"). `thehub-pr` is the central hub of the PRII (Puerto Rico Integrated
Intelligence) federation: it aggregates, correlates, and validates data exported by six
producer repos (`aguayluz-pr` water/power/karst, `moneysweep-pr` procurement/campaign
finance, `ovnis-pr` historical anomalous-event corpus, `spiderweb-pr` GIS/subsurface/marine,
`centinelas-pr` civic signal intake, `skywatcher-pr` airspace/aircraft), and hosts a
Federation Manager operations plane plus two shared libraries (`packages/prii_maintenance`,
`packages/prii_export_utils`) the producers pin as git dependencies. This document covers
both `thehub-pr`'s own local backend completion and, in the final section, a cross-repo
sequencing recommendation — since several gaps across the federation are explicitly
described in this repo's own code comments as needing "one federation-wide answer" rather
than six separate patches.

## Tech stack & backend inventory

- **Framework**: FastAPI (optional `server` extra: fastapi, uvicorn, cryptography), `src`-
  layout installable package `hub` with console scripts `hub`/`fed`. Ships a bundled
  `server/frontend` SPA and an iOS companion surface referenced via
  `/api/admin-companion/capabilities`.
- **Storage**: single generic SQLite table `entities(entity_type, entity_id, data JSON,
  updated_at)` — a document-store pattern, not a relational schema; no per-entity-type
  validation at write time beyond `id` presence.
- **Endpoints**:
  - `server/backend/main.py` is a compatibility shim importing `main_core.py` as the real
    app and mounting `gis_proxy.py`'s router.
  - `main_core.py` ("TheHub PRII Federation API"): `/health`, `/api/health`,
    `/api/apps/public-settings`, `/api/admin-companion/capabilities` (deny-by-default iOS
    capability contract), `/api/auth/me` (always 401 — "No auth in diagnostic mode");
    notifications (`/api/notifications`, `POST /ack`, `GET/PUT /preferences`); generic
    entity CRUD (`/api/entities/{entity_name}` list/create/get/patch/delete/filter/bulk);
    explicit diagnostic-mode stubs returning `status="not_implemented"` by design
    (`POST /api/functions/{function_name}/invoke`, `/api/agents/{path}`,
    `/api/integrations/{path}`, `POST /api/files/upload`,
    `/api/connectors/{name}/connection`); project signs (`/api/project-signs`, generation,
    HTML render); SPA catch-all serving `server/frontend/dist`.
  - `federation_manager_api.py` (mounted at `/api/federation-manager/*`): a full
    local-admin operations plane — sessions, apps/prerequisites, operations
    (plan/run/cancel), receipts, gates, secrets, file slots, and an SSE log-ticket pattern
    for streaming run logs.
  - `mcp_api.py`: mounted defensively (try/except; logs and continues on failure).
- **Auth**: the Federation Manager has a genuinely well-designed three-gate model
  (loopback-only + origin allowlist + short-lived opaque bearer session token, plus
  single-use SSE log-stream tickets) — but it entirely depends on an externally-supplied
  "native host" populating a `ManagerRuntime` global; absent that, every operations
  endpoint 503s. The main entity API has **no user auth**; mutations are gated only by an
  optional shared-secret `PRII_WRITE_TOKEN` (fail-closed if unset) — code comments
  explicitly flag this as incomplete, noting the browser UI has no write-credential input
  and that `aguayluz-pr` has the same gap (tracked in `docs/MATURITY_AUDIT.md`).
- **Business/services layer**: `src/hub` — `aggregate.py`, `correlate.py` (20.5 KB,
  cross-producer entity matching by name/external-id/location/funding-date/alert/
  observation footprint), `validate.py`, `ingest.py`, `identity_registry.py` (42 KB) +
  `identity_adjudication.py`, `htr.py`/`htr_v2.py`, `project_signs.py`,
  `project_leads.py`, `threshold_tuning.py`, `contract_runtime.py`, `spatial.py`,
  `sensor_fusion_consumer.py`. Plus `src/control_plane/` (dual-run equivalence/readiness,
  egress policy, producer job identity/policy, snapshot gate, model-run receipts) and
  `src/evidence_engine/` (producer admission accounting/identity/lineage, artifact
  intake/validation).
- **Background jobs**: no in-process scheduler; producer pickup/ingestion runs via GitHub
  Actions (`federation-pickup.yml`, `federation-ingest.yml`); the Federation Manager runs
  "operations" as supervised, receipted subprocesses on demand, not on a schedule.
- **Tests/CI**: ~115 test files; `fail_under = 88` coverage gate scoped to `src/hub`
  (91% measured) — the strongest coverage discipline of the seven repos, specifically over
  the aggregation/correlation core. 30+ workflows: `ci.yml`,
  `federation-completion-gate.yml`, `federation-governance.yml`/`-certify.yml`,
  `federation-ingest.yml`, `federation-pickup.yml`, `federation-ppp-e2e.yml`,
  `federation-runtime-certification.yml`, `gis-live-providers.yml`/
  `-source-certification.yml`, `gis-renderer-lock.yml`, an `htr-*` family, `mcp-cross-repo-
  sync.yml`, `mcp-registry-*.yml`, `ontology-ci.yml`, `pr180-identity-certification.yml`,
  `admin-control-plane.yml`.

## Completion assessment

- **Fully implemented**: generic entity CRUD; notifications subsystem; project-signs
  generation; the aggregation/correlation/validation library (`src/hub`); the Federation
  Manager's auth-gate design (as a pattern, even though it needs an external runtime host
  to function).
- **Partially implemented**: write authorization (single shared token, no real multi-user
  auth); the Federation Manager operations plane (code-complete but non-functional without
  an externally-supplied native-host runtime); the MCP API (mounted defensively, failures
  silently swallowed).
- **Missing entirely, by explicit design**: `/api/functions/*`, `/api/agents/*`,
  `/api/integrations/*`, `/api/files/upload` — self-documented diagnostic-mode stubs bound
  to infrastructure that doesn't exist yet (a producer-feed execution runtime, an agent
  backend, object storage).

## Development plan — hardest tasks first

Ordering rationale: item 1 is sequenced first not only because it's architecturally hard,
but because it's the one every producer's own "missing auth" gap is explicitly blocked on —
solving it once here avoids six repos each inventing an incompatible local answer. Item 2
follows because the Federation Manager's dependency-injection problem is the second-most
structural item and defines how producer operations get invoked once real identity exists.
Items 3–5 can mostly proceed in parallel with 1–2 since they don't share the same blocking
dependency.

1. **Design and ship real multi-user auth (login/session/RBAC) for the entity API** —
   Effort: **XL**. Explicitly flagged in code as needing "one federation-wide answer"
   shared with `aguayluz-pr`'s equivalent gap — see the federation-wide section below for
   the adoption sequence across all six producers.
2. **Make the Federation Manager operations plane usable as a standalone backend service**
   — Effort: **L**. The 9 modules (~150 KB, `federation_manager*.py`) currently require a
   native desktop host to inject `ManagerRuntime` (runner, files broker, secrets broker,
   gate rules, repositories) — a structural dependency-injection redesign, not a bug fix.
3. **Build real backends for the three intentionally-stubbed subsystems** (function
   execution, conversational agents, binary file storage) — Effort: **XL**, open-ended.
   Each needs new infrastructure (a producer-feed execution runtime, an agent backend,
   object storage), not just code — sequence only once there's a concrete consumer need,
   since building ahead of a real use case risks guessing the wrong contract.
4. **Harden the cross-producer correlation/identity-resolution engine**
   (`correlate.py` + `identity_registry.py`/`identity_adjudication.py`, ~75 KB combined) —
   Effort: **L**, ongoing. Inherently a fuzzy-matching precision/recall problem across
   independently-evolving producer schemas — never fully "done," track as continuous
   quality work rather than a one-time deliverable.
5. **Harden the MCP runtime** (`src/hub/mcp_runtime/`, `mcp_api.py`) — Effort: **M**.
   Currently mounted behind a bare try/except that silently logs and continues on failure;
   OAuth tests (`test_mcp_oauth_networked.py`) suggest network-dependent, possibly-flaky
   auth flows that need real hardening.

## Quick wins (sequenced after/alongside the above, not skipped)

- Have `/api/integrations/{path}` and `/api/connectors/{name}/connection` return a static
  registry of "known but unconfigured" integrations instead of a generic message.
- Replicate `main_core.py`'s defensive `_read_json_body`/`_clamp_limit` helper pattern into
  the producer repos' POST handlers, several of which lack equivalent input validation.

## Federation-wide sequencing (cross-repo)

No producer repo has real authentication today, and this repo's own code comments already
flag that as needing a shared answer rather than six local patches. Recommended order,
reflecting what each producer's own assessment doc separately identified as blocked on this:

1. **`thehub-pr` designs and ships the federation-wide auth contract** (item 1 above),
   replacing the ad hoc `PRII_WRITE_TOKEN` shared-secret pattern used piecemeal today in
   `aguayluz-pr`, `spiderweb-pr`, `centinelas-pr`, and `skywatcher-pr`.
2. **Producers adopt the contract.** Highest-priority adopter: `moneysweep-pr`'s
   case-manager API, whose `X-Case-Clearance`/`X-Case-Actor` headers are currently
   client-supplied with no identity verification at all — a live gap, not architecture
   debt (see that repo's own plan doc). The other producers swap their shared-secret
   stopgaps for the same contract.
3. **`thehub-pr`'s correlation/identity-resolution hardening** (item 4 above) can proceed
   in parallel with 1–2 — it doesn't share the same blocking dependency.
4. **Federation Manager operations-plane redesign** (item 2 above) follows the auth
   contract, since it defines how producer operations get invoked once real identity
   exists rather than an externally-injected native-host runtime.
5. **`skywatcher-pr`'s imagery/model-execution migration to `thehub-pr`** (its ADR 0006)
   follows the ops-plane redesign, since it depends on that plane being callable as a
   standalone service — see `skywatcher-pr`'s own plan doc for the producer-side detail.

Process note: once any of the above is actually implemented (out of scope for this
docs-only pass), it is a federation-visible contract change and must go through the
`federation-compatibility.yml` gate / `contract-sweeper-operator` / `contract-sweeper-
workflow` machinery already present in this federation's CI before merging in any single
repo — i.e. the full affected-repo set must be determined and every affected repo must
either adopt the change or demonstrate compatibility with it under the resulting contract
generation, not just pass CI in the repo that authored the change. This documentation PR
itself does not touch any federation-visible contract (`schemas/`, `federation.json`), so
it is not subject to that gate — but the next, implementation phase is.
