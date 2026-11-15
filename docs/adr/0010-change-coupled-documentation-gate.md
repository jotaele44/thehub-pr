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

Per ADR 0004, a passing workflow without a required-status rule is `PROVISIONAL`, not a certified merge block. `docs-sync` is `PROVISIONAL` in every repository until `main` requires it. `governance/merge_blocking_status.json` records what `main` requires in each repository and where `docs-sync` stands. Repository settings are outside what a template can set, so a repository administrator must mark `docs-sync` required once per repository; `tools/require_docs_sync.py` does that.

## Rollout

1. `thehub-pr`: templates, `targets.yaml` entries, this repository's manifest, this ADR.
2. Each producer, after (1) merges: re-render with `--template-ref <merged hub SHA>`, add its own `.federation/docs-sync.json`, and hand-apply the pre-commit, `CONTRIBUTING.md` and PR-template additions where the repository keeps its own copies (`moneysweep-pr`, `spiderweb-pr`).
3. Mark `docs-sync` required on `main` in each repository: `tools/require_docs_sync.py --apply`, run by a repository administrator. It appends the check to an existing ruleset or branch protection that already requires checks, otherwise creates a ruleset requiring only `docs-sync`. It skips a repository whose `main` has no `docs-sync` workflow, and holds any repository in its `HELD` table: one where a workflow in regular use pushes commits straight to `main`, which a required check would reject.

## Consequences

- Every repository maintains a small manifest. It is per-repository data and is deliberately not templated.
- Touching a covered path costs either a doc edit or one reasoned line. That line is visible to reviewers in the log, which is the point.
- The gate is only as good as its couplings. Documents that no coupling names are protected only by the reference ratchet.
- Files rendered from templates stay single-sourced: the checker cannot drift between repositories the way hand-copied scripts have.

## Amendment (2026-10-12): what "judged by both manifests" covers

Review of the first rollout found the rule stated more broadly than it was built. It is corrected, and now tested:

- The base manifest's couplings and `mode` still bind a change, so it cannot pass by deleting the coupling it violates or by switching the gate to report-only. Manifest hygiene (decision 3) is judged on the head manifest alone, so retiring a coupling together with its last covered file, or renaming a coupled doc and repointing the coupling, passes once the doc is updated. A doc renamed in the change counts as updated, and is compared with itself under its old name for the reference ratchet and the dead-glob check.
- A glob that matches nothing is a violation when the change adds it, and a warning when it was already there. Without a base to compare with (`--validate`, or a base manifest that does not parse) it stays a warning.
- `exempt_authors` is honoured only when the base manifest already lists the author. Read from the head, it let a pull request exempt itself and switch the whole gate off. Dependabot, the Actions bot and the federation bot stay built in.
- A `:symbol`, `:42` or `::node` locator is dropped from Markdown link targets as well as from inline code.
- Reference checking (decision 2) reads root Markdown and `docs/**` only. That scope is deliberate for the first version and is now stated in `CONTRIBUTING.md`. `exempt_docs` and `ignore_refs` still come from the head manifest because they are visible, per-document escape hatches.
