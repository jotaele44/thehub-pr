"""Shared desktop-wrapper runtime for PRII producers.

Public API:
- ``DesktopConfig`` — per-producer config (built from ``desktop/config.py``).
- ``make_desktop_app(config)`` — producer FastAPI app + same-origin SPA serving.
- ``launch(config)`` — native setup/repair + branded local app lifecycle.
"""

from __future__ import annotations

from .appserver import attach_spa, make_desktop_app
from .config import DesktopConfig
from .launcher import launch
from .setup_ui import contrast_ratio, render_setup_html, run_diagnostics

__all__ = [
    "DesktopConfig",
    "attach_spa",
    "contrast_ratio",
    "launch",
    "make_desktop_app",
    "render_setup_html",
    "run_diagnostics",
]
__version__ = "0.2.0"
