# ECPAF-V2.2 — Durable bounded task dispatcher

**Implementation phase:** isolated development candidate. **Certification:** WITHHELD.

The dispatcher accepts a fixed JSON dependency graph of authorized, SHA-256 pinned task manifests and an exact-hash repository writer executable. It selects eligible tasks in dependency order, runs the bounded worker once per task, checks the worker's verified result, and records each transition in a durable SQLite WAL with full synchronous writes and content-addressed receipts.

## Controls

- A validated `epoch_id` and immutable plan SHA-256 must match on every restart. Changed plans, tasks, or worker bytes fail closed.
- One dispatcher per host uses an exclusive process lock. A maximum of 12 predeclared tasks is enforced; cyclic, duplicate, or unknown dependencies are rejected.
- A job marked `RUNNING` after interruption is reconciled against the writer ledger. Only a verified DONE result can be resumed without reissuing an operation. A partial/unknown mutation stays `RECONCILIATION_REQUIRED`.
- No arbitrary shell commands, unapproved merges, deployments, file deletion, policy changes, secret management, or certification operations exist in this dispatcher.
- If the worker fails before reserving a mutation because disk space is insufficient, the task is `RESOURCE_BLOCKED` and may be retried after storage recovery. A stale baseline or integrity error remains blocked.
- Independent tasks remain eligible when unrelated dependencies are blocked. This is a bounded batch dispatcher, **not yet a fully persistent 180-minute coding agent**.
- TheHub controls cross-repository governance. Domain authority stays with the corresponding repository. Repository-specific GitHub protections are not overridden by ECPAF policy 2.1.1.

## Example use

Run the regression suite from the TheHub checkout:

`python3 -m unittest discover -s tests -p test_ecpaf_afk_task_dispatcher.py -v`

Then run a validated queue manifest through the dispatcher only when each job and its SHA-256 authorization are prepared:

`python3 tools/afk/ecpaf_task_dispatcher.py --plan /path/to/frozen-plan.json --worker /path/to/verified/ecpaf_repo_worker.py --validate-only`

Remove `--validate-only` only within the authorized task scope. No production queue is bundled with this candidate.

## Remaining MAX-AFK gates

A persistent job supervisor and task authoring/approval workflow must be integrated with this dispatcher, followed by resource-pressure and sleep/disconnection fault injection, crash/restart/power-loss tests, GitHub exact-head CI, guarded merge and post-merge replay, and source/evidence audit. The earlier three-hour monitoring epoch is evidence for that **bounded monitoring supervisor only**; it does not establish three hours of unattended cross-repository coding.
