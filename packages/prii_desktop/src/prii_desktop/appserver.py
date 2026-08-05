"""Same-origin ASGI app for the desktop wrapper (shared runtime).

Reuses a producer's existing FastAPI backend and additionally serves the built
Vite frontend from the same port, so the desktop app needs exactly one local
server and no CORS. API routes keep priority because they were registered on the
app before the catch-all below — except for browser page navigations
(Accept: text/html), which the middleware routes to the SPA so client routes
that share a path with an API endpoint still load on hard refresh.

Ported verbatim from the per-repo ``desktop/app_server.py``; the only difference
is that the producer's FastAPI app and its ``dist`` directory arrive via
``DesktopConfig`` instead of module-level imports.
"""

from __future__ import annotations

import html
import importlib
import re
import sys
from pathlib import Path

from .config import DesktopConfig

_PASSTHROUGH_PREFIXES = ("/docs", "/redoc", "/openapi")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

_MISSING_BUILD_CSS = (
    "html,body{height:100%;margin:0}"
    "body{display:flex;flex-direction:column;align-items:center;"
    "justify-content:center;font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
    "background:#0f172a;color:#e2e8f0;text-align:center;padding:0 32px}"
    "h1{font-size:18px;margin:0 0 12px}"
    "p{color:#94a3b8;font-size:14px;max-width:34rem}"
    "button{min-height:44px;border:0;border-radius:8px;padding:10px 16px;"
    "background:#2563eb;color:#fff;font:600 14px inherit;cursor:pointer}"
    "button:focus-visible{outline:3px solid #93c5fd;outline-offset:3px}"
)
_MISSING_BUILD_PAGE = (
    '<!doctype html><html><head><meta charset="utf-8"><title>Setup needed</title>'
    f"<style>{_MISSING_BUILD_CSS}</style></head>"
    "<body><h1>The dashboard isn't available</h1>"
    "<p>The bundled interface is missing. Open Setup &amp; Diagnostics to verify "
    "the installation or repair generated configuration. No command line is required.</p>"
    '<button type="button" onclick="window.pywebview.api.open_setup()">'
    "Open Setup &amp; Diagnostics</button>"
    "</body></html>"
)


def desktop_controls_script(config: DesktopConfig) -> str:
    """Inject an unobtrusive, keyboard-accessible native setup entry point."""
    accent = (
        config.brand_accent_strong
        if _HEX.fullmatch(config.brand_accent_strong)
        else "#1d4ed8"
    )
    label = html.escape(
        f"Open {config.app_title} Setup & Diagnostics", quote=True
    )
    return f"""<script id="prii-desktop-controls">
(() => {{
  const mount = () => {{
    if (!window.pywebview || !window.pywebview.api ||
        document.getElementById("prii-desktop-setup-button")) return;
    const button = document.createElement("button");
    button.id = "prii-desktop-setup-button";
    button.type = "button";
    button.setAttribute("aria-label", "{label}");
    button.title = "Setup & Diagnostics";
    button.textContent = "⚙";
    Object.assign(button.style, {{
      position:"fixed", right:"14px", bottom:"14px", zIndex:"2147483647",
      width:"44px", height:"44px", borderRadius:"12px",
      border:"1px solid #ffffff66", color:"#fff", background:"{accent}",
      font:"600 20px system-ui", boxShadow:"0 7px 24px #0005", cursor:"pointer"
    }});
    button.addEventListener("focus", () => {{
      button.style.outline = "3px solid #fff";
      button.style.outlineOffset = "3px";
    }});
    button.addEventListener("blur", () => {{ button.style.outline = "none"; }});
    button.addEventListener("click", () => window.pywebview.api.open_setup());
    document.body.appendChild(button);
  }};
  mount();
  window.addEventListener("pywebviewready", mount, {{ once:true }});
}})();
</script>"""


def _inject_desktop_controls(
    index: Path, config: DesktopConfig | None
) -> str:
    document = index.read_text(encoding="utf-8")
    if config is None or "prii-desktop-controls" in document:
        return document
    control = desktop_controls_script(config)
    marker = "</body>"
    if marker in document:
        return document.replace(marker, f"{control}{marker}", 1)
    return document + control


def _load_app(config: DesktopConfig):
    """Import the producer's FastAPI app object from ``config.app_import``."""
    # The repo root must be importable so "server.backend.main" resolves.
    root = str(Path(config.repo_root).resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    module_path, _, attr = config.app_import.partition(":")
    module = importlib.import_module(module_path)
    return getattr(module, attr or "app")


def make_desktop_app(config: DesktopConfig):
    """Return the producer's FastAPI app augmented with same-origin SPA serving."""
    app = _load_app(config)
    if not config.attach_frontend:
        return app
    return attach_spa(app, config.dist_dir, config=config)


def attach_spa(
    app,
    dist_dir,
    *,
    config: DesktopConfig | None = None,
    passthrough_prefixes: tuple[str, ...] = _PASSTHROUGH_PREFIXES,
):
    """Augment a FastAPI ``app`` with same-origin static + SPA-fallback serving.

    Split out from ``make_desktop_app`` so it can be unit-tested against a minimal
    app without importing a producer backend.
    """
    from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

    dist_dir = Path(dist_dir)

    def _index_response():
        """The SPA entry point, or a friendly setup page when the build is missing."""
        index = dist_dir / "index.html"
        if index.is_file():
            return HTMLResponse(_inject_desktop_controls(index, config))
        return HTMLResponse(_MISSING_BUILD_PAGE, status_code=503)

    @app.middleware("http")
    async def spa_navigation(request, call_next):
        """Serve the SPA for browser page navigations, even on API-shadowed paths.

        Navigations advertise text/html first in Accept; the SPA's own fetch()
        calls send */* and fall through to the API routes.
        """
        accept = request.headers.get("accept", "")
        path = request.url.path
        if (
            request.method == "GET"
            and accept.split(",", 1)[0].strip().startswith("text/html")
            and not path.startswith(passthrough_prefixes)
            and "." not in path.rsplit("/", 1)[-1]
        ):
            return _index_response()
        return await call_next(request)

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """Serve built frontend files, falling back to index.html for SPA routes."""
        if full_path.endswith("/"):
            # Preserve FastAPI's usual trailing-slash behavior for API paths
            # (e.g. /health/ -> /health) instead of swallowing them as SPA routes.
            trimmed = "/" + full_path.strip("/")
            if any(getattr(route, "path", None) == trimmed for route in app.routes):
                return RedirectResponse(trimmed, status_code=307)
        if full_path:
            candidate = (dist_dir / full_path).resolve()
            # Keep path traversal inside the dist directory.
            if candidate.is_file() and candidate.is_relative_to(dist_dir.resolve()):
                return FileResponse(candidate)
        return _index_response()

    return app
