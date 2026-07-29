"""Lightweight tests for prii_desktop that need no fastapi/uvicorn/pywebview.

The heavy runtime deps are provided by the consuming producer's environment;
here we only exercise the pure, import-cheap surface.
"""

from pathlib import Path

import prii_desktop
from prii_desktop import DesktopConfig
from prii_desktop.launcher import display_url


def test_public_api():
    assert hasattr(prii_desktop, "launch")
    assert hasattr(prii_desktop, "make_desktop_app")
    assert hasattr(prii_desktop, "DesktopConfig")
    assert hasattr(prii_desktop, "SetupBridge")
    assert hasattr(prii_desktop, "diagnostics")


def test_desktop_config_from_module():
    class _Mod:
        APP_TITLE = "OVNIS — PRII Case Corpus"
        APP_IMPORT = "server.backend.main:app"
        REPO_ROOT = Path("/tmp/ovnis")
        DIST_DIR = Path("/tmp/ovnis/dashboard/dist")
        HEALTH_PATH = "/health"
        APP_ID = "OVNIS"
        BRAND_ACCENT = "#7c3aed"
        BRAND_ACCENT_STRONG = "#5b21b6"
        DATA_ENV_VAR = "OVNIS_DATA_HOME"

    cfg = DesktopConfig.from_module(_Mod)
    assert cfg.app_title == "OVNIS — PRII Case Corpus"
    assert cfg.app_import == "server.backend.main:app"
    assert cfg.health_path == "/health"
    assert cfg.repo_root == Path("/tmp/ovnis")
    assert cfg.app_id == "OVNIS"
    assert cfg.brand_accent == "#7c3aed"
    assert cfg.data_env_var == "OVNIS_DATA_HOME"


def test_display_url_route():
    assert display_url("http://127.0.0.1:8000", []) == "http://127.0.0.1:8000"
    assert (
        display_url("http://127.0.0.1:8000", ["--route", "/launcher"])
        == "http://127.0.0.1:8000/launcher"
    )
