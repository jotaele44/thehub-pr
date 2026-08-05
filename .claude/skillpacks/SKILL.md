---
name: thehub-pr-unified-live-skillpack
description: "Compiled non-activating dispatch contract for shared and thehub-pr capabilities."
version: 1.0.0
compatibility: claude
repository: thehub-pr
---

# thehub-pr Unified Live Skillpack

Pinned base: `bf4c9d85a595d22f57f46d3fd7e192ccb5b77798`.

## Execution contract

- Exact capability identifiers only; unknown identifiers fail closed.
- Runtime activation, automatic dispatch, live polling, notifications, external writes, promotion, control actions, merge, and release are disabled.
- Source module semantics remain cryptographically bound in `MANIFEST.json`; this file is the compiled live dispatcher.
- Repository-specific authority overrides shared defaults.

## Capability dispatch

| Capability | Module | Status | Preserved responsibility |
|---|---|---|---|
| `repo-state-reader` | `repository-governance` | `` |  |
| `repo-identity-guard` | `repository-governance` | `` |  |
| `branch-guard` | `repository-governance` | `` |  |
| `task-scope-guard` | `repository-governance` | `` |  |
| `git-action-guard` | `repository-governance` | `` |  |
| `skill-authoring-template` | `skill-lifecycle` | `` |  |
| `skill-package-builder` | `skill-lifecycle` | `` |  |
| `validation-gate-runner` | `validation-and-recovery` | `` |  |
| `failure-packet-builder` | `validation-and-recovery` | `` |  |
| `delta-reporter` | `reporting-and-receipts` | `` |  |
| `status-writer` | `reporting-and-receipts` | `` |  |
| `foia-correspondence-manager` | `foia-operations` | `` |  |
| `foia-request-sender` | `foia-operations` | `` |  |
| `prii-federation-operator` | `federation-orchestration` | `` |  |
| `base44-federation-hub` | `federation-orchestration` | ``; alias of `prii-federation-operator` |  |
| `prii-producer-discovery` | `producer-discovery` | `` |  |
| `prii-federation-skill-catalog` | `producer-discovery` | ``; alias of `prii-producer-discovery` |  |
| `prii-manifest-validator` | `validation-readiness-and-release` | `` |  |
| `prii-export-package-validator` | `validation-readiness-and-release` | `` |  |
| `prii-readiness-reconciler` | `validation-readiness-and-release` | `` |  |
| `prii-release-auditor` | `validation-readiness-and-release` | `` |  |
| `prii-aggregate-builder` | `aggregation-and-correlation` | `` |  |
| `prii-cross-producer-correlator` | `aggregation-and-correlation` | `` |  |

## Required output fields

Every execution receipt must include `capability_id`, `repository`, `pinned_base_commit`, `inputs`, `outputs`, `validation`, `limitations`, `authority`, and `next_action`.

## Non-activation boundary

This binding does not invoke repository code. A later runtime adapter requires separate design, tests, review, and explicit authorization.
