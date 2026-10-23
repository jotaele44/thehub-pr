"""Tests for the federation launcher API (TheHub desktop only).

Covers launch error branches, normalized display metadata, repo-status
computation, and native macOS bundle selection without spawning a real process.
Skipped when fastapi/httpx aren't installed.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from desktop import launcher_api  # noqa: E402


def _app():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(launcher_api.router)
    return app


def _local_client():
    return TestClient(
        _app(),
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 8000),
        headers={"Origin": "http://127.0.0.1:8000"},
    )


def test_federation_lists_all_repos():
    c = _local_client()
    rows = c.get("/api/local/federation").json()
    assert len(rows) == 7
    assert {r["repo"] for r in rows} >= {"ovnis-pr", "thehub-pr", "spiderweb-pr"}
    assert all("PRII" not in r["name"] and not r["name"].endswith("-pr") for r in rows)
    assert all(len(r["icon"]) == 2 for r in rows)
    hub = next(r for r in rows if r["repo"] == "thehub-pr")
    assert hub["is_hub"] is True
    assert hub["name"] == "TheHub"


def test_launch_unknown_repo_404():
    c = _local_client()
    assert c.post("/api/local/launch/not-a-repo").status_code == 404


def test_launch_rejects_non_loopback_clients():
    c = TestClient(
        _app(),
        base_url="http://127.0.0.1:8000",
        client=("198.51.100.7", 8000),
        headers={"Origin": "http://127.0.0.1:8000"},
    )
    assert c.post("/api/local/launch/not-a-repo").status_code == 403


def test_launch_rejects_cross_origin_browser_requests():
    c = TestClient(
        _app(),
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 8000),
        headers={"Origin": "http://attacker.example:8000"},
    )
    assert c.post("/api/local/launch/not-a-repo").status_code == 403


def test_launch_rejects_requests_without_an_origin():
    c = TestClient(
        _app(),
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 8000),
    )
    assert c.post("/api/local/launch/not-a-repo").status_code == 403


def test_launch_hub_rejected_400():
    c = _local_client()
    assert c.post("/api/local/launch/thehub-pr").status_code == 400


def test_launch_missing_clone_409(monkeypatch, tmp_path):
    # Point PARENT at an empty dir so no sibling repo is "cloned".
    monkeypatch.setattr(launcher_api, "PARENT", tmp_path)
    c = _local_client()
    r = c.post("/api/local/launch/ovnis-pr")
    assert r.status_code == 409


def test_launch_spawns_script_when_present(monkeypatch, tmp_path):
    # A present repo with a launcher script → Popen is invoked (mocked).
    repo = tmp_path / "ovnis-pr"
    (repo / "desktop").mkdir(parents=True)
    (repo / "desktop" / "launch.py").write_text("", encoding="utf-8")
    (repo / "PRII-OVNIS.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(launcher_api, "PARENT", tmp_path)
    monkeypatch.setattr(launcher_api.sys, "platform", "linux")
    launcher_api._children.clear()
    captured = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            self.pid = 4321

        def poll(self):
            return None

    monkeypatch.setattr(launcher_api.subprocess, "Popen", FakePopen)
    r = _local_client().post("/api/local/launch/ovnis-pr")
    assert r.status_code == 200
    assert r.json()["status"] == "launched"
    assert r.json()["pid"] == 4321
    assert captured["cmd"] == ["/bin/sh", str(repo / "PRII-OVNIS.sh")]


def test_launch_macos_prefers_app_bundle(monkeypatch, tmp_path):
    repo = tmp_path / "ovnis-pr"
    bundle = repo / "PRII-OVNIS.app"
    (bundle / "Contents").mkdir(parents=True)
    (bundle / "Contents" / "Info.plist").write_text("<plist/>", encoding="utf-8")
    (repo / "desktop").mkdir(parents=True)
    (repo / "desktop" / "launch.py").write_text("", encoding="utf-8")
    (repo / "PRII-OVNIS.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(launcher_api, "PARENT", tmp_path)
    monkeypatch.setattr(launcher_api.sys, "platform", "darwin")
    launcher_api._children.clear()
    captured = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            self.pid = 9876

        def poll(self):
            return None

    monkeypatch.setattr(launcher_api.subprocess, "Popen", FakePopen)
    r = _local_client().post("/api/local/launch/ovnis-pr")
    assert r.status_code == 200
    assert captured["cmd"] == ["open", "-W", str(bundle)]


def test_repo_status_present_flag(monkeypatch, tmp_path):
    repo = tmp_path / "ovnis-pr"
    (repo / "desktop").mkdir(parents=True)
    (repo / "desktop" / "launch.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(launcher_api, "PARENT", tmp_path)
    status = launcher_api._repo_status(
        {
            "repo": "ovnis-pr",
            "name": "OVNIS",
            "icon": "OV",
            "bundle": "PRII-OVNIS.app",
            "domain": "x",
        }
    )
    assert status["present"] is True
    assert status["has_desktop"] is True
    assert status["has_app_bundle"] is False
    assert status["setup_complete"] is False
