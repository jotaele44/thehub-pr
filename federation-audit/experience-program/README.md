# Federation Application Experience & Modernization Program

Working package for the eight-repository experience program (gates RC0–RC11).
Everything here is evidence or tooling for that program. Nothing in this
directory is imported by the hub or by any producer.

Release policy is fail-closed. A gate file states `PASS`, `FAIL`, `OPEN`,
`BLOCKED`, `PROVISIONAL`, `AUDIT_ONLY`, `UNRESOLVED` or `SUPERSEDED`. An artifact
that has not been produced or validated is left `OPEN`; it is never filled in.
Certification is withheld until every required gate passes, including a review by
someone other than the author of the work.

## Layout

| Path | What it is |
|---|---|
| `scripts/rc0_baseline.py` | Rebuilds the RC0 artifacts. Read-only against the repositories. |
| `rc0/repository_baselines.json` | Git identity of each audited `main`, next to the identities recorded earlier. |
| `rc0/source_manifest.json` | Per-repository file counts, bytes, lockfiles, and the SHA-256 of each listing. |
| `rc0/manifests/<repo>.sha256` | One line per tracked file: `<sha256>  <git mode>  <path>`. |
| `rc0/source_manifest.sha256` | SHA-256 of every RC0 artifact above. |
| `rc0/worktree_inventory.json` | Local branches, worktrees, uncommitted files and stashes at capture time. |
| `rc0/recovery_verification.json` | Result of re-fetching each audited commit into an empty directory. |
| `rc0/RC0_GATE.json` | Gate state and the checks behind it. |
| `scripts/rc1_merge.py` | Validates the RC1 surveys and writes the merged RC1 artifacts. Audits nothing itself. |
| `rc1/surveys/<repo>.json` | One source survey per application, made from a snapshot of its RC0 commit. |
| `rc1/application_inventory.json` | The surveys merged, with each denominator recomputed from its rows. |
| `rc1/ui_workflow_matrix.csv` | One row per workflow, plus one per surface that has no workflow. |
| `rc1/settings_inventory.json`, `rc1/context_actions_inventory.json` | Settings, contextual actions and keyboard shortcuts across applications. |
| `rc1/accessibility_findings.json` | Accessibility leads read from source. Not scan results. |
| `rc1/special_adjudications.json` | Answers to the per-application questions in the program brief. |
| `rc1/desktop_conventions.json` | Where recents, pinning, renaming and Dock behaviour exist today (workstream WS-D). |
| `rc1/RC1_GATE.json` | Gate state, totals and per-application validation. |
| `rc2/schemas/*.schema.json` | Federation Experience Contract v1: the contract, actions, settings, navigation and compatibility schemas. |
| `scripts/rc2_validate.py` | Validates contract documents: the schemas plus the rules that span sections or applications. |
| `rc2/fixtures/positive/` | Two illustrative contracts that must be accepted, alone and together. |
| `rc2/fixtures/negative/` | One file per rule: a patch on a positive fixture and the finding it must produce. |
| `rc2/RC2_GATE.json` | Gate state, schema hashes and the checks behind it. |

## Reading RC0

- Git commit and tree ids are Git object hashes. The SHA-256 values are hashes of
  file content. They are recorded in separate fields and are not interchangeable.
- "Remote reproduces trees" means a fresh fetch of the exact commit, checked out
  into an empty directory, hashes to the same listing. One file in `mucaro-ai`
  differs on disk because `.gitattributes` declares `eol=crlf` for it; undoing
  that conversion reproduces the committed hash, and the record says so.
- That check is not a backup test. No backup outside the Git host was identified,
  so off-device recovery is `OPEN` and RC0 is `PROVISIONAL`, not `PASS`.
- The commit ids in the program brief were starting references. Where `main` has
  moved since, the brief's id is an ancestor of the audited one and is marked
  `SUPERSEDED`.

## Reading RC1

- RC1 is a **source audit**. No application was started for it, so no surface is
  `OBSERVED_RUNTIME`. The best class a surface can have here is
  `SOURCE_CONFIRMED`.
- A surface counts as mounted only where the survey cites the line that mounts or
  routes to it. A component file existing is not enough.
- `rc1_merge.py` checks each survey's shape, recomputes its totals from its rows,
  and checks that every cited `path:line` exists at the audited commit. A citation
  written as a bare file name is accepted only when exactly one tracked file has
  that name. Resolving a citation shows the line exists, not that it says what the
  survey claims; that needs a person or a runtime check.
- An application with no survey yet is `OPEN`, and so is the gate.
- Forms, tables and filters inside a page are listed as each survey's
  `coverage_statement` says, which may be a sample. The denominator is therefore
  closed for routes, workspaces, tabs, navigation, dialogs, settings, contextual
  actions, shortcuts and backend endpoints, and open for in-page controls.

## Reading RC2

- The contract fixes interaction **semantics**, not layout. Applications keep
  their own pages; they agree on what an action, a setting and a navigation
  entry are.
- One action definition feeds every surface it appears on: toolbar, item menu,
  right-click menu, command palette, Dock menu, keyboard. The schema refuses an
  action whose only surface is right-click or the Dock menu, so no action is
  mouse-only or macOS-only.
- A write is never available to a guest and always names an audit event. Only a
  user-named object can be renamed; an evidence object cannot.
- Settings carry a scope. A federation-global setting lives in the `federation.`
  namespace with no owning application; every other setting lives in its
  application's namespace, so one application cannot overwrite a global value or
  another application's value. Pins and recents are bounded per-user lists at
  application scope.
- Unknown fields are rejected except extension fields named `x-*`. `null` is
  accepted only where a property declares it.
- `rc2_validate.canonical()` is the serialization to hash or compare: sorted
  keys, compact separators, UTF-8. Array order is kept because it is meaningful.
- **The positive fixtures are not declarations.** They are documents written to
  exercise the rules and say so in an `x-fixture-note`. No application has
  adopted the contract, which is why RC2 is `PROVISIONAL`.

A negative fixture is `{"description", "base", "patch", "expect"}`. `base` names
one or more positive fixtures; each `patch` entry is `set`, `remove` or `copy` on
a `/`-separated path (`doc` picks which base document, `-` appends to a list);
`expect` lists finding codes that must appear.

## Re-running

```bash
python federation-audit/experience-program/scripts/rc0_baseline.py \
  --root <directory holding the eight checkouts> \
  --out federation-audit/experience-program/rc0 --verify-recovery
```

Each checkout needs `origin/main` fetched first. The script fetches only into a
temporary directory that it deletes.

```bash
python federation-audit/experience-program/scripts/rc1_merge.py \
  --surveys federation-audit/experience-program/rc1/surveys \
  --snapshots <directory holding one export of each audited commit> \
  --baselines federation-audit/experience-program/rc0/repository_baselines.json \
  --out federation-audit/experience-program/rc1
```

A snapshot is `git archive <audited commit> | tar -x -C <dir>/<repo>`.

```bash
python federation-audit/experience-program/scripts/rc2_validate.py <contract.json> [...]
pytest tests/test_experience_contract.py
```
