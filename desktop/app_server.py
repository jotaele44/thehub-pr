"""Thin TheHub ASGI adapter: local launcher routes plus shared SPA serving."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from prii_desktop import DesktopConfig, attach_spa  # noqa: E402
from server.backend.main import app  # noqa: E402

from desktop import config  # noqa: E402
from desktop.launcher_api import router as launcher_router  # noqa: E402

_LAUNCHER_PAGE = Path(__file__).resolve().parent / "launcher.html"

_SPA_CATCH_ALL = "/{full_path:path}"

# Snapshot the backend's routes so the desktop-only additions below can be told
# apart by identity. Newer FastAPI wraps include_router() results in path-less
# route objects, so matching on route.path would silently miss them.
_backend_routes = {id(route) for route in app.router.routes}

app.include_router(launcher_router)


@app.get("/launcher", include_in_schema=False)
def launcher_page() -> FileResponse:
    return FileResponse(_LAUNCHER_PAGE)


def _prioritize_desktop_routes(target: FastAPI, known_routes: set[int]) -> None:
    """Keep routes added after ``known_routes`` ahead of the SPA catch-all.

    The imported Hub backend registers /{full_path:path} when its frontend dist
    exists. The desktop adapter adds /launcher and /api/local/* after that
    import, so these routes must be moved before the catch-all or they are
    shadowed as unknown API paths.
    """
    routes = target.router.routes
    desktop_routes = [route for route in routes if id(route) not in known_routes]
    remaining_routes = [route for route in routes if id(route) in known_routes]

    insert_at = next(
        (
            index
            for index, route in enumerate(remaining_routes)
            if getattr(route, "path", "") == _SPA_CATCH_ALL
        ),
        len(remaining_routes),
    )
    routes[:] = (
        remaining_routes[:insert_at] + desktop_routes + remaining_routes[insert_at:]
    )


_prioritize_desktop_routes(app, _backend_routes)


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
