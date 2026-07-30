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
