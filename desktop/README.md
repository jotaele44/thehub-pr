# TheHub for macOS

Use the standalone macOS `.dmg` from a desktop release:

1. Open the downloaded `.dmg`.
2. Drag **TheHub** to **Applications**.
3. Open TheHub from Finder or Launchpad.
4. In **Setup & Diagnostics**, choose a workspace and select **Save & Open App**.

The release app is self-contained. End-user setup needs no Terminal and no
separate Python, Node.js, Git, package-manager, or source checkout. The writable
Hub database is created inside the selected workspace, never inside the
read-only application bundle.

Use the always-available gear button in the app to reopen **Setup & Diagnostics**.
It can choose the workspace, run local checks, or repair generated configuration.
Repair is idempotent and does not delete user data.

The optional federation launcher remains available at `/launcher` inside the
desktop app for sibling development checkouts. A standalone TheHub installation
does not require those repositories to open its own dashboard.

## If macOS blocks the first open

Open **System Settings → Privacy & Security**, find the message naming TheHub,
and select **Open Anyway**. This is the complete UI-only recovery path for an
unnotarized development release.

## Architecture

`desktop/config.py` and `desktop/app_server.py` are thin Hub adapters for the
local federation-launcher routes. Native setup, repair, diagnostics, the
per-user lock, same-origin serving, and the pywebview window live in the shared
`packages/prii_desktop` runtime. Release CI builds and smokes the frozen app on
macOS, Windows, and Linux and packages the macOS `.dmg`.

`desktop/setup.py` and command-line launcher flags remain developer conveniences;
they are not part of end-user installation.
