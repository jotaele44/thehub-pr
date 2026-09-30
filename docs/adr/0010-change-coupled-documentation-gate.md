# ADR 0010 — Change-coupled documentation gate

- **Status:** Proposed
- **Date:** 2026-09-29
- **Deciders:** PRII federation maintainers
- **Scope:** all seven PRII federation repositories (defined in `thehub-pr`, rendered into each)
- **Extends:** [ADR 0004](0004-federation-governance-layer.md), §Documentation drift

## Context

ADR 0004 requires documentation to agree with the machine-readable state of the federation and lists "No known documentation contradiction remains inside the certified scope" as an invariant. The only mechanized check is `check_docs()` in `scripts/federation_governance.py`, which requires `ARCHITECTURE.md` to name every producer. Everything else relies on a reviewer remembering.

Two measurements shape the design (last several hundred non-bot commits per repository, 2026-09-29):

- 79–93% of human code commits touch no Markdown at all. A blanket "code changes need a doc change" rule would fail most pull requests, and the federation has already removed one repo-wide check because it "blocked ordinary PRs" (`governance/change_log.json`, 2026-09-13).
- Dangling references are rare and, in the core docs, nearly absent (0–2 per repository), but `docs/` trees run 9–25% stale because most of what lives there is a dated snapshot rather than a description of current state.

No tool can prove that prose still matches code. What can be checked mechanically is narrower, and the rest should become an explicit, reviewable decision rather than a silent omission.

## Decision

A change that makes a document describing a repository untrue MUST update that document in the same change. The federation enforces the mechanically checkable part of that rule with one checker, `tools/check_docs_sync.py`, rendered byte-identically into every repository from `federation-templates/baseline/check_docs_sync.py`:

1. **Co-change.** Each repository declares in `.federation/docs-sync.json` which docs cover which paths, and which kinds of change (add, delete, rename, modify) matter. Changing a covered path without changing its doc fails unless a commit message or the PR description carries `Docs-Impact: none - <reason>`. A waiver without a real reason is itself a failure.
2. **References, as a ratchet.** A change MUST NOT leave a document pointing at a repository path that no longer exists. Only references the change itself broke count, so legacy dangling references never block unrelated work. Snapshot documents (dated audits, receipts, ADRs, changelogs) describe a moment rather than the repository and are listed under `exempt_docs`. A dangling reference is a fact, not a judgement call, so `Docs-Impact: none` cannot waive it; a deliberate one goes in `ignore_refs` or is waived for that document by name.
3. **Manifest integrity.** Unknown keys, missing docs, and globs that stopped matching anything are reported. A change is judged by the manifest it arrives with as well as the one it edits, so it cannot pass by deleting the coupling it violates or by switching the gate to report-only.

The same verdict is delivered at four points: pre-commit (`--staged`, where a missing doc update is only a warning because the waiver text does not exist yet), CI (the `docs-sync` job, on every pull request, without a path filter so a required check always reports), a Claude Code Stop hook in `.claude/settings.json`, and the standing instruction in `CLAUDE.md` and `CONTRIBUTING.md`. Four pieces ship as one unit (checker, workflow, hook settings, `CLAUDE.md`); a subset would be worse than none.

Seeds are chosen by replaying history. A coupling that fires on routine work is removed rather than waived; one that has never fired or has fired with the doc already updated is kept. `"mode": "report"` in a manifest prints the same findings without failing the job, for triaging a new manifest.

## What this does not do

- It does not prove prose is true. A coupling says "look at this doc", not "this doc is now correct". Semantic review of contradictions in prose remains a reviewer's job; an LLM-assisted reviewer is a possible later layer and is deliberately not part of this decision.
- It does not stop a merge by itself. See below.
- It does not cover documents that are generated from data. Those need regenerate-and-diff checks, several of which already exist per repository.

## Merge enforcement

Per ADR 0004, a passing workflow without a required-status rule is `PROVISIONAL`, not a certified merge block. `docs-sync` is `PROVISIONAL` in every repository until `main` requires it. `governance/merge_blocking_status.json` records that on 2026-09-06 five of the seven repositories had no branch protection on `main` at all. Repository settings are outside what a template can set, so a repository administrator must mark `docs-sync` required once per repository.

## Rollout

1. `thehub-pr`: templates, `targets.yaml` entries, this repository's manifest, this ADR.
2. Each producer, after (1) merges: re-render with `--template-ref <merged hub SHA>`, add its own `.federation/docs-sync.json`, and hand-apply the pre-commit, `CONTRIBUTING.md` and PR-template additions where the repository keeps its own copies (`moneysweep-pr`, `spiderweb-pr`).
3. Mark `docs-sync` required in each repository's ruleset.

## Consequences

- Every repository maintains a small manifest. It is per-repository data and is deliberately not templated.
- Touching a covered path costs either a doc edit or one reasoned line. That line is visible to reviewers in the log, which is the point.
- The gate is only as good as its couplings. Documents that no coupling names are protected only by the reference ratchet.
- Files rendered from templates stay single-sourced: the checker cannot drift between repositories the way hand-copied scripts have.
