"""Per-producer desktop configuration passed into the shared runtime.

Built by each producer's ``desktop/config.py`` (the one genuinely per-repo file)
from its module-level constants, so the shared ``launch`` / ``make_desktop_app``
code carries no repo-specific values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    #: Health endpoint used to detect the backend is up.
    health_path: str = "/health"
    #: Extra pip specs / build env are handled by the vendored setup.py, not here.
    extra: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_module(cls, module) -> "DesktopConfig":
        """Build a config from a producer's ``desktop/config.py`` module.

        Reads the established constant names (APP_TITLE, APP_IMPORT, REPO_ROOT,
        DIST_DIR, HEALTH_PATH) so a producer's shim is a one-liner.
        """
        return cls(
            app_title=module.APP_TITLE,
            app_import=module.APP_IMPORT,
            repo_root=Path(module.REPO_ROOT),
            dist_dir=Path(module.DIST_DIR),
            health_path=getattr(module, "HEALTH_PATH", "/health"),
        )
