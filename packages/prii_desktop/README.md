# prii-desktop

Shared self-contained desktop runtime for federation applications:

- `launch(config)` runs first-launch Setup & Diagnostics, applies a per-user
  writable workspace, starts the local service, and opens the native pywebview.
- `SetupBridge` provides a native folder picker, local diagnostics, idempotent
  repair, and an always-available in-app setup entry point.
- `make_desktop_app(config)` imports the producer backend and serves its built
  frontend same-origin, including client-route fallback.
- Per-user state and the single-instance lock live in Application Support on
  macOS rather than inside the app or PyInstaller extraction directory.
- `--smoke` bypasses interactive setup for frozen-build CI.

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

The package is installed as a local editable dependency while developing and
is frozen into each release app by PyInstaller.
