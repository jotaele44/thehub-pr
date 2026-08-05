# MCP Adapter Evaluation

## Purpose

Before any external MCP (a third-party tool/service adapter) is trusted by
a project manifest, it is scored and tracked in
`mcp/registry/external_mcp_candidates.csv`. This document defines how that
scoring works, what qualifies a candidate for adoption, and the hard
blocks that apply regardless of score.

## Scoring fields

Each candidate row in the CSV carries:

- `authority_score` (0–1) — how authoritative the underlying data source is
  for its domain (e.g. a federal agency's own API scores higher than a
  third-party aggregator).
- `coverage_score` (0–1) — how completely the adapter covers the data
  needed by the federation's use cases.
- `puerto_rico_fit` (0–1) — how well the adapter's coverage/resolution
  applies to Puerto Rico specifically (many federal geospatial/weather
  datasets under- or over-generalize for PR).
- `auth_requirements` — the credential burden to use the adapter
  (`none`, `none_or_low`, `none_or_api_key`, `api_key_possible`,
  `api_key_likely`, `secret_required`).
- `cost` — `free`, `free_or_low`, `free_or_paid`, or `paid`.
- `write_risk` — `low`, `medium`, or `high`; whether the adapter could ever
  be used for a write/mutating action.
- `provenance_support` — `low`, `medium`, or `high`; whether the adapter's
  responses carry traceable source/lineage metadata.
- `adoption_status` — `pilot`, `conditional`, `hold`, `reject`, or `active`.

## Adoption rules

- A candidate may only reach `active` once it has run as `pilot` (or
  `conditional`) against at least one real project manifest without a
  write-policy violation or forbidden-language finding.
- `version_pin: pending-evaluation` is allowed only while a candidate is
  `pilot` or `conditional`. Once `active`, it must carry a concrete pinned
  version in the capability registry.
- A candidate scored `write_risk: high` may never be adopted with a
  `write_policy.default` other than `read_only` at the project level; any
  write action it enables must be individually allowlisted and reviewed.

## Minimum acceptance criteria

A candidate must meet **all** of the following to move past `hold`:

- `authority_score >= 0.5`
- `provenance_support` is `medium` or `high`
- `auth_requirements` is not `secret_required` unless the project's secret
  management (out of scope for this registry) has already been reviewed
- no forbidden terms (secrets, confirmed-anomaly language) appear anywhere
  in its row

## Initial candidate summary

The initial 13 candidates in `external_mcp_candidates.csv` span government
data (Federal Register, Federal Regulations, SAM.gov, USAspending),
geospatial/terrain/weather utility adapters, provenance/governance
infrastructure (Provenance Content Registry, Governance Policy Gate),
logistics (AIS), parcel/zoning/flood data, and two explicitly higher-risk
categories flagged for caution: a generic paid API marketplace (broad,
low-authority, cost/write-risk concerns) and a personal GPS location MCP
(field-ops relevant but carries real privacy/sensitive-data handling
obligations at the consuming project, not at this registry layer).

## Promotion workflow

1. Candidate is added to the CSV with an initial score and
   `adoption_status: pilot` or `conditional`.
2. `tools/validate_mcp_candidates.py` runs in CI on every change to the
   CSV, enforcing the vocabularies and score bounds above.
3. A project manifest may reference the underlying registry capability
   once the candidate has demonstrated fit; the candidate itself is never
   referenced directly from a manifest — manifests only declare registry
   capabilities, never named third-party adapters.
4. Promotion to `active` requires an update to
   `mcp/registry/capability_registry.yaml` pinning a concrete version for
   the capability class the candidate serves, per the release checklist.

## Hard blocks

Regardless of score, a candidate is permanently `reject`ed if it:

- requires committing a live credential to this repository,
- cannot support `read_only` operation,
- has no reproducible or auditable provenance path, or
- is described using confirmed-anomaly language anywhere in its own
  documentation that this registry would need to reproduce.
