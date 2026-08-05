#!/usr/bin/env python3
"""Render one producer's real native setup UI for browser-based CI checks."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from prii_desktop import DesktopConfig, render_setup_html


def load_config(repo: Path) -> DesktopConfig:
    config_path = repo / "desktop" / "config.py"
    if not config_path.is_file():
        raise SystemExit(f"Desktop config not found: {config_path}")
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    spec = importlib.util.spec_from_file_location(
        "prii_visual_desktop_config", config_path
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load desktop config: {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return DesktopConfig.from_module(module)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_setup_html(load_config(repo)), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
