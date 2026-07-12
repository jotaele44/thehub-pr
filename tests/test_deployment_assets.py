"""Hermetic checks on the deployment assets (no docker daemon required)."""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_entrypoint_and_healthcheck():
    text = (REPO_ROOT / "Dockerfile").read_text()
    assert "server.backend.main:app" in text
    assert "/healthz" in text
    assert 'pip install --no-cache-dir -e ".[server]"' in text
    # runs as a non-root user
    assert "USER appuser" in text


def test_compose_parses_and_maps_port():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    service = compose["services"]["thehub"]
    assert service["build"] == "."
    assert "8000:8000" in service["ports"]
    assert any(v.endswith("/app/data") for v in service["volumes"])


def test_systemd_unit_has_execstart():
    text = (REPO_ROOT / "deploy" / "thehub-mcp.service").read_text()
    assert "ExecStart=" in text
    assert "uvicorn server.backend.main:app" in text


def test_dockerignore_excludes_heavy_dirs():
    text = (REPO_ROOT / ".dockerignore").read_text()
    for pattern in (".git", "server/frontend/node_modules", ".venv"):
        assert pattern in text
