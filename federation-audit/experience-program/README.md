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

## Re-running

```bash
python federation-audit/experience-program/scripts/rc0_baseline.py \
  --root <directory holding the eight checkouts> \
  --out federation-audit/experience-program/rc0 --verify-recovery
```

Each checkout needs `origin/main` fetched first. The script fetches only into a
temporary directory that it deletes.
