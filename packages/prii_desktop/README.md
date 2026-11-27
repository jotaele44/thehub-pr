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
- **Menus** (`prii_desktop.menus`): a menu bar, a Dock tile menu and a right-click
  menu, with no per-app configuration. See [Menus](#menus).
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
  sets that variable to a fresh random credential for each session (or keeps one
  exported by the shell) and, with `url_param`, appends it to the URL the window
  opens.
- **Guest mode** sets `PRII_ACCESS_MODE=guest`, and `GuestGuard` (installed by
  `make_desktop_app`) answers every `POST`/`PUT`/`PATCH`/`DELETE` with `403`
  unless it matches `guest_guard.allow`. Patterns are `"[METHOD ]/path"`; `*`
  is one path segment and `**` any depth. List the producer's read-only POSTs
  there. The guard does nothing unless a session set the mode, so
  `--no-window`, tests and hosted deployments behave as before.
- **`options`** are `toggle`, `choice`, `text` or `secret`, each bound to one
  environment variable. `operator_only` options are disabled for a guest, and a
  guest session also withholds an operator-only variable the shell exported. A
  `secret` is used for that session and never written to disk.
- **Each session starts clean.** Changing the mode or options restarts the
  process, and a restarted process inherits its environment. `apply_session`
  therefore records what it changed in `PRII_LAUNCHPAD_MANAGED` (the names) and
  `PRII_LAUNCHPAD_ORIGINAL` (the shell's values it replaced), and
  `scrub_managed_environment` undoes both before the restart and before the next
  session is applied. A minted write credential, a typed secret, or an option
  value never carries over, so an Operator session followed by a Guest one
  leaves no credential behind, and a secret left empty is really unset. Values
  the shell exported are put back. Options may not use these two variable names.
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

An invalid declaration stops the launch with a message naming the problem: in
the window as an error screen (also written to `logs/launcher.log`), and on
`--browser`, `--no-window` and `--smoke` starts as the exit message. It never
falls back to the browser as if pywebview were missing. A second start while the
app is running opens the running instance in the browser and logs its mode; an
Operator session's credential stays with the original window, so writes from
that browser tab are refused.

### Checking a declaration offline

```bash
python -m prii_desktop launchpad --check            # from the producer's repo root
python -m prii_desktop launchpad --check --no-status
```

It imports `desktop/config.py` (`--module` and `--repo-root` choose another),
validates `LAUNCHPAD` exactly as the launcher does, and calls the `status`
provider once. A provider that raises, or a row with an unknown status, fails
the check, although at launch time such a provider only adds a warning row. The
exit code is `0` when there is no declaration or it is valid, and `1` otherwise.
The federation template `tests/test_launchpad_declaration.py` runs this check
in each desktop producer's test suite.

`tools/render_desktop_setup.py --page launchpad` renders a producer's real page
for browser checks.

## Menus

Every app gets the same three menus, built by `MenuController` from one list of
actions. A producer declares nothing: the **Go** entries are the Launch Pad's
`start_pages`, so an app without a Launch Pad simply has no page list.

| Surface | Where | What it holds |
| --- | --- | --- |
| Menu bar | all platforms (pywebview's `menu=`) | App menu: Setup & Diagnostics, Launch Pad, Restart. **Go**: Back, Forward, Reload Page, Start Page, then every start page. **Tools**: Copy Page Address, Open Page in Browser, Show Workspace and App Data in the file manager. **Window**: Minimize, Bring to Front. **Help**: Open Launcher Log, Show Logs, Copy Diagnostics Summary. |
| Dock tile menu | macOS | Show *App*, Launch Pad, Setup & Diagnostics; once the app page is up, Go To (a submenu of the start pages), Reload Page, Open Page in Browser; Show Workspace, Show Logs (once a log exists); Restart. macOS adds Options, Show All Windows, Hide and Quit below. |
| Right-click | macOS | Cut, Copy, Paste, Select All; Open Link / Copy Link Address when the pointer is on a web link; on the app page also Back, Forward, Reload Page, Copy Page Address, Open Page in Browser and Go To; then Launch Pad and Setup & Diagnostics. |

How it behaves:

- **State.** The Dock and right-click menus are built each time they open, so they
  only offer what works now (page actions appear only while the app itself is
  showing, not Setup, the Launch Pad or an error page). The menu bar is fixed by
  pywebview, so its page actions do nothing outside the app page instead.
- **Credentials.** Copy Page Address and Open Page in Browser remove the Operator
  credential parameter (`LAUNCHPAD.operator.url_param`) from the address. The Go
  entries load declared pages on the app's own origin with no credential in the
  address (the app keeps it in the page's session storage); Start Page reloads the
  session's original address, exactly as the first load did. Copy Diagnostics
  Summary contains no environment and no credential.
- **Page hook.** pywebview empties WebKit's own context menu, so on macOS each
  page gets a small script (`CONTEXT_MENU_JS`) that asks the bridge's
  `show_context_menu` for the native menu. It stands down if the page handles
  `contextmenu` itself, or if the bridge is missing.
- **No shortcuts.** pywebview's menu items carry no key equivalents, so these
  entries have no keyboard shortcuts; Edit and View come from pywebview.
- **Fails soft.** The macOS-only parts import PyObjC lazily and swap in a subclass
  of pywebview's application delegate rather than patching any of its methods. If
  anything about pywebview or PyObjC is not as expected, the reason is appended to
  `<app state dir>/logs/launcher.log` and the window opens as it did before.
- **Not exposed to pages.** pywebview exposes every public attribute of the bridge
  to page JavaScript, so the controller is held privately; `show_context_menu`
  is the only menu call a page can make, and it can only open a menu.

The package is installed as a local editable dependency while developing and
is frozen into each release app by PyInstaller.
