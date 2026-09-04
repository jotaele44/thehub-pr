# PRII Federation Canon v1

Canon v1 converts the exhaustive 2026-08-05 semantic inventory into explicit, non-merging adjudications and canonical term records, then requires a fresh current-head verification before release.

## Normative identity

CURIE identifiers such as `prii:SourceRecord` are the normative semantic identity keys. `https://prii.dev/...` expansions remain serialization aliases until domain-control attestation is recorded.

## Baseline adjudication

- 21 scale conflicts: fully dispositioned.
- 3,717 authority conflicts: priority families receive explicit authority; the remainder stay owner-scoped.
- 8,777 homonym groups: every group classified as true conflict, expected bounded-context reuse, local conflict, implementation reuse, or literal reuse.
- 9,338 synonym candidates: every candidate mapped to exact/close/broad/related/non-equivalent; automatic merging is forbidden.

## Coverage semantics

`100%` means **eligible-file semantic inventory coverage**, not all tracked files. Exclusions are separately reported. Parser fallbacks are inventory-only and cannot directly justify canonicalization.

## Release

Canon v1 may merge only when current-head exhaustive extraction passes and `APPROVALS.json` records every required repository owner approval.
