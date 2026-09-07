# ADR 0010 — Seven local production apps

- Status: Accepted by the operator for implementation; release verification OPEN.
- Date: 2026-09-07 UTC
- Authority: explicit user-approved seven-app completion plan.
- Supersedes: ADR 0001 product-surface consolidation only.

## Decision

Ship seven independently usable local operator apps on macOS, Windows and Linux.
TheHub remains the Federation coordinator. Each producer retains domain logic,
data ownership, reviewed promotion and its production UI. Exchange versioned
artifact contracts; do not introduce a competing shared authoritative database.
Hosted authentication is outside this local release. Other ownership ADRs,
including imagery/model execution, remain in force.

## Migration and gates

Propagate `seven-local-apps.v1` through the existing template renderer. Preserve
existing runtime labels until capability-specific evidence permits promotion.
Repair each app's setup, protected operations, recovery and provenance surfaces.
Validate 49 completion-axis cells and 21 platform journeys, with exact revisions,
input hashes, test logs and explicit residue. Any missing evidence blocks release.
Keep the previous release generation available for rollback. Existing endpoint
consumers continue through compatibility adapters during versioned changes.

## Verification

The release evidence validator must reject missing/duplicate cells, mismatched
heads or generations, tampered logs, nonterminal checks, missing source evidence,
unresolved residue and unsupported platform claims. It reports bounded evidence
validation only; a schema-valid claim does not itself certify the product.
