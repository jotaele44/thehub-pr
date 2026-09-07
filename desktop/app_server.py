"""Thin TheHub ASGI adapter: local launcher routes plus shared SPA serving."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.responses import FileResponse  # noqa: E402
from prii_desktop import DesktopConfig, attach_spa  # noqa: E402
from server.backend.main import app  # noqa: E402

from desktop import config  # noqa: E402
from desktop.launcher_api import router as launcher_router  # noqa: E402

_LAUNCHER_PAGE = Path(__file__).resolve().parent / "launcher.html"

app.include_router(launcher_router)


@app.get("/launcher", include_in_schema=False)
def launcher_page() -> FileResponse:
    return FileResponse(_LAUNCHER_PAGE)


def _prioritize_desktop_routes() -> None:
    """Keep desktop-only routes ahead of the backend SPA catch-all.

    The imported Hub backend registers /{full_path:path} when its frontend dist
    exists. The desktop adapter adds /api/local/* after that import, so these
    routes must be moved before the catch-all or they are shadowed as unknown
    API paths.
    """
    desktop_routes = []
    remaining_routes = []
    for route in app.router.routes:
        path = getattr(route, "path", "")
        if path == "/launcher" or path.startswith("/api/local"):
            desktop_routes.append(route)
        else:
            remaining_routes.append(route)

    insert_at = next(
        (
            index
            for index, route in enumerate(remaining_routes)
            if getattr(route, "path", "") == "/{full_path:path}"
        ),
        len(remaining_routes),
    )
    app.router.routes[:] = (
        remaining_routes[:insert_at] + desktop_routes + remaining_routes[insert_at:]
    )


_prioritize_desktop_routes()


attach_spa(
    app,
    config.DIST_DIR,
    config=DesktopConfig.from_module(config),
    passthrough_prefixes=(
        "/docs",
        "/redoc",
        "/openapi",
        "/launcher",
        "/api/local",
    ),
)
