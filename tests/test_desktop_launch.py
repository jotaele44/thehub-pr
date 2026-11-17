"""Contract tests for TheHub's thin shared-runtime launcher adapter."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("prii_desktop")

from prii_desktop import DesktopConfig  # noqa: E402

from desktop import config, launch  # noqa: E402


def test_main_delegates_to_shared_runtime(monkeypatch):
    captured = []
    monkeypatch.setattr(launch, "launch", captured.append)

    launch.main()

    assert len(captured) == 1
    desktop_config = captured[0]
    assert isinstance(desktop_config, DesktopConfig)
    assert desktop_config.app_title == "TheHub"
    assert desktop_config.app_import == "desktop.app_server:app"
    assert desktop_config.repo_root == Path(config.REPO_ROOT)
    assert desktop_config.dist_dir == Path(config.DIST_DIR)
    assert desktop_config.icon_path == Path(config.ICON_PATH)
    assert desktop_config.attach_frontend is False


def test_adapter_exports_only_its_entrypoint():
    legacy_helpers = {
        "display_url",
        "free_port",
        "running_instance_base",
        "wait_healthy",
        "write_lock",
    }
    assert legacy_helpers.isdisjoint(vars(launch))


def test_launchpad_declaration_is_valid_and_matches_the_app():
    launchpad = pytest.importorskip("prii_desktop.launchpad")

    spec = launchpad.launchpad_spec(DesktopConfig.from_module(config))

    assert spec is not None and spec.has_modes
    # The write credential must be the variable the backend actually guards on,
    # delivered the way the frontend actually reads it (lib/app-params.js).
    assert spec.operator.token_env == "PRII_WRITE_TOKEN"
    assert spec.operator.url_param == "write_token"
    core = (Path(config.REPO_ROOT) / "server/backend/main_core.py").read_text()
    params = (Path(config.FRONTEND_DIR) / "src/lib/app-params.js").read_text()
    assert 'os.environ.get("PRII_WRITE_TOKEN"' in core
    assert "getParamValue('write_token'" in params
    option_envs = {option.env for option in spec.options}
    assert option_envs == {"PRII_GRID_V2_PROFILE_ROOT"}
    assert 'os.environ.get("PRII_GRID_V2_PROFILE_ROOT")' in (
        Path(config.REPO_ROOT) / "server/backend/grid_v2_api.py"
    ).read_text()


def test_launchpad_start_pages_are_real_routes():
    launchpad = pytest.importorskip("prii_desktop.launchpad")

    spec = launchpad.launchpad_spec(DesktopConfig.from_module(config))
    app_routes = (Path(config.FRONTEND_DIR) / "src/App.jsx").read_text()
    for page in spec.start_pages:
        if page.route == "/launcher":  # served by desktop/app_server.py
            continue
        assert f'path="{page.route}"' in app_routes, page.route


def test_launchpad_status_reads_the_selected_workspace(tmp_path, monkeypatch):
    import sqlite3

    pytest.importorskip("prii_desktop.launchpad")
    monkeypatch.setenv(config.DATA_ENV_VAR, str(tmp_path))
    empty = config._launchpad_status()
    assert empty[0]["value"] == "Empty" and empty[0]["status"] == "info"
    assert not (tmp_path / "data").exists()  # a readiness check creates nothing

    (tmp_path / "data").mkdir()
    conn = sqlite3.connect(tmp_path / "data" / "hub.db")
    conn.execute(
        "CREATE TABLE entities (entity_type TEXT, entity_id TEXT, data TEXT, updated_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO entities VALUES (?, ?, '{}', '')",
        [("Programs", "1"), ("Programs", "2"), ("Sources", "1")],
    )
    conn.commit()
    conn.close()
    loaded = config._launchpad_status()
    assert loaded[0]["value"] == "3 records" and "2 collections" in loaded[0]["detail"]
    assert loaded[1]["label"] == "Producer checkouts"
