# Seven-app release evidence

The accepted authority is ADR 0010 and generation `seven-local-apps.v1`. This generation promotes each domain interface without transferring domain ownership to TheHub.

## Evidence and refusal

Run `python scripts/federation_release_evidence.py BUNDLE.json` to validate a bundle. `pending_bundle(heads)` seeds all 49 repository-axis and 21 repository-platform cells as OPEN. Seed files are review queues, never passing receipts. PASS cells require executed evidence bound to a full repository SHA, generation, dimension, command, environment, timestamps, frozen input and output hashes, log, and empty residue. Platform receipts additionally require eight passing journey steps. Artifact paths must remain inside the bundle directory. Duplicate JSON keys and incomplete or duplicate matrix cells fail closed.

This validator checks evidence integrity and declared outcomes; it cannot independently establish the truth of a source classification or operator observation. Its output remains AUDIT_ONLY. A release decision also requires reviewed domain evidence, PR disposition, source accounting, exact remote heads, enforced executed checks, and rollback proof.

The completion runner accepts `--release-evidence BUNDLE.json` and rejects absent or nonpassing evidence, stale heads, dirty snapshots, incomplete remote inventory, failed commands, and actionable residue. Command success alone cannot certify completion. Preserve output directories and failed receipts; create a new attempt instead of overwriting an old one.

## Startup preparation

After installing the declared environment and building the frontend, run `python scripts/desktop_startup_probe.py --out RECEIPT.json` in each app checkout. The shared probe launches `desktop.app_server:app` on a held ephemeral loopback socket, checks health and HTML, retrieves actual same-origin JavaScript assets, and shuts down its server. Redirects outside the local origin are rejected. Receipt creation is exclusive.

This is startup preparation, not a real-browser journey. Complete install, launch, setup, domain workflow, export, restart recovery, upgrade and rollback separately on macOS, Windows and Linux. Missing packages and frontend bundles must remain visible as failed setup attempts.
