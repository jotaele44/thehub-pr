# prii-desktop

Shared desktop-wrapper **runtime** for PRII producer repos. It holds the code
that every producer's `desktop/launch.py` and `desktop/app_server.py` used to
copy verbatim:

- `make_desktop_app(config)` — wraps a producer's FastAPI app so the same local
  port also serves the built Vite frontend (same-origin, no CORS), with SPA
  navigation handling.
- `launch(config)` — starts uvicorn on a free localhost port in a background
  thread, waits for health, and opens a native `pywebview` window (falling back
  to the browser), plus a single-instance lock and a `--smoke` CI mode.

Everything is parameterized by a `DesktopConfig` built from the producer's
`desktop/config.py` (the one genuinely per-repo file). Producers consume this
package as an **editable local path dep** from the sibling `thehub-pr` checkout
(added to `requirements-desktop.txt`), so editing this runtime once updates every
producer with no per-repo change.

Only *post-install* code lives here: the pre-venv `desktop/setup.py` bootstrap
cannot import an installed package, so it stays vendored per repo (deduped
separately via templating).

```python
from prii_desktop import DesktopConfig, launch
launch(DesktopConfig(
    app_title="OVNIS — PRII Case Corpus",
    app_import="server.backend.main:app",
    repo_root=REPO_ROOT,
    dist_dir=REPO_ROOT / "dashboard" / "dist",
    health_path="/health",
))
```
