---
name: thehub-pr-unified-live-skillpack
description: "Compiled non-activating dispatch contract."
version: 1.0.1
compatibility: claude
repository: thehub-pr
---

# thehub-pr Unified Live Skillpack

Pinned base: `4d9e59d76e96b736307cc574f76b20854c349faf`.

## Execution contract

- Exact identifiers only; unknown identifiers fail closed.
- Runtime activation, automatic dispatch, polling, notifications, writes, promotion, control, merge, and release are disabled.
- Module and package hashes remain in `MANIFEST.json`.

## Capability dispatch

| Capability | Module | Status | Preserved responsibility |
|---|---|---|---|
<a id="capability-repo-state-reader"></a>| `repo-state-reader` | `repository-governance` | `preserved-active-contract` | Preserve `repo-state-reader` under `repository-governance`. |
<a id="capability-repo-identity-guard"></a>| `repo-identity-guard` | `repository-governance` | `preserved-active-contract` | Preserve `repo-identity-guard` under `repository-governance`. |
<a id="capability-branch-guard"></a>| `branch-guard` | `repository-governance` | `preserved-active-contract` | Preserve `branch-guard` under `repository-governance`. |
<a id="capability-task-scope-guard"></a>| `task-scope-guard` | `repository-governance` | `preserved-active-contract` | Preserve `task-scope-guard` under `repository-governance`. |
<a id="capability-git-action-guard"></a>| `git-action-guard` | `repository-governance` | `preserved-active-contract` | Preserve `git-action-guard` under `repository-governance`. |
<a id="capability-skill-authoring-template"></a>| `skill-authoring-template` | `skill-lifecycle` | `preserved-active-contract` | Preserve `skill-authoring-template` under `skill-lifecycle`. |
<a id="capability-skill-package-builder"></a>| `skill-package-builder` | `skill-lifecycle` | `preserved-active-contract` | Preserve `skill-package-builder` under `skill-lifecycle`. |
<a id="capability-validation-gate-runner"></a>| `validation-gate-runner` | `validation-and-recovery` | `preserved-active-contract` | Preserve `validation-gate-runner` under `validation-and-recovery`. |
<a id="capability-failure-packet-builder"></a>| `failure-packet-builder` | `validation-and-recovery` | `preserved-active-contract` | Preserve `failure-packet-builder` under `validation-and-recovery`. |
<a id="capability-delta-reporter"></a>| `delta-reporter` | `reporting-and-receipts` | `preserved-active-contract` | Preserve `delta-reporter` under `reporting-and-receipts`. |
<a id="capability-status-writer"></a>| `status-writer` | `reporting-and-receipts` | `preserved-active-contract` | Preserve `status-writer` under `reporting-and-receipts`. |
<a id="capability-foia-correspondence-manager"></a>| `foia-correspondence-manager` | `foia-operations` | `preserved-active-contract` | Preserve `foia-correspondence-manager` under `foia-operations`. |
<a id="capability-foia-request-sender"></a>| `foia-request-sender` | `foia-operations` | `preserved-active-contract` | Preserve `foia-request-sender` under `foia-operations`. |
<a id="capability-prii-federation-operator"></a>| `prii-federation-operator` | `federation-orchestration` | `preserved-active-contract` | Preserve `prii-federation-operator` under `federation-orchestration`. |
<a id="capability-base44-federation-hub"></a>| `base44-federation-hub` | `federation-orchestration` | `compatibility-alias` | Preserve `base44-federation-hub` as an alias of `prii-federation-operator`. |
<a id="capability-prii-producer-discovery"></a>| `prii-producer-discovery` | `producer-discovery` | `preserved-active-contract` | Preserve `prii-producer-discovery` under `producer-discovery`. |
<a id="capability-prii-federation-skill-catalog"></a>| `prii-federation-skill-catalog` | `producer-discovery` | `compatibility-alias` | Preserve `prii-federation-skill-catalog` as an alias of `prii-producer-discovery`. |
<a id="capability-prii-manifest-validator"></a>| `prii-manifest-validator` | `validation-readiness-and-release` | `preserved-active-contract` | Preserve `prii-manifest-validator` under `validation-readiness-and-release`. |
<a id="capability-prii-export-package-validator"></a>| `prii-export-package-validator` | `validation-readiness-and-release` | `preserved-active-contract` | Preserve `prii-export-package-validator` under `validation-readiness-and-release`. |
<a id="capability-prii-readiness-reconciler"></a>| `prii-readiness-reconciler` | `validation-readiness-and-release` | `preserved-active-contract` | Preserve `prii-readiness-reconciler` under `validation-readiness-and-release`. |
<a id="capability-prii-release-auditor"></a>| `prii-release-auditor` | `validation-readiness-and-release` | `preserved-active-contract` | Preserve `prii-release-auditor` under `validation-readiness-and-release`. |
<a id="capability-prii-aggregate-builder"></a>| `prii-aggregate-builder` | `aggregation-and-correlation` | `preserved-active-contract` | Preserve `prii-aggregate-builder` under `aggregation-and-correlation`. |
<a id="capability-prii-cross-producer-correlator"></a>| `prii-cross-producer-correlator` | `aggregation-and-correlation` | `preserved-active-contract` | Preserve `prii-cross-producer-correlator` under `aggregation-and-correlation`. |

## Required receipt fields

`capability_id`, `repository`, `pinned_base_commit`, `inputs`, `outputs`, `validation`, `limitations`, `authority`, and `next_action`.

## Non-activation boundary

This binding does not invoke repository code. Runtime adapters require separate authorization.
