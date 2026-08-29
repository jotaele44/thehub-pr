"""TheHub FastAPI application compatibility entrypoint.

`main_core.py` is the byte-preserved application implementation that passed the
GIS acquisition-v1 exact-head matrix.  This wrapper re-exports that surface and
mounts narrowly-scoped application extensions without regenerating the passed
core file.
"""
from server.backend.main_core import *  # noqa: F401,F403
from server.backend.main_core import app
from server.backend.gis_proxy import router as gis_proxy_router

app.include_router(gis_proxy_router)
