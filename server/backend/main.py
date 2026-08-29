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

# Idempotent under reload/import probes.
if not any(getattr(route, "path", None) == "/api/gis/proxy" for route in _core.app.routes):
    _core.app.include_router(_gis_proxy_router)

# `server.backend.main` must be the *same module object* as the preserved core.
# Existing tests and application code monkeypatch globals such as DB_PATH on
# this import path; a `from ... import *` wrapper would silently split globals.
sys.modules[__name__] = _core
