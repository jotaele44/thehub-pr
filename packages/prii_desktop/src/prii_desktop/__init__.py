"""Shared desktop-wrapper runtime for PRII producers.

Public API:
- ``DesktopConfig`` — per-producer config (built from ``desktop/config.py``).
- ``make_desktop_app(config)`` — producer FastAPI app + same-origin SPA serving.
- ``launch(config)`` — native-window launcher (uvicorn + pywebview, browser fallback).
"""

from __future__ import annotations

from .appserver import attach_spa, make_desktop_app
from .config import DesktopConfig
from .launcher import launch

__all__ = ["DesktopConfig", "make_desktop_app", "attach_spa", "launch"]
__version__ = "0.1.0"
