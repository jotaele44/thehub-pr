"""Tests for the federation launcher API (thehub desktop only).

Covers the launch() error branches and repo-status computation without ever
spawning a real process. Skipped when fastapi/httpx aren't installed.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from starlette.testclient import TestClient  # noqa: E402

from desktop import launcher_api  # noqa: E402


def _app():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(launcher_api.router)
    return app


def test_federation_lists_all_repos():
    c = TestClient(_app())
    rows = c.get("/api/local/federation").json()
    assert len(rows) == 7
    assert {r["repo"] for r in rows} >= {"ovnis-pr", "thehub-pr", "spiderweb-pr"}
    hub = next(r for r in rows if r["repo"] == "thehub-pr")
    assert hub["is_hub"] is True


def test_launch_unknown_repo_404():
    c = TestClient(_app())
    assert c.post("/api/local/launch/not-a-repo").status_code == 404


def test_launch_hub_rejected_400():
    c = TestClient(_app())
    assert c.post("/api/local/launch/thehub-pr").status_code == 400


def test_launch_missing_clone_409(monkeypatch, tmp_path):
    # Point PARENT at an empty dir so no sibling repo is "cloned".
    monkeypatch.setattr(launcher_api, "PARENT", tmp_path)
    c = TestClient(_app())
    r = c.post("/api/local/launch/ovnis-pr")
    assert r.status_code == 409


def test_launch_spawns_when_present(monkeypatch, tmp_path):
    # A present repo with a launcher script → Popen is invoked (mocked).
    repo = tmp_path / "ovnis-pr"
    (repo / "desktop").mkdir(parents=True)
    (repo / "desktop" / "launch.py").write_text("", encoding="utf-8")
    (repo / "PRII-OVNIS.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(launcher_api, "PARENT", tmp_path)
    launcher_api._children.clear()

    class FakePopen:
        def __init__(self, *a, **k):
            self.pid = 4321

        def poll(self):
            return None

    monkeypatch.setattr(launcher_api.subprocess, "Popen", FakePopen)
    r = TestClient(_app()).post("/api/local/launch/ovnis-pr")
    assert r.status_code == 200
    assert r.json()["status"] == "launched"
    assert r.json()["pid"] == 4321


def test_repo_status_present_flag(monkeypatch, tmp_path):
    repo = tmp_path / "ovnis-pr"
    (repo / "desktop").mkdir(parents=True)
    (repo / "desktop" / "launch.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(launcher_api, "PARENT", tmp_path)
    status = launcher_api._repo_status(
        {"repo": "ovnis-pr", "name": "OVNIS", "domain": "x"}
    )
    assert status["present"] is True
    assert status["has_desktop"] is True
    assert status["setup_complete"] is False
