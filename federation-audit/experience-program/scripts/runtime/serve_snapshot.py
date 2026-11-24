#!/usr/bin/env python3
"""Serve one audited snapshot (real backend plus built frontend) on a local port.

Used by the Chromium runtime pass. The seven PRII applications are served
through ``prii_desktop.make_desktop_app`` with a fresh temporary workspace, so
each application's own setup action seeds it. mucaro-ai has its own backend and
is served directly.

Usage:
  serve_snapshot.py <snapshots dir> <repository> <port>
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def build_app(root: Path, name: str):
    os.chdir(root)
    for extra in ("backend", "src", ""):
        candidate = root / extra if extra else root
        if candidate.is_dir():
            sys.path.insert(0, str(candidate))
    if name == "mucaro-ai":
        os.environ.setdefault("MUCARO_AI_DATA_DIR", tempfile.mkdtemp(prefix="mucaro-rt-"))
        from backend.app.main import app

        return app

    from desktop import config as config_module
    from prii_desktop import DesktopConfig
    from prii_desktop.appserver import make_desktop_app
    from prii_desktop.setup_center import apply_environment, configure

    config = DesktopConfig.from_module(config_module)
    config.state_dir = Path(tempfile.mkdtemp(prefix=f"{name}-rt-"))
    configure(config, config.state_dir / "ws")
    apply_environment(config)
    if name == "moneysweep-pr":
        # Its launcher bootstraps the workspace before handing over to the runtime.
        from desktop.workspace import bootstrap_workspace

        bootstrap_workspace()
    return make_desktop_app(config)


def main() -> None:
    snapshots, name, port = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    import uvicorn

    uvicorn.run(build_app(snapshots / name, name), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
