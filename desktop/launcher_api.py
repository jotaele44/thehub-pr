"""Local federation launcher API (desktop wrapper only).

Lets the hub's desktop window list the sibling PRII producer repos cloned
next to this one and launch each repo's own desktop app. Purely local:
scans the parent directory, spawns the sibling's double-click launcher
script, and tracks the child process. Nothing here touches the hub's
federation backend or mutates any repo.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

REPO_ROOT = Path(__file__).resolve().parents[1]
PARENT = REPO_ROOT.parent

FEDERATION_REPOS = [
    {"repo": "thehub-pr", "name": "TheHub", "domain": "Federation control plane"},
    {"repo": "moneysweep-pr", "name": "MoneySweep", "domain": "Public money"},
    {"repo": "spiderweb-pr", "name": "Spiderweb", "domain": "Spatial / airspace ops"},
    {"repo": "aguayluz-pr", "name": "AguaYLuz", "domain": "Water & grid"},
    {"repo": "ovnis-pr", "name": "OVNIS", "domain": "Case corpus"},
    {"repo": "skywatcher-pr", "name": "Skywatcher", "domain": "Airspace intelligence"},
    {"repo": "centinelas-pr", "name": "Centinelas", "domain": "Pre-signal monitoring"},
]

router = APIRouter(prefix="/api/local", tags=["local-launcher"])

_children: dict[str, subprocess.Popen] = {}


def _launcher_script(repo_dir: Path) -> Path | None:
    pattern = "PRII-*.bat" if os.name == "nt" else "PRII-*.sh"
    matches = sorted(repo_dir.glob(pattern))
    return matches[0] if matches else None


def _repo_status(entry: dict[str, str]) -> dict[str, Any]:
    repo_dir = PARENT / entry["repo"]
    child = _children.get(entry["repo"])
    running = child is not None and child.poll() is None
    return {
        **entry,
        "is_hub": entry["repo"] == "thehub-pr",
        "present": repo_dir.is_dir(),
        "has_desktop": (repo_dir / "desktop" / "launch.py").is_file(),
        "setup_complete": (repo_dir / "desktop" / ".setup-complete").exists(),
        "running": running,
        "github_url": f"https://github.com/jotaele44/{entry['repo']}",
    }


@router.get("/federation")
def federation_status() -> list[dict[str, Any]]:
    return [_repo_status(entry) for entry in FEDERATION_REPOS]


@router.post("/launch/{repo}")
def launch(repo: str) -> dict[str, Any]:
    entry = next((e for e in FEDERATION_REPOS if e["repo"] == repo), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown federation repo: {repo}")
    if repo == "thehub-pr":
        raise HTTPException(status_code=400, detail="The hub is already running")

    child = _children.get(repo)
    if child is not None and child.poll() is None:
        return {"repo": repo, "status": "already_running", "pid": child.pid}

    repo_dir = PARENT / repo
    if not repo_dir.is_dir():
        raise HTTPException(
            status_code=409,
            detail=f"{repo} is not cloned next to the hub (expected {repo_dir})",
        )

    script = _launcher_script(repo_dir)
    if script is not None and os.name != "nt":
        cmd = ["/bin/sh", str(script)]
    elif script is not None:
        cmd = ["cmd", "/c", str(script)]
    elif (repo_dir / "desktop" / "launch.py").is_file():
        # No double-click script (older checkout): best effort via launch.py.
        venv_py = (
            repo_dir
            / ".venv"
            / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        python = str(venv_py) if venv_py.exists() else sys.executable
        cmd = [python, "desktop/launch.py"]
    else:
        raise HTTPException(
            status_code=409,
            detail=f"{repo} has no desktop wrapper — pull its latest main first",
        )

    child = subprocess.Popen(  # noqa: S603 - launching sibling repo's own launcher
        cmd,
        cwd=repo_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _children[repo] = child
    return {"repo": repo, "status": "launched", "pid": child.pid}
