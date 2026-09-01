# Federation baseline issue #226 refresh plan

This branch is intentionally separate from all HTR feature branches. It preserves every HTR v1/v2 frozen artifact and does not alter HTR semantic contracts.

## Snapshot refresh basis

The federation pickup snapshot is versioned to the explicitly observed repository `main` heads below. This is an explicit new bounded snapshot, not a silent rebind of the 2026-08-29 snapshot.

- jotaele44/skywatcher-pr: `6b5c13c06ba10b742b6af30b71301757e7b96072`
- jotaele44/aguayluz-pr: `aaf1d79df1bcf20e07358db0662a09b6bc4bd82b`
- jotaele44/spiderweb-pr: `533fdde554e11b486a4ddb7a3fbe8127ed3fa2b2`
- jotaele44/moneysweep-pr: `ffdc781bc2196fc5e35903573f3948137e18bb1b`
- jotaele44/centinelas-pr: `6adbba5bcdc251e6f60c8aa8b6298d6966a74013`
- jotaele44/ovnis-pr: `b02ac5094852e3e86901d0225f6be0b8af334876`
- jotaele44/thehub-pr: `643a4b7b17d90a316de86def89fc9b5fef7eb413`

Captured at `2026-08-31T23:57:06Z`.

## Launcher governance

Spiderweb's macOS/Linux launchers intentionally contain repo-specific setup-failure/Node.js diagnostics added on main. They are therefore removed from the shared `PRII-APP.command` / `PRII-APP.sh` byte-equality target set while the other launcher targets remain governed by the canonical templates. This preserves functionality rather than overwriting it to satisfy drift.

## Skywatcher lint

The three Ruff failures observed on the stale HTR merge ref are already repaired on current Skywatcher main: the sqlite3.Row membership line carries a documented `# noqa: SIM118`, import order is normalized, and the unused `sqlite3` import is absent. No HTR branch is rewritten.
