# Run TheHub as a desktop app

Double-click the launcher for your system in the repo root:

| System | File |
|---|---|
| macOS | `PRII-THEHUB.command` or `PRII-THEHUB.app` |
| Windows | `PRII-THEHUB.bat` |
| Linux | `PRII-THEHUB.sh` |

`PRII-FEDERATION.command`/`.bat`/`.sh`/`.app` open the same app directly on its
federation-launcher page (`/launcher`), which can also open sibling federation
checkouts (`PRII-<NAME>.app`/`.sh`/`.bat` in `../<repo>`) if you have any
checked out next to `thehub-pr`. Neither launcher requires the other.

The **first run** needs an internet connection once: it creates a private
`.venv`, installs the Python dependencies, and builds the frontend (requires
Python 3.10+ and Node.js to be installed). Every later run starts instantly
and **works offline**.

## The Launch Pad

After the first-run setup, TheHub opens on its **Launch Pad** instead of going
straight to the dashboard. Nothing is running yet at that point. It shows:

- **Readiness**: the workspace, how many records the store holds, and which
  producer checkouts sit next to TheHub.
- **Guest or Operator.** Guest is read-only. Operator turns on administrative
  writes for that session: the launcher sets `PRII_WRITE_TOKEN` to a one-time
  value and hands it to the window, so there is nothing to paste. You can
  protect Operator with a passphrase.
- **Open on**: the page the window starts on.
- **Launch options**: the Grid V2 profile folder.
- **Next time**: skip the Launch Pad and reuse these choices.

Press **Launch** to start. To change the mode or options later, use the
**Launch Pad** button in the corner of the app (next to the Setup gear); it
restarts on this page. Guest and the passphrase keep a shared desktop tidy;
they do not stop someone who can already run programs under your account.

The launcher opens TheHub with an **empty** database — `data/hub.db` is
gitignored and created fresh on first run. That's expected, not a setup
failure: populating it with real federation data is a separate, optional
operator step (`hub aggregate && hub correlate`, `hub ingest` — see the root
README's "single product" section) done after the app already opens.

A separately built, no-Python-required standalone `.dmg`/`.exe`/AppImage is
also produced by the `desktop-build` release workflow — that's an additional
distribution channel, not a replacement for the launcher above.

## How it works

- `desktop/config.py` and `desktop/app_server.py` are thin Hub adapters that
  reuse the existing FastAPI backend and serve the built frontend from the
  same origin (no CORS, one process).
- `desktop/launcher_api.py` / `desktop/launcher.html` back the `/launcher`
  federation-launcher page that `PRII-FEDERATION.*` opens directly.
- `desktop/launch.py` shows the Launch Pad, then picks a free port, starts
  uvicorn, and opens the app in the same native
  [pywebview](https://pywebview.flowrl.com/) window (falls back to the
  default browser, where there is no Launch Pad and stored options apply).
  Flags: `--no-window`, `--browser`, `--route <path>`, `--launchpad`,
  `--skip-launchpad`, `--guest`, `--operator`.
- `LAUNCHPAD` in `desktop/config.py` is TheHub's Launch Pad content: its
  summary, readiness check, start pages, the read-only POSTs a guest may call,
  and its options. The screen itself lives in the shared runtime
  ([`packages/prii_desktop`](../packages/prii_desktop/README.md#the-launch-pad)).
- The native window has a menu bar (Go, Tools, Window, Help, plus extra items in
  the app menu), and on macOS a Dock tile menu and a right-click menu. The **Go**
  entries are the Launch Pad's start pages, so they follow `LAUNCHPAD` in
  `desktop/config.py` with nothing else to configure; the rest comes from the
  shared runtime ([Menus](../packages/prii_desktop/README.md#menus)).
- `desktop/setup.py` is idempotent one-time setup (`--force` to redo).

## Command line

```bash
python desktop/setup.py          # one-time setup
.venv/bin/python desktop/launch.py              # native window
.venv/bin/python desktop/launch.py --route /launcher  # federation launcher page
.venv/bin/python desktop/launch.py --skip-launchpad    # straight into the app
.venv/bin/python desktop/launch.py --no-window --operator  # server only, writes enabled
.venv/bin/python desktop/launch.py --no-window  # server only
```

## If macOS won't open the app

The app is safe — it's an open-source launcher script you can read in
`Contents/MacOS/`. macOS blocks it only because it isn't signed with a paid
Apple Developer ID or notarized by Apple, so the first open may show *"cannot
be opened because Apple cannot check it for malicious software"* or an
*"unidentified developer"* notice. That's macOS quarantining files downloaded
from the internet. Any one of the following clears it — you only do this once
per download:

- **Easiest — run the helper.** Double-click **`Fix-Gatekeeper.command`** in
  the repo root, then open the app normally.
- **Terminal (always works).** Paste this into Terminal, then press Return:
  ```bash
  xattr -dr com.apple.quarantine "/path/to/thehub-pr/PRII-THEHUB.app"
  ```
- **System Settings.** Double-click the app, let macOS block it, then open
  **System Settings → Privacy & Security**, scroll to the message naming the
  app, and click **Open Anyway**.
