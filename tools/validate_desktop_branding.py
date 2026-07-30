#!/usr/bin/env python3
"""Validate supplied-icon provenance, native bundle wiring, and AA brand colors.

This intentionally uses only the standard library so every producer can run it
before dependency installation. The full icon byte-for-byte regeneration still
lives in build_program_icons.py; this is the fast fresh-checkout CI contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import re
import struct
import sys
from pathlib import Path

PROGRAMS = {
    "centinelas-pr": {
        "name": "Centinelas",
        "accent": "#df630d",
        "strong": "#9f3e00",
        "source_sha256": "34d846f464743a33b647b1ec65e8b2c32e29770ef48d8b9244850bb721f6a4d1",
        "bundle": "PRII-CENTINELAS.app",
        "frontend": "frontend",
        "palette": ("frontend/src/index.css", "24.6 89% 46.3%"),
    },
    "spiderweb-pr": {
        "name": "Spiderweb",
        "accent": "#ca0c02",
        "strong": "#9f0a02",
        "source_sha256": "d94022d4684fd871fbb21cada5d1251d42962dd703c508f8499278471303b71f",
        "bundle": "PRII-SPIDERWEB.app",
        "frontend": "server/frontend",
        "palette": ("server/frontend/src/main.tsx", "spiderweb-pr"),
    },
    "skywatcher-pr": {
        "name": "Skywatcher",
        "accent": "#0573e4",
        "strong": "#075ba7",
        "source_sha256": "305fba8cd4e7bcef1b448f43a12daf2507a20feaa1079a07f2d91d6e07eeb5cd",
        "bundle": "PRII-SKYWATCHER.app",
        "frontend": "frontend",
        "palette": ("frontend/src/index.css", "207.4 100% 63.1%"),
    },
    "thehub-pr": {
        "name": "TheHub",
        "accent": "#0529a8",
        "strong": "#0529a8",
        "source_sha256": "981fb8c6f36cca7d451f21210c7f54f19bf102c022b01066ebb56d2e710d76dc",
        "bundle": "PRII-THEHUB.app",
        "frontend": "server/frontend",
        "palette": ("server/frontend/src/index.css", "226.7 94.2% 33.9%"),
    },
    "aguayluz-pr": {
        "name": "AguaYLuz",
        "accent": "#0de3d8",
        "strong": "#087d77",
        "source_sha256": "17170b4f510c9e9ffa4db747b63c53a02c24ea45b65f14842beee7480383aa3d",
        "bundle": "PRII-AGUAYLUZ.app",
        "frontend": "dashboard",
        "palette": ("dashboard/src/index.css", "176.7 78.5% 54.3%"),
    },
}

PNG_SIZES = (32, 64, 180, 192, 256, 512)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def _linear(channel: int) -> float:
    value = channel / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) for index in (1, 3, 5)]
    red, green, blue = (_linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: str, second: str) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def validate(repo: Path) -> list[str]:
    failures: list[str] = []
    config = PROGRAMS.get(repo.name)
    if config is None:
        return [f"unsupported repository: {repo.name}"]

    branding = repo / "assets" / "branding"
    master = branding / "icon.png"
    require(master.is_file(), "missing assets/branding/icon.png", failures)
    if master.is_file():
        require(
            sha256(master) == config["source_sha256"],
            "branding master is not the supplied source file",
            failures,
        )
        require(
            png_size(master)[0] >= 1024 and png_size(master)[0] == png_size(master)[1],
            "branding master must be a square image of at least 1024px",
            failures,
        )

    manifest_path = branding / "icon-manifest.json"
    require(manifest_path.is_file(), "missing icon provenance manifest", failures)
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(
            manifest.get("source_sha256") == config["source_sha256"],
            "icon manifest source hash mismatch",
            failures,
        )
        require(
            manifest.get("sampled_accent") == config["accent"],
            "icon manifest sampled accent mismatch",
            failures,
        )
        for filename, expected in manifest.get("derivatives", {}).items():
            path = branding / filename
            require(
                path.is_file() and sha256(path) == expected,
                f"derived icon drift: {filename}",
                failures,
            )

    for size in PNG_SIZES:
        path = branding / f"icon-{size}.png"
        require(path.is_file(), f"missing icon-{size}.png", failures)
        if path.is_file():
            require(
                png_size(path) == (size, size),
                f"icon-{size}.png has the wrong dimensions",
                failures,
            )
    require((branding / "icon.ico").is_file(), "missing Windows icon.ico", failures)
    require((branding / "AppIcon.icns").is_file(), "missing macOS AppIcon.icns", failures)

    bundle = repo / str(config["bundle"])
    plist_path = bundle / "Contents" / "Info.plist"
    bundle_icon = bundle / "Contents" / "Resources" / "AppIcon.icns"
    require(plist_path.is_file(), "missing committed macOS Info.plist", failures)
    require(bundle_icon.is_file(), "missing committed macOS AppIcon.icns", failures)
    if plist_path.is_file():
        plist = plistlib.loads(plist_path.read_bytes())
        require(
            plist.get("CFBundleDisplayName") == config["name"],
            "macOS display name is not the product name",
            failures,
        )
        require(
            plist.get("CFBundleIconFile") == "AppIcon",
            "macOS bundle is not wired to AppIcon.icns",
            failures,
        )

    frontend = repo / str(config["frontend"])
    index = frontend / "index.html"
    if repo.name == "spiderweb-pr":
        index = repo / "dashboard" / "dashboard.html"
    require(index.is_file(), f"missing web entry point: {index}", failures)
    if index.is_file():
        require(
            config["accent"] in index.read_text(encoding="utf-8").lower(),
            "web theme-color does not match supplied artwork",
            failures,
        )

    palette_file, palette_marker = config["palette"]
    palette_source = repo / str(palette_file)
    require(
        palette_source.is_file()
        and str(palette_marker) in palette_source.read_text(encoding="utf-8"),
        "frontend palette marker is missing",
        failures,
    )
    require(
        contrast(str(config["strong"]), "#ffffff") >= 4.5,
        f"primary brand color fails WCAG AA with white ({contrast(str(config['strong']), '#ffffff'):.2f}:1)",
        failures,
    )

    desktop_config = (repo / "desktop" / "config.py").read_text(encoding="utf-8")
    for marker in (
        f'APP_TITLE = "{config["name"]}"',
        f'BRAND_ACCENT = "{config["accent"]}"',
        f'BRAND_ACCENT_STRONG = "{config["strong"]}"',
        "ICON_PATH = ",
        "DATA_ENV_VAR = ",
    ):
        require(marker in desktop_config, f"desktop adapter missing {marker!r}", failures)

    spec = (repo / "desktop" / "pyinstaller.spec").read_text(encoding="utf-8")
    require("AppIcon.icns" in spec, "PyInstaller macOS icon is not configured", failures)
    require(
        "prii_desktop.setup_center" in spec,
        "frozen build does not include shared setup runtime",
        failures,
    )

    workflow_path = repo / ".github" / "workflows" / "desktop-build.yml"
    require(workflow_path.is_file(), "missing desktop build workflow", failures)
    if workflow_path.is_file():
        workflow = workflow_path.read_text(encoding="utf-8")
        for marker, message in (
            ("prii_desktop/tests", "fresh-machine setup tests are not in CI"),
            ("desktop-setup.spec.js", "browser visual setup smoke is not in CI"),
            ("PRII_SETUP_FIXTURE", "visual smoke does not use the real setup UI"),
            (
                "Upload native setup visual evidence",
                "native setup screenshots are not retained",
            ),
        ):
            require(marker in workflow, message, failures)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    failures = validate(repo)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"branding/setup contract ok: {repo.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
