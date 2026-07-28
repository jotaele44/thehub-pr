"""Per-producer desktop configuration passed into the shared runtime.

Built by each producer's ``desktop/config.py`` (the one genuinely per-repo file)
from its module-level constants, so the shared ``launch`` / ``make_desktop_app``
code carries no repo-specific values.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DesktopConfig:
    """Everything the shared desktop runtime needs to know about one producer."""

    #: Native-window title, e.g. "OVNIS — PRII Case Corpus".
    app_title: str
    #: Dotted import path of the FastAPI app object, e.g. "server.backend.main:app".
    app_import: str
    #: Repository root (added to sys.path so ``app_import`` resolves).
    repo_root: Path
    #: Vite build output served same-origin by the desktop app.
    dist_dir: Path
    #: Stable product id used for Application Support state and environment keys.
    app_id: str = ""
    #: Accessible product accent used by the native setup/repair surface.
    accent: str = "#4f46e5"
    #: Canonical runtime icon. The OS bundle/executable remains authoritative.
    icon_path: Path | None = None
    #: Frontend file checked by diagnostics. Defaults to dist_dir/index.html.
    frontend_entry: Path | None = None
    #: Optional already-assembled desktop ASGI app (TheHub and Spiderweb).
    desktop_app_import: str | None = None
    #: Product releases page opened by the UI-only recovery path.
    releases_url: str = ""
    #: Increment to require the guided setup again after a breaking change.
    setup_version: int = 1
    #: Health endpoint used to detect the backend is up.
    health_path: str = "/health"
    #: Legacy source-checkout metadata; the packaged runtime never installs deps.
    extra: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_module(cls, module) -> "DesktopConfig":
        """Build a config from a producer's ``desktop/config.py`` module.

        Reads the established constant names (APP_TITLE, APP_IMPORT, REPO_ROOT,
        DIST_DIR, HEALTH_PATH) so a producer's shim is a one-liner.
        """
        repo_root = Path(module.REPO_ROOT)
        app_title = module.APP_TITLE
        app_id = getattr(module, "APP_ID", "")
        if not app_id:
            app_id = re.sub(r"[^a-z0-9]+", "-", app_title.lower()).strip("-")
        dist_dir = Path(module.DIST_DIR)
        return cls(
            app_title=app_title,
            app_import=module.APP_IMPORT,
            repo_root=repo_root,
            dist_dir=dist_dir,
            app_id=app_id,
            accent=getattr(module, "APP_ACCENT", "#4f46e5"),
            icon_path=Path(
                getattr(
                    module,
                    "APP_ICON",
                    repo_root / "assets" / "branding" / "icon-256.png",
                )
            ),
            frontend_entry=Path(
                getattr(module, "FRONTEND_ENTRY", dist_dir / "index.html")
            ),
            desktop_app_import=getattr(module, "DESKTOP_APP_IMPORT", None),
            releases_url=getattr(
                module,
                "RELEASES_URL",
                f"https://github.com/jotaele44/{repo_root.name}/releases",
            ),
            setup_version=int(getattr(module, "SETUP_VERSION", 1)),
            health_path=getattr(module, "HEALTH_PATH", "/health"),
        )
