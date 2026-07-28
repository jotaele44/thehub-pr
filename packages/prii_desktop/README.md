# prii-desktop

Shared desktop-wrapper **runtime** for PRII producer repos. It holds the code
that every producer previously copied into `desktop/launch.py` and
`desktop/app_server.py`:

- `make_desktop_app(config)` — wraps a producer's FastAPI app so the same local
  port also serves the built Vite frontend (same-origin, no CORS), with SPA
  navigation handling.
- `launch(config)` — opens native first-run setup and diagnostics, stores
  mutable state under the platform's application-data directory, starts the
  bundled local service, and opens a branded `pywebview` window.
- `setup_ui` — owns accessible storage selection, repair, diagnostic, release
  recovery, and `--setup-smoke` fresh-machine contracts.

Everything is parameterized by a `DesktopConfig` built from the producer's
`desktop/config.py` (the one genuinely per-repo file). Producers consume this
package as an **editable local path dep** from the sibling `thehub-pr` checkout
(added to `requirements-desktop.txt`), so editing this runtime once updates every
producer with no per-repo change.

Release builds freeze this package, Python, the backend, the compiled
interface, branding, and baseline resources into one application bundle.
Packaged users never run a bootstrap or install Python, Node.js, Git, or
project dependencies. Legacy `desktop/setup.py` files remain developer-only
source-checkout conveniences and are not part of the end-user setup path.

```python
from prii_desktop import DesktopConfig, launch
launch(DesktopConfig(
    app_title="TheHub",
    app_import="server.backend.main:app",
    repo_root=REPO_ROOT,
    dist_dir=REPO_ROOT / "server" / "frontend" / "dist",
    app_id="thehub",
    accent="#0B39CA",
    icon_path=REPO_ROOT / "assets" / "branding" / "icon-256.png",
    health_path="/health",
))
```
