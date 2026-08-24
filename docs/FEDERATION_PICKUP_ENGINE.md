# Federation development-vector pickup engine

The Hub owns the canonical development intent ledger at `registry/development_vectors.yaml`. The `fed` CLI reconciles that intent against repository state, plans a dependency-safe order, and emits resumable receipts.

## Identity and evidence rules

Repository identity is bound by the stable GitHub repository ID plus `owner/repo`; names, branch names, counts, proximity, and search absence are never identity proof. Development-vector identity is the canonical `vector_id` in the ledger. GitHub issues, branches, commits, PRs, manifests, and operator instructions are source manifestations that must be explicitly bound to that vector.

Duplicate issue declarations are not duplicated vectors. AguaYLuz issues #10/#11 and OVNIS issues #4/#5 each contain the same explicit Vector identifier and are represented as `1:N` source manifestations of one canonical vector. Neither manifestation is discarded or marked superseded without independent evidence.

Text/code search is discovery only. In particular, a missing issue or missing code-search result never proves the absence of an active vector. Centinelas remains `UNRESOLVED` until authoritative intent is bound.

## Commands

| Command | Purpose | Mutation |
| --- | --- | --- |
| `fed doctor` | Validate ledger, runtime prerequisites, Git/gh availability | none |
| `fed snapshot` | Inspect local checkout heads against the frozen ledger | none |
| `fed snapshot --remote` | Inspect GitHub `main` heads through authenticated `gh api` | none |
| `fed ingest-vectors` | Validate canonical vector universe and DAG | none |
| `fed reconcile` | Compute effective state and blockers | none |
| `fed plan` | Emit deterministic topological plan | none |
| `fed status` | Roll up one state per repository and close arithmetic | none |
| `fed verify` | Run doctor + snapshot + reconciliation + plan + status | none |
| `fed run VECTOR` | Run one READY vector | dry-run unless `--apply` |
| `fed run --ready` | Run all presently READY vectors in DAG order | dry-run unless `--apply` |
| `fed pickup` | Freeze a pickup receipt without executing domain vectors | receipt only |
| `fed max` | Boundedly exhaust presently admissible vectors | dry-run unless `--apply` |
| `fed resume RECEIPT` | Reuse PASSed vector state from a prior receipt | dry-run unless `--apply` |
| `fed certify` | Emit bounded certification for the current ledger/snapshot | none |

## Status model

Operational states are mutually exclusive: `READY`, `BLOCKED`, `OPEN`, `PASS`, `FAIL`, `UNRESOLVED`. Certification is separate and may be `PASS`, `FAIL`, `OPEN`, `BLOCKED`, `PROVISIONAL`, `AUDIT_ONLY`, `NONCANONICAL`, `CANDIDATE_NOT_IDENTITY`, `UNRESOLVED`, or `SUPERSEDED`.

`fed max` means bounded exhaustion of the frozen declared-vector universe. It does not mean universal completion of every possible repository task. A vector is executed only if it is `READY`, every dependency is `PASS`, the snapshot is exact, and a safe executable command has been explicitly bound. Domain vectors without such commands remain `OPEN`, `BLOCKED`, or `UNRESOLVED`; they are not synthesized from issue prose.

## Fail-closed gates

The controller fails on duplicate stable repository IDs, duplicate vector IDs, one GitHub issue bound to different canonical vectors, undeclared dependencies, dependency cycles, invalid SHAs, repository-universe drift, status arithmetic mismatch, stale/unverified SHAs, and prohibited execution definitions.

Automatic PR merge, force-push, destructive branch deletion, and remote branch deletion are prohibited. `--apply` is required before any declared command is executed. A vector marked `prohibited_by_fed_max` may not carry an executable command.

## Receipts and restartability

Pickup/MAX/resume receipts are written atomically beneath `.fed/runs/`. The receipt contains the ledger digest, repository snapshot, reconciliation, plan, execution result, certification, and completed vector set. `fed resume` reuses the prior completed/PASS set and does not intentionally repeat those vector executions.

A changed `main` head invalidates the frozen expected SHA and blocks execution until the ledger is deliberately refreshed as a new snapshot. The first implementation run demonstrated this gate: multiple producer repositories advanced between the initial inventory and certification pass, so the original snapshot was superseded rather than silently reused.

## Current bounded universe

The bootstrap ledger contains eight canonical vectors across seven repositories. After the pickup engine itself passes, the expected development-vector repository rollup is four `OPEN`, two `BLOCKED`, one `UNRESOLVED`, zero `READY`, zero `FAIL`, and zero repository-level `PASS`; `4 + 2 + 1 = 7`. This is development-vector state and must not be conflated with the existing producer federation/live-readiness registry.
