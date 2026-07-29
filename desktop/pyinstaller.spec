# PyInstaller spec for the standalone desktop build (Phase 2).
# Build (on the target OS):
#   pip install pyinstaller
#   pyinstaller desktop/pyinstaller.spec --distpath dist-desktop
# Produces a self-contained one-folder app: dist-desktop/PRII-THEHUB/
# The bundle mirrors the repo layout so server/backend/main.py finds data/
# and releases/ with its normal relative paths.

import os
import sys
from pathlib import Path

REPO_ROOT = Path(SPECPATH).resolve().parent
APP_NAME = "PRII-THEHUB"

# Branding is generated from assets/branding/icon.png by
# thehub-pr/tools/build_program_icons.py, so the frozen build, the committed
# PRII-*.app bundle and the web favicons all trace back to one master.
BRANDING = REPO_ROOT / "assets" / "branding"
# PyInstaller wants .ico on Windows and .icns on macOS; it warns and ignores the
# argument on other platforms, so leave it unset there.
EXE_ICON = str(BRANDING / "icon.ico") if sys.platform == "win32" else None

# Windowed by default (no console window for double-click users). CI sets
# PRII_CONSOLE=1 to build a console binary it can smoke-test with visible stdio.
CONSOLE = os.environ.get("PRII_CONSOLE") == "1"

datas = [
    (str(REPO_ROOT / "server" / "frontend" / "dist"), "server/frontend/dist"),
    (str(BRANDING / "icon-256.png"), "assets/branding"),
    (str(REPO_ROOT / "registry"), "registry"),
    (str(REPO_ROOT / "schemas"), "schemas"),
    # The committed federation readiness snapshot. The frozen app runs the same
    # FastAPI lifespan as the served build, and without this file _load_snapshot
    # returns None, seeding falls back to registry-only, and the Gates page ships
    # empty in the standalone product. It is a committed file, so a missing one
    # should fail the build loudly rather than be skipped.
    (str(REPO_ROOT / "data" / "federation_status.json"), "data"),
]
datas.append((str(REPO_ROOT / "desktop" / "launcher.html"), "desktop"))

a = Analysis(
    [str(REPO_ROOT / "desktop" / "launch.py")],
    pathex=[str(REPO_ROOT)],
    datas=datas,
    hiddenimports=[
        "desktop.launcher_api",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "desktop.app_server",
        "server.backend.main",
        "prii_desktop",
        "prii_desktop.launcher",
        "prii_desktop.appserver",
        "prii_desktop.config",
        "prii_desktop.setup_center",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=APP_NAME,
    console=CONSOLE,
    icon=EXE_ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(BRANDING / "AppIcon.icns"),
        bundle_identifier="pr.prii.thehub",
        info_plist={
            "CFBundleDisplayName": "TheHub",
            "CFBundleName": "TheHub",
        },
    )
