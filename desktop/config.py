"""Desktop-wrapper configuration for this repo.

The desktop/ folder is a shared federation template; only this file differs
between repos.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# User-facing window title of the desktop app.
APP_TITLE = "TheHub"
APP_ID = "TheHub"
BRAND_ACCENT = "#0529a8"
BRAND_ACCENT_STRONG = "#0529a8"
ICON_PATH = REPO_ROOT / "assets" / "branding" / "icon-256.png"
SETUP_VERSION = 1
DATA_ENV_VAR = "THEHUB_DATA_HOME"

# Dotted import path of the FastAPI application object.
APP_IMPORT = "desktop.app_server:app"

# Directory containing the Vite frontend (with package.json).
FRONTEND_DIR = REPO_ROOT / "server" / "frontend"

# Vite build output served by the desktop app.
DIST_DIR = FRONTEND_DIR / "dist"

# Requirement files installed into the private .venv by desktop/setup.py.
REQUIREMENT_FILES = [
    REPO_ROOT / "server" / "backend" / "requirements.txt",
    REPO_ROOT / "requirements-desktop.txt",
]

# Health endpoint used to detect that the backend is up.
HEALTH_PATH = "/health"

# desktop/app_server.py attaches the Hub-only native federation launcher before
# delegating SPA serving to the shared runtime.
ATTACH_FRONTEND = False

# The hub API imports the repo package (yaml/jsonschema); install it editable
# with the fastapi/uvicorn server extra into the private venv.
EXTRA_PIP_SPECS = ["-e", f"{REPO_ROOT}[server]"]

# The frontend reads its API base from these scoped vars (see
# server/frontend/src/lib/app-params.js); blank them at build time so a
# developer .env.local can't point the desktop build at an external backend.
EXTRA_BUILD_ENV = {
    "VITE_HUB_API_BASE_URL": "",
    "VITE_FEDERATION_API_BASE_URL": "",
}


def _launchpad_status() -> list[dict[str, str]]:
    """Readiness rows for the Launch Pad. Runs before the backend exists, so it
    reads the store and the sibling checkouts directly instead of calling the API.
    """
    data_home = os.environ.get(DATA_ENV_VAR, "").strip()
    db_path = (Path(data_home) if data_home else REPO_ROOT) / "data" / "hub.db"
    records = collections = 0
    if db_path.is_file():
        # mode=ro: a readiness check must never create or migrate the store.
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
            records, collections = conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT entity_type) FROM entities"
            ).fetchone()
    if records:
        store = {
            "label": "Federation data",
            "value": f"{records:,} records",
            "status": "pass",
            "detail": f"{collections} collections loaded in {db_path}",
        }
    else:
        store = {
            "label": "Federation data",
            "value": "Empty",
            "status": "info",
            "detail": (
                "The app opens with an empty store. Load federation data with "
                "hub aggregate, hub correlate and hub ingest (see the README)."
            ),
        }

    # Deferred: launcher_api needs fastapi, and this module must stay importable
    # by the stdlib-only setup script.
    from desktop.launcher_api import FEDERATION_REPOS, PARENT

    siblings = [entry for entry in FEDERATION_REPOS if entry["repo"] != REPO_ROOT.name]
    present = [entry["name"] for entry in siblings if (PARENT / entry["repo"]).is_dir()]
    return [
        store,
        {
            "label": "Producer checkouts",
            "value": f"{len(present)} of {len(siblings)}",
            "status": "pass" if present else "info",
            "detail": (
                "Found next to TheHub: " + ", ".join(present)
                if present
                else "No producer repositories are cloned next to TheHub."
            ),
        },
    ]


# Pre-launch screen shown by the shared runtime (prii_desktop.launchpad).
LAUNCHPAD = {
    "tagline": "PRII federation control plane",
    "summary": (
        "TheHub brings the federation's producers into one place: it aggregates "
        "their exports, correlates records across domains, and lets you search, "
        "review and trace evidence without switching between producer apps."
    ),
    "highlights": [
        "Cross-producer search and timeline",
        "Crossover and anomaly overlap",
        "Evidence provenance",
        "Federation app launcher",
    ],
    "status": _launchpad_status,
    "start_pages": [
        {"route": "/", "label": "Recent Activity",
         "description": "What changed across the federation since you last looked."},
        {"route": "/hub", "label": "Hub",
         "description": "Control-plane overview of every producer."},
        {"route": "/search", "label": "Search",
         "description": "Search records across all producers."},
        {"route": "/timeline", "label": "Timeline",
         "description": "Events from every producer on one time axis."},
        {"route": "/constellation", "label": "Constellation",
         "description": "The federation as a graph of entities and links."},
        {"route": "/crossover", "label": "Crossover",
         "description": "Records that connect two or more producers."},
        {"route": "/cases", "label": "Cases",
         "description": "Case files and reconstructions."},
        {"route": "/sources", "label": "Sources",
         "description": "Unified source catalogue."},
        {"route": "/source-monitor", "label": "Source Monitor",
         "description": "Freshness of each monitored source."},
        {"route": "/gis", "label": "GIS Workspace",
         "description": "Map layers and spatial analysis."},
        {"route": "/research", "label": "Research",
         "description": "Research workspace and case reconstruction."},
        {"route": "/apps", "label": "App Center",
         "description": "Open the other federation apps from inside TheHub."},
        {"route": "/launcher", "label": "Federation launcher",
         "description": "The standalone list of federation desktop apps."},
        {"route": "/operator-settings", "label": "Operator Settings",
         "description": "Uploads, exports and administrative write access."},
    ],
    "guest": {
        "label": "Guest",
        "description": (
            "Read-only. Browse, search and export; nothing in the store can be "
            "created, edited or deleted."
        ),
    },
    "operator": {
        "label": "Operator",
        "description": (
            "Full access. Administrative writes are enabled for this session "
            "with a one-time credential that is discarded when the app closes."
        ),
        # server/backend/main_core.py fails every write closed without this
        # variable; the UI picks the credential up from ?write_token=.
        "token_env": "PRII_WRITE_TOKEN",
        "url_param": "write_token",
    },
    "guest_guard": {
        # POSTs that only read, plus the stub and session endpoints the UI calls
        # while browsing. Everything else that is not a GET is refused for a guest.
        "allow": [
            "POST /api/entities/*/filter",
            "POST /api/functions/*/invoke",
            "/api/agents/**",
            "/api/integrations/**",
            "POST /api/federation-manager/session",
            "POST /api/federation-manager/secrets/presence",
            "POST /api/federation-manager/runs/*/log-ticket",
            "POST /api/local/launch/*",
        ],
    },
    "options": [
        {
            "id": "grid_profile_root",
            "label": "Grid V2 profile folder",
            "kind": "text",
            "env": "PRII_GRID_V2_PROFILE_ROOT",
            "placeholder": "Leave empty if you have no profile folder",
            "help": (
                "Folder holding materialized PR grid V2 cell profiles. Without it "
                "the grid cell lookups report that profile storage is not configured."
            ),
        },
    ],
}
