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
- `desktop/launch.py` picks a free port, starts uvicorn, and opens a native
  [pywebview](https://pywebview.flowrl.com/) window (falls back to the
  default browser). Flags: `--no-window`, `--browser`, `--route <path>`.
- `desktop/setup.py` is idempotent one-time setup (`--force` to redo).

## Command line

```bash
python desktop/setup.py          # one-time setup
.venv/bin/python desktop/launch.py              # native window
.venv/bin/python desktop/launch.py --route /launcher  # federation launcher page
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
