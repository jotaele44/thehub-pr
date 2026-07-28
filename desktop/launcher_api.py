"""Local federation launcher API for the desktop wrapper.

Lists sibling federation repositories cloned next to TheHub and launches each
repository's desktop app. On macOS the checked-in .app bundle is preferred so
LaunchServices preserves the app's own display name and icon. The shell-script
launcher remains the compatibility fallback for other systems and older clones.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

REPO_ROOT = Path(__file__).resolve().parents[1]
PARENT = REPO_ROOT.parent

FEDERATION_REPOS = [
    {
        "repo": "thehub-pr",
        "name": "TheHub",
        "icon": "TH",
        "bundle": "PRII-THEHUB.app",
        "domain": "Federation control plane",
    },
    {
        "repo": "moneysweep-pr",
        "name": "MoneySweep",
        "icon": "MS",
        "bundle": "PRII-MONEYSWEEP.app",
        "domain": "Public money",
    },
    {
        "repo": "spiderweb-pr",
        "name": "Spiderweb",
        "icon": "SW",
        "bundle": "PRII-SPIDERWEB.app",
        "domain": "Spatial / airspace ops",
    },
    {
        "repo": "aguayluz-pr",
        "name": "AguaYLuz",
        "icon": "AL",
        "bundle": "PRII-AGUAYLUZ.app",
        "domain": "Water & grid",
    },
    {
        "repo": "ovnis-pr",
        "name": "OVNIS",
        "icon": "OV",
        "bundle": "PRII-OVNIS.app",
        "domain": "Case corpus",
    },
    {
        "repo": "skywatcher-pr",
        "name": "Skywatcher",
        "icon": "SK",
        "bundle": "PRII-SKYWATCHER.app",
        "domain": "Airspace intelligence",
    },
    {
        "repo": "centinelas-pr",
        "name": "Centinelas",
        "icon": "CE",
        "bundle": "PRII-CENTINELAS.app",
        "domain": "Pre-signal monitoring",
    },
]

router = APIRouter(prefix="/api/local", tags=["local-launcher"])

# The federation tile art, one 256px PNG per program, kept as a single copy under
# the hub frontend's public/ dir. launcher.html is served straight off disk and
# has no sibling static dir, so it reaches the art through the route below.
#
# Two locations, in priority order: Vite copies public/ into dist/, and
# desktop/pyinstaller.spec packages server/frontend/dist — not public/. So in a
# frozen build only the dist/ copy exists, and checking public/ alone would make
# every packaged launcher fall back to monograms.
BRANDING_DIRS = (
    REPO_ROOT / "server" / "frontend" / "dist" / "branding",
    REPO_ROOT / "server" / "frontend" / "public" / "branding",
)

_children: dict[str, subprocess.Popen] = {}


def _launcher_script(repo_dir: Path) -> Path | None:
    pattern = "PRII-*.bat" if os.name == "nt" else "PRII-*.sh"
    matches = sorted(repo_dir.glob(pattern))
    return matches[0] if matches else None


def _app_bundle(repo_dir: Path, entry: dict[str, str]) -> Path | None:
    bundle = repo_dir / entry["bundle"]
    if bundle.is_dir() and (bundle / "Contents" / "Info.plist").is_file():
        return bundle
    return None


def _icon_path(repo: str) -> Path | None:
    """The program's tile art, or None so the caller can fall back to initials."""
    for base in BRANDING_DIRS:
        candidate = base / f"{repo}.png"
        if candidate.is_file():
            return candidate
    return None


def _repo_status(entry: dict[str, str]) -> dict[str, Any]:
    repo_dir = PARENT / entry["repo"]
    child = _children.get(entry["repo"])
    running = child is not None and child.poll() is None
    bundle = _app_bundle(repo_dir, entry)
    return {
        **entry,
        # None when the art is missing; the tile then renders entry["icon"],
        # the two-letter monogram, exactly as it did before.
        "icon_url": (
            f"/api/local/federation/icon/{entry['repo']}"
            if _icon_path(entry["repo"])
            else None
        ),
        "is_hub": entry["repo"] == "thehub-pr",
        "present": repo_dir.is_dir(),
        "has_desktop": bundle is not None or (repo_dir / "desktop" / "launch.py").is_file(),
        "has_app_bundle": bundle is not None,
        "setup_complete": (repo_dir / "desktop" / ".setup-complete").exists(),
        "running": running,
        "github_url": f"https://github.com/jotaele44/{entry['repo']}",
    }


@router.get("/federation")
def federation_status() -> list[dict[str, Any]]:
    return [_repo_status(entry) for entry in FEDERATION_REPOS]


@router.get("/federation/icon/{repo}")
def federation_icon(repo: str) -> FileResponse:
    """Serve a program's tile art. Only known program ids resolve, so the path
    parameter can never walk out of BRANDING_DIR."""
    if not any(entry["repo"] == repo for entry in FEDERATION_REPOS):
        raise HTTPException(status_code=404, detail=f"Unknown federation repo: {repo}")
    path = _icon_path(repo)
    if path is None:
        raise HTTPException(status_code=404, detail=f"No icon for {repo}")
    return FileResponse(path, media_type="image/png")


@router.post("/launch/{repo}")
def launch(repo: str) -> dict[str, Any]:
    entry = next((e for e in FEDERATION_REPOS if e["repo"] == repo), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown federation repo: {repo}")
    if repo == "thehub-pr":
        raise HTTPException(status_code=400, detail="TheHub is already running")

    child = _children.get(repo)
    if child is not None and child.poll() is None:
        return {"repo": repo, "status": "already_running", "pid": child.pid}

    repo_dir = PARENT / repo
    if not repo_dir.is_dir():
        raise HTTPException(
            status_code=409,
            detail=f"{entry['name']} is not cloned next to TheHub (expected {repo_dir})",
        )

    bundle = _app_bundle(repo_dir, entry)
    script = _launcher_script(repo_dir)

    if sys.platform == "darwin" and bundle is not None:
        # LaunchServices reads Info.plist and AppIcon.icns. -W keeps this child
        # alive until the app closes so the launcher can report RUNNING status.
        cmd = ["open", "-W", str(bundle)]
    elif script is not None and os.name != "nt":
        cmd = ["/bin/sh", str(script)]
    elif script is not None:
        cmd = ["cmd", "/c", str(script)]
    elif (repo_dir / "desktop" / "launch.py").is_file():
        # No bundle/script (older checkout): best effort via launch.py.
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
            detail=f"{entry['name']} has no desktop wrapper — pull its latest main first",
        )

    child = subprocess.Popen(  # noqa: S603 - launching a registered sibling app
        cmd,
        cwd=repo_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _children[repo] = child
    return {"repo": repo, "status": "launched", "pid": child.pid}
