# Federation snapshot volatility-safe gate design v0.1

Status: DESIGN_ONLY / NON_PRODUCTION / NO_SEMANTICS_CHANGE
Scope: FEDERATION_PICKUP_SYSTEM_LEVEL_3 snapshot-currentness semantics.

## Problem

The current production gate treats any repository `main` SHA movement as material to `exact_main_sha_snapshot`. This is intentionally conservative and must remain the controlling rule until a separately reviewed implementation changes it. Repositories with scheduled refreshes, UI-template bumps, data-only updates, or other non-contract changes can therefore make a previously certified seven-repository snapshot stale within a short interval.

## Design objective

Reduce false invalidation from non-contract mainline movement without weakening provenance, hiding material change, or permitting heuristic promotion. This document does not alter the current validator, workflow, registry schema, or certification semantics.

## Proposed future model

Each repository manifestation would carry two independently frozen identities:

1. `repository_main_head_sha` — exact Git commit SHA. Always recorded and never ignored.
2. `federation_contract_fingerprint_sha256` — deterministic digest of a fail-closed allowlist of federation-critical contracts, schemas, producer exports, adapters, workflow interfaces, and other explicitly registered paths.

Every main advancement would be classified only after deterministic diff inspection as one of:

- `CONTRACT_RELEVANT`
- `DATA_MANIFESTATION_ONLY`
- `TOOLING_OR_UI_ONLY`
- `MIXED`
- `UNKNOWN`

`UNKNOWN` and `MIXED` fail closed as contract-relevant. Classification by commit message, `[skip ci]`, author, path name alone, or scheduled-job origin is prohibited.

## Proposed future gates

- `exact_main_sha_snapshot`: unchanged, retains strict 7/7 exact-head semantics.
- `contract_fingerprint_match`: optional second gate, only after a future schema/workflow implementation is separately certified.
- `main_head_advanced_contract_unchanged`: may support a distinct state such as `CONTRACT_CURRENT_NEW_MAIN_MANIFESTATION`; it must never be reported as `EXACT_MAIN_CURRENT`.
- any contract-fingerprint change, unregistered path affecting federation behavior, classifier uncertainty, hash failure, missing file, or source API error => `BLOCKED`.

## Provenance requirements

A future implementation must preserve every superseded exact-head snapshot, every observed main SHA, the complete changed-file denominator, classification receipts, fingerprints, and contradictions. No prior PASS may be rewritten as though it never existed. New currentness claims must identify their exact scope and timestamp.

## Merge-window protocol under current production semantics

Until such a future implementation is approved, retain the existing strict behavior:

1. read all seven `main` heads;
2. read all seven again and require 7/7 equality;
3. freeze the exact SHAs in `registry/development_vectors.yaml`;
4. run bounded MAX immediately;
5. require remote MAX observation to equal the frozen SHAs 7/7;
6. require CI/security gates PASS;
7. re-read all seven heads immediately before merge authorization;
8. if any head moved, revoke `MERGE_READY` and refreeze rather than weakening the gate.

## Explicit non-effects

This design does not change production code, workflow behavior, schema validation, vector arithmetic, project-lead identity semantics, banner eligibility, merge authorization, or production promotion. Project-lead evidence is prohibited from satisfying federation-MAX currentness gates.
