# prii-desktop

Shared self-contained desktop runtime for federation applications:

- `launch(config)` runs first-launch Setup & Diagnostics, applies a per-user
  writable workspace, starts the local service, and opens the native pywebview.
- The **Launch Pad** (`prii_desktop.launchpad`) is the screen a producer opens
  on once it declares `LAUNCHPAD`: what the app is for, readiness, Guest or
  Operator entry, the starting page, and the producer's pre-launch options. See
  [The Launch Pad](#the-launch-pad).
- `SetupBridge` provides a native folder picker, local diagnostics, idempotent
  repair, and an always-available in-app setup entry point.
- `make_desktop_app(config)` imports the producer backend and serves its built
  frontend same-origin, including client-route fallback.
- Per-user state and the single-instance lock live in Application Support on
  macOS rather than inside the app or PyInstaller extraction directory.
- `--smoke` bypasses interactive setup for frozen-build CI.
- A failed start is never silent: the splash shows first, and any backend import
  or startup error (or a backend thread that dies) replaces it with an error
  screen offering **Try Again** and **Open Setup & Diagnostics**. The traceback is
  appended to `<app state dir>/logs/launcher.log`.

Release bundles contain the Python runtime, producer backend, dependencies,
built frontend, and app artwork. The setup center never downloads tools, runs a
shell, or mutates the installed application bundle.

Each producer keeps a thin `desktop/config.py` adapter:

```python
APP_TITLE = "Skywatcher"
APP_ID = "Skywatcher"
APP_IMPORT = "server.backend.main:app"
DIST_DIR = REPO_ROOT / "frontend" / "dist"
BRAND_ACCENT = "#0573e4"
BRAND_ACCENT_STRONG = "#075ba7"
ICON_PATH = REPO_ROOT / "assets" / "branding" / "icon-256.png"
DATA_ENV_VAR = "SKYWATCHER_DATA_HOME"
```

An adapter may also declare an idempotent `SETUP_ACTION =
"module:function"` for producer-specific workspace preparation. The shared
runtime invokes it after the workspace and environment are ready.

## The Launch Pad

A producer opts in with one constant in `desktop/config.py`. Without it nothing
changes: the window opens straight into the app.

```python
LAUNCHPAD = {
    "tagline": "Airspace intelligence",
    "summary": "One paragraph: what this app is for.",
    "highlights": ["Flight archive", "Sky cameras"],
    "status": _launchpad_status,            # callable or "module:function"
    "start_pages": [{"route": "/", "label": "Command Dashboard"}],
    "guest": {"label": "Guest", "description": "Read-only."},
    "operator": {
        "label": "Operator",
        "description": "May change data.",
        "token_env": "PRII_WRITE_TOKEN",    # the backend's write-credential variable
        "url_param": "write_token",         # how its UI is handed that credential
    },
    "guest_guard": {"allow": ["POST /api/entities/*/filter"]},
    "options": [
        {"id": "offline", "label": "Work offline", "kind": "toggle",
         "env": "APP_OFFLINE", "help": "Skip live feeds."},
    ],
}
```

What each part does:

- **Order.** Setup & Diagnostics (first run only), then the Launch Pad, then
  the backend. The choices are written to the process environment *before* the
  producer backend is imported, so settings that are read at import time apply.
- **`status`** returns rows of `{"label", "value", "status", "detail"}` with
  `status` one of `pass`, `warn`, `fail`, `info`. It runs before the backend
  exists, so it reads files; the workspace variables are already set. A status
  function that raises becomes one warning row and never blocks launching.
- **`operator`** makes the app two-mode. Leave it out for an app with no write
  surface and the access choice is not shown. With `token_env`, Operator mode
  sets that variable to a per-session random credential (or keeps one already
  exported) and, with `url_param`, appends it to the URL the window opens.
- **Guest mode** sets `PRII_ACCESS_MODE=guest`, and `GuestGuard` (installed by
  `make_desktop_app`) answers every `POST`/`PUT`/`PATCH`/`DELETE` with `403`
  unless it matches `guest_guard.allow`. Patterns are `"[METHOD ]/path"`; `*`
  is one path segment and `**` any depth. List the producer's read-only POSTs
  there. The guard does nothing unless a session set the mode, so
  `--no-window`, tests and hosted deployments behave as before.
- **`options`** are `toggle`, `choice`, `text` or `secret`, each bound to one
  environment variable. `operator_only` options are disabled for a guest. A
  `secret` is used for that session and never written to disk.
- **Start page.** `--route` preselects a page; the user's choice wins.

Per user, in the app state directory: `launchpad.json` holds the last mode,
page and non-secret options and the "skip next time" preference;
`operator-lock.json` holds a salted PBKDF2 hash when the user protects Operator
mode with a passphrase. Neither file ever contains a credential.

Guest mode and the passphrase are conveniences for a shared desktop, not a
security boundary: anyone who can run programs as the same operating-system
user can bypass both. A producer's own write guard remains its real control.

Flags: `--launchpad` shows the page even when it was set to be skipped,
`--skip-launchpad` opens with the stored choices, and `--guest` / `--operator`
choose the mode for `--browser` and `--no-window` starts (which otherwise leave
the mode unmanaged). `--smoke` never shows the page. Inside the app, the
**Launch Pad** button beside the Setup gear restarts on the page so the mode
or options can be changed.

`tools/render_desktop_setup.py --page launchpad` renders a producer's real page
for browser checks.

The package is installed as a local editable dependency while developing and
is frozen into each release app by PyInstaller.
