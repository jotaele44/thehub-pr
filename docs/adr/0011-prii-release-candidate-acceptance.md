# ADR 0011: One acceptance contract for the PRII release candidate

Status: Accepted for implementation by the 2026-09-12 release-candidate request;
all completion and release gates remain OPEN until verified.

## Context

Seven independently owned apps exchange artifacts through TheHub. Existing
development branches contain repairs, while the default checkouts contain user
work. Another task is developing the `seven-local-apps.v1` startup candidate.
Historical checks cannot certify a new combination of these inputs.

## Decision

Use `federation/prii-rc-acceptance.v1.json` as the finite acceptance contract for
this candidate. Preserve the 49 repository-axis and 21 platform cells from ADR
0010. Add explicit preservation, repository gates, six-producer scenario coverage,
scope reconciliation, independent clean installation, review, immutable tuple,
authority, live-source, hosted-check and rollback requirements. Each requirement
has an ID, source, owner, dependencies, acceptance test and evidence state.

The integration owner is task `01a095e8-9725-72d3-bf8a-130efadc6506`. Candidate
branches live in isolated worktrees; original checkouts and other tasks' branches
are inputs, never editing targets. Take committed snapshots of ongoing work and
preserve staged, unstaged and untracked changes separately. Reconcile content
before incorporating repairs. Keep source commit bindings in checkpoint records.

Use append-only checkpoint attempts outside the worktrees. Bind each to the
contract hash, seven source SHAs and evidence hashes. The contract's initial OPEN
states describe requirements; checkpoint receipts describe observed progress.
Changing code or inputs invalidates affected evidence. Amendments preserve the
prior contract hash and explain their source and effect on the denominator.

## Alternatives and consequences

Separate per-repo completion claims are insufficient to prove the combined path.
A shared authoritative database would violate producer ownership. Repeatedly
refreshing active source branches would make the candidate irreproducible.
Frozen source commits with explicit repair reconciliation preserve independence
and permit repeatable integration, at the cost of reviewing each later update.

Fixtures can prove software behavior, including refusal and recovery. They do
not close live-source, identity, platform or hosted gates. The signed operations
policy currently declares `hub.fetch` disabled pending acquisition gate G09;
improving the underlying fetch library does not enable that operation or satisfy
its GUI acceptance. Preserve this residue until the full gate and authorized
signature are available. No merge, deployment or production-data promotion
follows from this candidate or from successful local tests.
