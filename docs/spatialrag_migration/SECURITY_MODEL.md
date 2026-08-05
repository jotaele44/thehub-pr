# Security Model — hardening spec and access classifications

Phase 0 audit deliverable. Companion to [ADR 0003](../adr/0003-evidence-intelligence-control-plane.md).

The uploaded package's optional API-key setting is insufficient for an integrated evidence system.
This document turns every hygiene finding from the audit into a named, resolvable requirement — not
just a description of what's wrong.

## Findings resolved as requirements

| Finding (confirmed by direct inspection) | Requirement |
|---|---|
| `DATABASE_URL`/`DATABASE_URL_SYNC` default to `spatial_rag`/`spatial_rag` in `.env.example`, and `docker-compose.yml` hardcodes the same credentials and exposes port `5432:5432` to the host | No default password value ships anywhere. Credentials are required, generated or operator-supplied, and never checked into an example file with a working value. Database port is not exposed by default in any compose/deploy config. |
| `API_KEY_ENABLED: bool = False` in `config.py` — auth is opt-in | Auth is **required** outside development, not a togglable default. Modeled on `src/hub/mcp_runtime/auth.py`'s fail-closed `CredentialProvider` (resolution fails closed when a credential is missing), not spatial-rag's `config.py` settings object. |
| CORS in `main.py`: `allow_credentials=True`, origins from a single `CORS_ORIGINS` setting defaulting to `http://localhost:3000` | CORS is an explicit allowlist per environment, reviewed at deploy time — not a single default string. Note: thehub-pr's own `server/backend/main.py` already restricts CORS to two localhost dev origins, which is the right *shape* to follow, but its `/api/auth/me` endpoint is hardcoded to always return 401 ("no auth in diagnostic mode") — that is itself a gap the Control Plane must actually close for the new engines, not a pattern to copy forward. |
| `RATE_LIMIT_SEARCH`/`RATE_LIMIT_INGEST`/`RATE_LIMIT_ANSWER` defined in `config.py` but never wired to any route decorator; only a single global `default_limits=["200/minute"]` is registered | Rate limits are wired to the routes they're named for, not left as dead configuration that gives a false impression of protection. |
| Upload validation (`validate_upload`) checks extension allowlist, size cap, magic bytes — reasonable — but no explicit archive-structure scanning, decompression-ratio limit, or page-count limit exists anywhere in the ingestion path | Add decompression and page-count limits on ingest; scan archive structure before extraction (relevant if/when zip or multi-file uploads are supported). |
| No path-traversal-specific test exists for uploaded filenames beyond writing through `tempfile.NamedTemporaryFile` (which mitigates but doesn't formally guarantee safety) | Model path/archive-traversal protection on `src/hub/mcp_runtime/adapters/documents.py`'s existing `_is_within()`/symlink-escape check — a real, working precedent already in this repo, not a new pattern to invent. |
| `geocode_place()` (Nominatim via `geopy`) exists in `backend/app/spatial/enricher.py` but is never invoked — no outbound-fetch allowlist exists anywhere in the codebase | Outbound URL fetching is disabled unless explicitly allowlisted. Before `geocode_place()` (or any future outbound call) is ever wired in, it must be added to an explicit allowlist with a documented ToS/rate-limit review — not activated silently because the function already exists. |
| No tenant/user access-boundary model of any kind — `entities.evidence_tier` and every retrieval object are equally visible to any caller who passes the (optional) API key check | See Access classifications below. |
| No secret-redaction guarantee in application logs — `config.py`'s settings object has no `redact()` equivalent | Adopt `src/hub/mcp_runtime/auth.py`'s `redact()` helper for anything touching credentials in logs, provenance records, or error messages, across both new engines. |
| Single hardcoded `ANTHROPIC_API_KEY`/`LLM_MODEL` string with no provider abstraction | See [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §10 (`LLMProvider`/`EmbeddingProvider`/etc.) — a security concern as much as a reproducibility one, since a single hardcoded provider means credential handling for that provider is the only path ever exercised or reviewed. |

## HyDE as a data-handling concern, not only a retrieval-quality one

`HYDE_ENABLED: bool = True` by default in `config.py` means every query by default sends the user's
question to a third-party LLM (`ANTHROPIC_API_KEY`-backed) to generate a hypothetical passage before
retrieval even runs. For FOIA/legal/entity-attribution/UAP-case forensic work, this is a data
exfiltration and provenance concern independent of its effect on recall — text derived from
sensitive source material is being sent externally by default, before a user has made any explicit
choice to do so. `HYDE_ENABLED=false` by default is therefore listed here as well as in
[`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §4 and [`COMPONENT_MIGRATION_MATRIX.md`](COMPONENT_MIGRATION_MATRIX.md)
row 7 — it is one requirement viewed from two angles (retrieval design and data handling), not two
separate requirements.

## Access classifications

Not every indexed item is retrievable by every interface. A single enum, enforced identically across
search, map, exports, and the LLM's own retrieved context window (never a different policy per
surface):

```
PUBLIC
INTERNAL
RESTRICTED
SENSITIVE_LOCATION
LEGAL_HOLD
QUARANTINED
TEST_ONLY
```

Enforcement point: an extension of `src/hub/mcp_runtime/policy.py::PolicyEngine.check_access()` (new
method on the existing engine, not a new parallel policy system). Every `EvidenceItem`, `Claim`, and
`SpatialFeature` carries a classification; the Control Plane resolves the caller's `access_context`
(per [`API_CONTRACT.md`](API_CONTRACT.md)) and filters before any object crosses the API boundary —
including into an LLM's context window, which is exactly as much a disclosure surface as a search
result or a map tile and must be filtered the same way, not treated as an internal/trusted channel.

`SENSITIVE_LOCATION` in particular is the enforcement point for
[`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §6's rule that a municipality mention must not be displayed
as an exact facility coordinate — a `SpatialFeature` with fine-grained accuracy on a sensitive
facility can be classified `SENSITIVE_LOCATION` and served only at reduced precision
(`spatial_precision_class = locality`) to callers without elevated access, rather than withheld
entirely or shown at full accuracy to everyone.

`TEST_ONLY` and `QUARANTINED` are never returned to a normal query regardless of caller — this is
the same rule as "only `ACTIVE` snapshots answer normal queries" in
[`SNAPSHOT_STATE_MACHINE.md`](SNAPSHOT_STATE_MACHINE.md), applied at the object level for items that
need quarantine independent of their snapshot's overall state (e.g. one document later found to
contain synthetic/test fixtures inside an otherwise-legitimate snapshot).
