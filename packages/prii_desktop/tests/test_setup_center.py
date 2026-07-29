"""Fresh-machine tests for UI-only setup state, repair, and diagnostics."""

from __future__ import annotations

import json
import os
from pathlib import Path

from prii_desktop import DesktopConfig
from prii_desktop.setup_center import (
    SetupBridge,
    application_support_dir,
    configure,
    default_workspace_dir,
    diagnostics,
    read_state,
    render_setup_html,
    setup_complete,
)


def _config(tmp_path: Path) -> DesktopConfig:
    dist = tmp_path / "bundle" / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    icon = tmp_path / "bundle" / "assets" / "branding" / "icon-256.png"
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"png")
    return DesktopConfig(
        app_title="Test App",
        app_id="Test App",
        app_import="unused:app",
        repo_root=tmp_path / "bundle",
        dist_dir=dist,
        icon_path=icon,
        state_dir=tmp_path / "support",
        data_env_var="TEST_APP_DATA_HOME",
        brand_accent="#0573e4",
        brand_accent_strong="#075fb1",
    )


def test_macos_application_support_path(tmp_path):
    config = DesktopConfig(
        app_title="Skywatcher",
        app_id="Skywatcher",
        app_import="unused:app",
        repo_root=tmp_path,
        dist_dir=tmp_path,
    )
    assert application_support_dir(
        config, platform="darwin", home=tmp_path
    ) == tmp_path / "Library" / "Application Support" / "Skywatcher"


def test_fresh_setup_creates_workspace_and_atomic_record(tmp_path):
    config = _config(tmp_path)
    workspace = tmp_path / "chosen workspace"
    state = configure(config, workspace)

    assert setup_complete(config)
    assert read_state(config) == state
    assert json.loads((tmp_path / "support" / "setup.json").read_text()) == state
    assert all((workspace / name).is_dir() for name in ("data", "exports", "logs"))
    assert not list((tmp_path / "support").glob(".setup-*.json"))
    assert Path(os.environ["PRII_DATA_HOME"]) == workspace.resolve()
    assert Path(os.environ["TEST_APP_DATA_HOME"]) == workspace.resolve()


def test_invalid_or_old_state_returns_to_first_run(tmp_path):
    config = _config(tmp_path)
    path = tmp_path / "support" / "setup.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"setup_version": 0}', encoding="utf-8")
    assert read_state(config) is None
    assert setup_complete(config) is False


def test_diagnostics_cover_bundle_icon_workspace_and_state(tmp_path):
    config = _config(tmp_path)
    checks = diagnostics(config)
    by_label = {check["label"]: check for check in checks}
    assert by_label["Application interface"]["status"] == "pass"
    assert by_label["App icon"]["status"] == "pass"
    assert by_label["Workspace"]["status"] == "pass"
    assert by_label["Setup record"]["status"] == "info"


def test_setup_html_is_accessible_and_has_no_command_line_step(tmp_path):
    document = render_setup_html(_config(tmp_path))
    assert '<html lang="en">' in document
    assert 'role="status"' in document
    assert 'aria-live="polite"' in document
    assert "prefers-reduced-motion" in document
    assert "No Terminal, Python, Node.js, or Git installation required." in document
    assert "python desktop/setup.py" not in document


def test_bridge_picker_apply_repair_and_return(tmp_path):
    config = _config(tmp_path)
    chosen = tmp_path / "picker choice"
    bridge = SetupBridge(config, choose_directory=lambda _current: chosen)
    assert bridge.choose_workspace() == str(chosen)

    state = bridge.apply(str(chosen))
    assert state["configured"] is True
    assert bridge.completed.is_set()

    repaired = bridge.repair()
    assert repaired["workspace"] == str(chosen.resolve())
    assert repaired["diagnostics"][-1]["status"] == "pass"
    assert bridge.return_to_app() is False


def test_running_app_setup_saves_and_requests_restart(tmp_path):
    config = _config(tmp_path)
    restarts: list[bool] = []
    bridge = SetupBridge(config, restart_app=lambda: restarts.append(True))
    bridge.set_app_url("http://127.0.0.1:12345")

    state = bridge.apply(str(tmp_path / "new workspace"))

    assert state["can_return"] is True
    assert restarts == [True]
    assert "Save & Restart App" in render_setup_html(config)


def test_recommended_workspace_is_stable(tmp_path):
    config = _config(tmp_path)
    assert default_workspace_dir(config) == tmp_path / "support" / "Workspace"
