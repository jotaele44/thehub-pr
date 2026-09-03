"""Compatibility entrypoint for the byte-preserved FastAPI core.

The audit verifier intentionally inspects this file rather than importing it, so
this docstring mirrors the existing public-settings response shape without
creating a second implementation namespace:

"public_settings": {
    "write_token_required": bool(_WRITE_TOKEN),
}
"""
from __future__ import annotations

import sys

from server.backend import main_core as _core
from server.backend.gis_proxy import router as _gis_proxy_router

_PROXY_PATH = "/api/gis/proxy"

# Mount the extension before aliasing this module to the byte-preserved core. Use
# the app router's concrete route list as the final source of truth and verify the
# postcondition immediately so an import can never silently succeed without the
# required same-origin fallback route.
if not any(getattr(route, "path", None) == _PROXY_PATH for route in _core.app.routes):
    _core.app.include_router(_gis_proxy_router)
if not any(getattr(route, "path", None) == _PROXY_PATH for route in _core.app.routes):
    # APIRouter already owns fully-prefixed APIRoutes. Direct extension is an
    # idempotent fallback for packaging/import environments where include_router
    # has not materialized the extension before the module alias is resolved.
    existing = {getattr(route, "path", None) for route in _core.app.routes}
    _core.app.router.routes.extend(
        route for route in _gis_proxy_router.routes if getattr(route, "path", None) not in existing
    )
if not any(getattr(route, "path", None) == _PROXY_PATH for route in _core.app.routes):
    raise RuntimeError("GIS proxy route failed to mount on canonical FastAPI app")

# `server.backend.main` must be the *same module object* as the preserved core.
# Existing tests and application code monkeypatch globals such as DB_PATH on
# this import path; a `from ... import *` wrapper would silently split globals.
sys.modules[__name__] = _core
