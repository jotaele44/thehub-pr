---
name: prii-validate-producer-manifest
description: >-
  Validate a producer's federation.json against the Hub-owned manifest schema.
  Use when the user asks whether a producer manifest is Hub-conformant, or before
  discovering/aggregating a producer. Read-only: runs the authoritative hub
  validate-manifest command and reports validity, schema version, and any
  missing or invalid keys — it never edits or promotes the producer's manifest.
default_mode: read_only
allowed_modes: [read_only]
command_ids: [validate-manifest]
owner_repo: jotaele44/thehub-pr
---

# prii-validate-producer-manifest

Orchestrates the Hub's producer-manifest check; it does not reimplement schema
validation. The authority is the `validate-manifest` command
(`python -m hub validate-manifest <path>`), which validates a producer
`federation.json` against the Hub-owned
`schemas/repo_federation_manifest.schema.json`. This skill runs it and interprets
the result — it is the Hub's read-only conformance gate at the producer boundary.

## When this fires
"Is this producer's federation.json valid / Hub-conformant?" — a single
producer manifest, before or independent of discovery and aggregation.

## When this does NOT fire (boundary)
- Validating an export *package* directory → `validate-package`.
- Rolling up readiness across a whole workspace → `validate-federation`.
- Aggregating or correlating producer exports → `aggregate` / `correlate`.
- Producing, materializing, or promoting a producer's data → the producer owns
  that (route to moneysweep-pr / centinelas-pr / …); the Hub never mutates it.

## Procedure
1. Run `validate-manifest` on the producer `federation.json` path.
2. Report validity, the manifest `schema_version`, and any missing/invalid keys
   the schema flagged, keyed to the schema rule that failed.
3. Note the producer's `federation_readiness_gate` as reported — do not change
   it; readiness is owner-governed.

## Required outputs
- manifest validity (pass/fail); schema version; every schema violation with the
  key/rule that failed and the manifest path.

## Stop conditions
- Producer manifest violates the Hub-owned schema → STOP; report the failing
  key/rule and the manifest path. Do not proceed to discovery/aggregation on an
  invalid manifest.

## Evidence & result envelope
Emit `{status, commands_considered, commands_run, artifacts, blockers,
contradictions, next_safe_action}`. Do not mutate or promote a producer's
manifest or export from the Hub. Secrets by name only.
