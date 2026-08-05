"""Per-producer desktop configuration passed into the shared runtime.

Built by each producer's ``desktop/config.py`` (the one genuinely per-repo file)
from its module-level constants, so the shared ``launch`` / ``make_desktop_app``
code carries no repo-specific values.
"""

from __future__ import annotations

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
    #: Health endpoint used to detect the backend is up.
    health_path: str = "/health"
    #: Stable application identifier used for per-user state and diagnostics.
    app_id: str = ""
    #: Accessible brand colors used by native setup, repair, and error surfaces.
    brand_accent: str = "#2563eb"
    brand_accent_strong: str = "#1d4ed8"
    #: App artwork included in a frozen build and verified by diagnostics.
    icon_path: Path | None = None
    #: Bump when first-run setup needs to be shown again for a material change.
    setup_version: int = 1
    #: Producer-specific writable-data environment variable.
    data_env_var: str = "PRII_DATA_HOME"
    #: Optional idempotent callable invoked by Save and Repair after writable
    #: directories and environment variables are ready.
    setup_action: str | None = None
    #: Some adapters (for example the Hub launcher and Spiderweb's standalone
    #: dashboard) attach their own frontend before the shared runtime loads them.
    attach_frontend: bool = True
    #: Test/dev override. Production defaults to the platform's application
    #: support directory and never writes inside the signed .app bundle.
    state_dir: Path | None = None
    #: Extra pip specs / build env are handled by the vendored setup.py, not here.
    extra: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_module(cls, module) -> "DesktopConfig":
        """Build a config from a producer's ``desktop/config.py`` module.

        Reads the established constant names so a producer's launcher remains a
        one-liner and all imperative setup behavior stays in this package.
        """
        return cls(
            app_title=module.APP_TITLE,
            app_import=module.APP_IMPORT,
            repo_root=Path(module.REPO_ROOT),
            dist_dir=Path(module.DIST_DIR),
            health_path=getattr(module, "HEALTH_PATH", "/health"),
            app_id=getattr(module, "APP_ID", module.APP_TITLE),
            brand_accent=getattr(module, "BRAND_ACCENT", "#2563eb"),
            brand_accent_strong=getattr(
                module, "BRAND_ACCENT_STRONG", "#1d4ed8"
            ),
            icon_path=(
                Path(module.ICON_PATH)
                if getattr(module, "ICON_PATH", None) is not None
                else None
            ),
            setup_version=int(getattr(module, "SETUP_VERSION", 1)),
            data_env_var=getattr(module, "DATA_ENV_VAR", "PRII_DATA_HOME"),
            setup_action=getattr(module, "SETUP_ACTION", None),
            attach_frontend=bool(getattr(module, "ATTACH_FRONTEND", True)),
        )
