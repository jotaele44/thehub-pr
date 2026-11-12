# ECPAF-V2.2 — Bounded Autonomous Repository Writer

**Status:** isolated pilot candidate, not certified for production release.

This worker accepts explicit, byte-pinned task manifests and writes changes only into a new, isolated, uniquely named development branch. The result is a **draft GitHub pull request**, never a merge or deployment. TheHub remains authoritative for cross-repository governance; the individual repository retains its domain authority.

## Authorization and evidence boundary

- Only an explicitly enumerated eight-repository allowlist is eligible.
- An exact immutable `base_sha` must equal GitHub `main` and the local `origin/main` identity. A dirty primary checkout blocks execution.
- File changes are predeclared as paths with source and destination SHA-256 checks. Writes are limited to `scripts/`, `tools/`, `tests/`, and `docs/`. Traversal, `.git` paths, symlinks, unknown suffixes, and undeclared changes are rejected.
- Changes occur in an isolated sparse Git worktree; every push is verified against the GitHub branch identity before a **draft** PR is created.
- SQLite records PREPARED, COMMITTED, PUSHED and DONE checkpoints. A crash at a partial side effect returns `RECONCILIATION_REQUIRED`; the worker does not blindly retry a push or PR creation.
- Receipt bytes are SHA-256 addressed. A completed operation must reconcile its draft PR on GitHub before a replay returns DONE.
- No branch-protection override, auto-approval, force push, production merge, deployment, credential modification, source-byte promotion, or federation certification exists in the worker.

## Verified bounded pilot

The worker is tested against a disposable local bare Git repository. Its regression suite proves that valid scoped edits produce one draft PR, replay is idempotent, and unauthorized modes, stale heads, dirty repositories, path traversal, duplicate paths and interrupted operations stop safely. This is *not* a proof of long-duration unattended operation or general-purpose autonomous code generation.

Run tests from the repository root:

`python3 -m unittest discover -s tests -p test_ecpaf_afk_repo_worker.py -v`

The production admission path must remain `PLAN_VALID → RESOURCE_PREFLIGHT → PREPARED → COMMITTED → PUSHED → DRAFT_PR_VERIFIED`. The worker is deliberately not installed as a persistent LaunchAgent by this PR. Persisted scheduling, trusted task creation, automated CI fixes, device-restart fault injection, full browser-disconnection validation and actual multi-repository LOCKSTEP remain **OPEN**.

**Exit criteria:** independent runtime verification of exact-head commits, branch permissions, required hosted checks, task-scoped change budgets, full durability/failure-injection coverage, and all mandatory gates. ECPAF policy revision 2.1.1 removes the federation-wide independent-review requirement but does not override a repository's GitHub branch-protection rules.
