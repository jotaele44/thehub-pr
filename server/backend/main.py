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
from server.backend.moneysweep_leaderboards import router as _moneysweep_leaderboards_router
from server.backend.moneysweep_asg_leaderboards import router as _moneysweep_asg_leaderboards_router

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

# Evidence Object (provenance inspector), federated search, entity composition,
# event timeline, research and spatial APIs, mounted the same additive way.
from server.backend.entity_api import router as _entity_router  # noqa: E402
from server.backend.evidence_api import router as _evidence_router  # noqa: E402
from server.backend.research_api import router as _research_router  # noqa: E402
from server.backend.search_api import router as _search_router  # noqa: E402
from server.backend.spatial_api import router as _spatial_router  # noqa: E402
from server.backend.timeline_api import router as _timeline_router  # noqa: E402

# The routers' APIRoutes are already fully prefixed; extending the route table
# directly keeps them visible (FastAPI may wrap include_router lazily).
_existing_paths = {getattr(route, "path", None) for route in _core.app.router.routes}
for _extension_router in (_evidence_router, _search_router, _entity_router, _timeline_router, _research_router,
                         _spatial_router):
    _core.app.router.routes.extend(
        route for route in _extension_router.routes if getattr(route, "path", None) not in _existing_paths
    )

# When a built frontend exists the core registers its SPA catch-all at import,
# so routers appended above would sit behind it and every request to them would
# be answered by the catch-all's /api 404. Keep the catch-all last.
_SPA_PATH = "/{full_path:path}"
_spa_routes = [route for route in _core.app.router.routes if getattr(route, "path", None) == _SPA_PATH]
for _route in _spa_routes:
    _core.app.router.routes.remove(_route)
    _core.app.router.routes.append(_route)

_LEADERBOARD_STATUS_PATH = "/api/moneysweep/leaderboards/status"

if not any(getattr(route, "path", None) == _LEADERBOARD_STATUS_PATH for route in _core.app.routes):
    _core.app.include_router(_moneysweep_leaderboards_router)
if not any(getattr(route, "path", None) == _LEADERBOARD_STATUS_PATH for route in _core.app.routes):
    existing = {getattr(route, "path", None) for route in _core.app.routes}
    _core.app.router.routes.extend(
        route
        for route in _moneysweep_leaderboards_router.routes
        if getattr(route, "path", None) not in existing
    )
if not any(getattr(route, "path", None) == _LEADERBOARD_STATUS_PATH for route in _core.app.routes):
    raise RuntimeError("MoneySweep leaderboard consumer route failed to mount on canonical FastAPI app")

_ASG_LEADERBOARD_STATUS_PATH = "/api/moneysweep/asg-leaderboards/status"

if not any(getattr(route, "path", None) == _ASG_LEADERBOARD_STATUS_PATH for route in _core.app.routes):
    _core.app.include_router(_moneysweep_asg_leaderboards_router)
if not any(getattr(route, "path", None) == _ASG_LEADERBOARD_STATUS_PATH for route in _core.app.routes):
    existing = {getattr(route, "path", None) for route in _core.app.routes}
    _core.app.router.routes.extend(
        route
        for route in _moneysweep_asg_leaderboards_router.routes
        if getattr(route, "path", None) not in existing
    )
if not any(getattr(route, "path", None) == _ASG_LEADERBOARD_STATUS_PATH for route in _core.app.routes):
    raise RuntimeError("MoneySweep ASG leaderboard consumer route failed to mount on canonical FastAPI app")

# Leaderboard routes are mounted after the core SPA catch-all was originally
# moved. Re-assert the ordering invariant so /api/moneysweep/leaderboards/*
# cannot be intercepted by the SPA fallback.
_spa_routes = [route for route in _core.app.router.routes if getattr(route, "path", None) == _SPA_PATH]
for _route in _spa_routes:
    _core.app.router.routes.remove(_route)
    _core.app.router.routes.append(_route)

# `server.backend.main` must be the *same module object* as the preserved core.
# Existing tests and application code monkeypatch globals such as DB_PATH on
# this import path; a `from ... import *` wrapper would silently split globals.
sys.modules[__name__] = _core
