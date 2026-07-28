"""Contract tests for TheHub's thin shared-runtime desktop adapter.

Launcher behavior is covered by packages/prii_desktop/tests. These checks keep
TheHub's product adapter declarative and prevent runtime logic from being
copied back into the repository shim.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "desktop" / "launch.py"
CONFIG = REPO_ROOT / "desktop" / "config.py"


def test_launcher_is_a_thin_shared_runtime_adapter():
    source = LAUNCHER.read_text(encoding="utf-8")

    assert len(source.splitlines()) <= 40
    assert "from prii_desktop import DesktopConfig, launch" in source
    assert "launch(DesktopConfig.from_module(config))" in source
    assert "uvicorn" not in source
    assert "webview.create_window" not in source


def test_thehub_desktop_identity_and_custom_server_are_explicit():
    source = CONFIG.read_text(encoding="utf-8")

    assert 'APP_ID = "thehub"' in source
    assert 'APP_ACCENT = "#0B39CA"' in source
    assert 'DESKTOP_APP_IMPORT = "desktop.app_server:app"' in source
