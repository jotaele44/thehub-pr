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


def test_pyinstaller_bundles_the_federation_snapshot():
    """The frozen app runs the same lifespan and seeds from this file.

    Without it in `datas`, `_load_snapshot` returns None in a frozen build,
    seeding falls back to registry-only, and the Gates page ships empty in the
    standalone product.
    """
    spec = (REPO_ROOT / "desktop" / "pyinstaller.spec").read_text()
    assert 'REPO_ROOT / "data" / "federation_status.json"' in spec
    assert (REPO_ROOT / "data" / "federation_status.json").exists()


def test_docker_image_carries_the_data_directory():
    """The container path needs the same snapshot the desktop bundle does."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    assert "COPY data ./data" in dockerfile
    ignored = (REPO_ROOT / ".dockerignore").read_text().splitlines()
    assert not any(line.strip().rstrip("/") == "data" for line in ignored)


def test_backend_requirements_cover_unconditional_imports():
    """desktop-build.yml installs this file, never the project itself.

    `server/backend/main.py` imports `federation_manager_api` unconditionally,
    which imports `federation_manager`, which imports `jsonschema` at module
    scope. The Dockerfile installs the project (`pip install -e ".[server]"`) so
    it picks jsonschema up as a core dependency, but the desktop build installs
    only this file plus requirements-desktop.txt — so an omission here crashes
    the frozen app on startup rather than degrading.
    """
    text = (REPO_ROOT / "server" / "backend" / "requirements.txt").read_text()
    listed = {
        line.split(">=")[0].split("==")[0].split("[")[0].strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    }
    for package in ("fastapi", "uvicorn", "pyyaml", "cryptography", "jsonschema"):
        assert package in listed, f"{package} is imported by the backend but unlisted"
