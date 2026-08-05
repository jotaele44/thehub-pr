"""Shared desktop-wrapper runtime for PRII producers.

Public API:
- ``DesktopConfig`` — per-producer config (built from ``desktop/config.py``).
- ``make_desktop_app(config)`` — producer FastAPI app + same-origin SPA serving.
- ``launch(config)`` — native-window launcher (uvicorn + pywebview, browser fallback).
"""

from __future__ import annotations

from .appserver import attach_spa, desktop_controls_script, make_desktop_app
from .config import DesktopConfig
from .launcher import launch
from .setup_center import (
    SetupBridge,
    application_support_dir,
    diagnostics,
    render_setup_html,
    setup_complete,
)

__all__ = [
    "DesktopConfig",
    "SetupBridge",
    "application_support_dir",
    "attach_spa",
    "desktop_controls_script",
    "diagnostics",
    "launch",
    "make_desktop_app",
    "render_setup_html",
    "setup_complete",
]
__version__ = "0.2.0"
