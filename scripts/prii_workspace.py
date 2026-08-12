#!/usr/bin/env python3
"""Run the PRII workspace controller from an uninstalled TheHub checkout."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hub.workspace import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
