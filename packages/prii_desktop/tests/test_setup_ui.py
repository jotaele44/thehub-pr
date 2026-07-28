"""Accessibility and fresh-machine contracts for the native setup surface."""

from pathlib import Path

import pytest

from prii_desktop import setup_ui
from prii_desktop.config import DesktopConfig


@pytest.fixture
def desktop_config(tmp_path: Path) -> DesktopConfig:
    frontend = tmp_path / "dist" / "index.html"
    frontend.parent.mkdir()
    frontend.write_text("<!doctype html><title>App</title>", encoding="utf-8")
    icon = tmp_path / "icon-256.png"
    icon.write_bytes(b"\x89PNG\r\n\x1a\n")
    return DesktopConfig(
        app_title="Test App",
        app_import="test_app:app",
        repo_root=tmp_path,
        dist_dir=frontend.parent,
        app_id="test-app",
        accent="#0B39CA",
        icon_path=icon,
        frontend_entry=frontend,
        releases_url="https://github.com/example/test-app/releases",
    )


@pytest.mark.parametrize(
    ("accent", "foreground"),
    [
        ("#E3680F", "#000000"),
        ("#DC1606", "#ffffff"),
        ("#0B9DEE", "#000000"),
        ("#0B39CA", "#ffffff"),
        ("#12E0D6", "#000000"),
    ],
)
def test_federation_accents_choose_wcag_foreground(accent, foreground):
    assert setup_ui.accent_foreground(accent) == foreground
    assert setup_ui.contrast_ratio(accent, foreground) >= 4.5


def test_setup_state_round_trip(tmp_path, monkeypatch, desktop_config):
    monkeypatch.setattr(setup_ui, "_application_support", lambda: tmp_path / "support")
    selected = tmp_path / "application-data"

    assert setup_ui.setup_complete(desktop_config) is False
    setup_ui.save_state(desktop_config, selected)

    assert setup_ui.setup_complete(desktop_config) is True
    assert setup_ui.selected_data_directory(desktop_config) == selected.resolve()
    assert setup_ui.apply_setup_environment(desktop_config) == selected.resolve()


def test_required_fresh_machine_diagnostics_pass(tmp_path, desktop_config):
    checks = setup_ui.run_diagnostics(
        desktop_config,
        data_directory=tmp_path / "fresh-data",
    )
    assert setup_ui.diagnostics_pass(checks)
    assert {check["id"] for check in checks} >= {
        "runtime",
        "interface",
        "icon",
        "storage",
        "loopback",
    }


def test_setup_html_is_ui_only_and_accessible(tmp_path, monkeypatch, desktop_config):
    monkeypatch.setattr(setup_ui, "_application_support", lambda: tmp_path / "support")
    html = setup_ui.render_setup_html(desktop_config)
    lowered = html.lower()

    assert "no terminal, python, node.js, or git required" in lowered
    assert 'role="status"' in lowered
    assert 'aria-live="polite"' in lowered
    assert 'for="data-dir"' in lowered
    assert "run diagnostics" in lowered
    assert "repair local setup" in lowered
    assert "open releases" in lowered
    assert "save &amp; launch" in lowered
    assert "python desktop/setup.py" not in lowered
    assert "npm " not in lowered
    assert "pip " not in lowered


def test_setup_smoke_does_not_persist_user_state(desktop_config):
    ok, checks = setup_ui.setup_smoke(desktop_config)
    assert ok
    assert setup_ui.diagnostics_pass(checks)


def test_repair_rewrites_setup_state_without_deleting_data(
    tmp_path, monkeypatch, desktop_config
):
    monkeypatch.setattr(setup_ui, "_application_support", lambda: tmp_path / "support")
    selected = tmp_path / "application-data"
    evidence = selected / "evidence.json"
    selected.mkdir()
    evidence.write_text('{"kept": true}\n', encoding="utf-8")
    bridge = setup_ui.SetupBridge(
        desktop_config,
        health_url="http://127.0.0.1:9/health",
        start_callback=lambda: None,
    )

    result = bridge.repair_setup(str(selected))

    assert result["ok"] is True
    assert setup_ui.setup_complete(desktop_config) is True
    assert evidence.read_text(encoding="utf-8") == '{"kept": true}\n'
