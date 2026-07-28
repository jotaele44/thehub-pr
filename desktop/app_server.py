"""Same-origin ASGI app for the desktop wrapper.

Reuses the repo's existing FastAPI backend and additionally serves the built
Vite frontend from the same port, so the desktop app needs exactly one local
server and no CORS. API routes keep priority because they were registered on
the app before the catch-all below — except for browser page navigations
(Accept: text/html), which the middleware routes to the SPA so that client
routes that share a path with an API endpoint still load on hard refresh.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse  # noqa: E402
from server.backend.main import app  # noqa: E402

from desktop.config import DIST_DIR  # noqa: E402
from desktop.launcher_api import router as launcher_router  # noqa: E402

_PASSTHROUGH_PREFIXES = ("/docs", "/redoc", "/openapi", "/launcher", "/api/local")
_LAUNCHER_PAGE = Path(__file__).resolve().parent / "launcher.html"

_MISSING_BUILD_CSS = (
    "html,body{height:100%;margin:0}"
    "body{display:flex;flex-direction:column;align-items:center;"
    "justify-content:center;font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
    "background:#08143f;color:#f8faff;text-align:center;padding:0 32px}"
    "h1{font-size:18px;margin:0 0 12px}"
    "p{color:#c9d5ff;font-size:14px;max-width:34rem;line-height:1.55}"
)
_MISSING_BUILD_PAGE = (
    '<!doctype html><html><head><meta charset="utf-8"><title>Setup needed</title>'
    f"<style>{_MISSING_BUILD_CSS}</style></head>"
    "<body><h1>Setup &amp; Repair required</h1>"
    "<p>Open Setup &amp; Diagnostics from the app window to check and repair this "
    "installation. If the interface is still unavailable, use Open Releases there "
    "to reinstall the latest self-contained app.</p>"
    "</body></html>"
)

app.include_router(launcher_router)


@app.get("/launcher", include_in_schema=False)
def launcher_page() -> FileResponse:
    return FileResponse(_LAUNCHER_PAGE)


def _index_response():
    """The SPA entry point, or a friendly setup page when the build is missing."""
    index = DIST_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
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
        and not path.startswith(_PASSTHROUGH_PREFIXES)
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
        candidate = (DIST_DIR / full_path).resolve()
        # Keep path traversal inside the dist directory.
        if candidate.is_file() and candidate.is_relative_to(DIST_DIR.resolve()):
            return FileResponse(candidate)
    return _index_response()
