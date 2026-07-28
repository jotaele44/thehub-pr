#!/usr/bin/env python3
"""Verify one PRII desktop product's branding and UI-only release contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import struct
import sys
from pathlib import Path

PROGRAMS = {
    "centinelas-pr": {
        "accent": "#E3680F",
        "foreground": "#000000",
        "display": "Centinelas",
        "frontend": "frontend",
        "html": ["frontend/index.html"],
        "palette": [
            "frontend/src/index.css",
            "frontend/src/styles/federation.css",
        ],
        "bundle": "PRII-CENTINELAS.app",
    },
    "spiderweb-pr": {
        "accent": "#DC1606",
        "foreground": "#ffffff",
        "display": "Spiderweb",
        "frontend": "server/frontend",
        "html": ["server/frontend/index.html", "dashboard/dashboard.html"],
        "palette": [
            "server/frontend/src/styles/app.css",
            "dashboard/dashboard.jsx",
            "dashboard/dashboard_contract_finance.jsx",
        ],
        "bundle": "PRII-SPIDERWEB.app",
    },
    "skywatcher-pr": {
        "accent": "#0B9DEE",
        "foreground": "#000000",
        "display": "Skywatcher",
        "frontend": "frontend",
        "html": ["frontend/index.html"],
        "palette": ["frontend/src/index.css"],
        "bundle": "PRII-SKYWATCHER.app",
    },
    "thehub-pr": {
        "accent": "#0B39CA",
        "foreground": "#ffffff",
        "display": "TheHub",
        "frontend": "server/frontend",
        "html": ["server/frontend/index.html"],
        "palette": [
            "server/frontend/src/index.css",
            "federation-design/styles/foundation.css",
            "federation-design/tokens/federation.tokens.json",
        ],
        "bundle": "PRII-THEHUB.app",
    },
    "aguayluz-pr": {
        "accent": "#12E0D6",
        "foreground": "#000000",
        "display": "AguaYLuz",
        "frontend": "dashboard",
        "html": ["dashboard/index.html"],
        "palette": [
            "dashboard/src/index.css",
            "dashboard/src/styles/federation.css",
        ],
        "bundle": "PRII-AGUAYLUZ.app",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    return struct.unpack(">II", header[16:24])


def luminance(value: str) -> float:
    channels = [
        int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)
    ]

    def linear(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: str, second: str) -> float:
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def color_present(value: str, source: str) -> bool:
    """Match an exact six-digit colour or its equivalent CSS shorthand."""
    normalized = value.lower()
    variants = {normalized}
    if all(normalized[index] == normalized[index + 1] for index in (1, 3, 5)):
        variants.add(f"#{normalized[1]}{normalized[3]}{normalized[5]}")
    return any(variant in source for variant in variants)


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def verify(repo: Path) -> list[str]:
    failures: list[str] = []
    config = PROGRAMS.get(repo.name)
    if config is None:
        return [f"unsupported federation repo: {repo.name}"]

    branding = repo / "assets" / "branding"
    source = branding / "icon.png"
    manifest_path = branding / "manifest.json"
    require(source.is_file(), "branding master is missing", failures)
    require(manifest_path.is_file(), "branding manifest is missing", failures)
    if not source.is_file() or not manifest_path.is_file():
        return failures

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(
        manifest.get("schema") == "prii-branding/v1",
        "branding schema is not prii-branding/v1",
        failures,
    )
    require(
        manifest.get("source_sha256") == sha256(source),
        "branding source SHA-256 differs from manifest",
        failures,
    )
    require(
        tuple(manifest.get("source_dimensions", [])) == png_dimensions(source),
        "branding source dimensions differ from manifest",
        failures,
    )
    require(
        manifest.get("accent", "").upper() == config["accent"].upper(),
        "branding accent differs from product contract",
        failures,
    )
    for name, metadata in manifest.get("derivatives", {}).items():
        artifact = branding / name
        require(artifact.is_file(), f"missing derivative: {name}", failures)
        if artifact.is_file():
            require(
                sha256(artifact) == metadata.get("sha256"),
                f"derivative digest mismatch: {name}",
                failures,
            )

    frontend = repo / config["frontend"]
    for name in ("icon-32.png", "icon-180.png", "icon-192.png", "icon-512.png"):
        consumer = frontend / "public" / name
        require(consumer.is_file(), f"missing web icon: {consumer}", failures)
        if consumer.is_file():
            require(
                sha256(consumer) == sha256(branding / name),
                f"web icon drift: {consumer}",
                failures,
            )

    for relative in config["html"]:
        html = (repo / relative).read_text(encoding="utf-8")
        require("icon-32.png" in html, f"{relative} does not use icon-32.png", failures)
        require(
            config["accent"].lower() in html.lower(),
            f"{relative} theme-color does not match {config['accent']}",
            failures,
        )
        require(
            "data:image/png;base64" not in html,
            f"{relative} still embeds a stale favicon",
            failures,
        )

    palette = "\n".join(
        (repo / relative).read_text(encoding="utf-8")
        for relative in config["palette"]
    ).lower()
    require(
        config["accent"].lower() in palette,
        "frontend palette does not contain the exact product accent",
        failures,
    )
    require(
        color_present(config["foreground"], palette),
        "frontend palette does not contain its accessible accent foreground",
        failures,
    )

    desktop_config = (repo / "desktop" / "config.py").read_text(encoding="utf-8")
    require(
        config["accent"].lower() in desktop_config.lower(),
        "desktop config accent differs from web/branding contract",
        failures,
    )
    launch_lines = (repo / "desktop" / "launch.py").read_text(
        encoding="utf-8"
    ).splitlines()
    require(
        len(launch_lines) <= 40,
        "desktop launcher is not a thin shared-runtime adapter",
        failures,
    )

    spec = (repo / "desktop" / "pyinstaller.spec").read_text(encoding="utf-8")
    for fragment in (
        '"prii_desktop.setup_ui"',
        '"assets/branding"',
        '"NSHighResolutionCapable": True',
    ):
        require(fragment in spec, f"PyInstaller contract missing {fragment}", failures)

    bundle = repo / config["bundle"]
    plist_path = bundle / "Contents" / "Info.plist"
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    require(
        plist.get("CFBundleDisplayName") == config["display"],
        "macOS display name differs from product contract",
        failures,
    )
    bundle_icon = bundle / "Contents" / "Resources" / "AppIcon.icns"
    require(bundle_icon.is_file(), "macOS bundle icon is missing", failures)
    if bundle_icon.is_file():
        require(
            sha256(bundle_icon) == sha256(branding / "AppIcon.icns"),
            "macOS bundle icon drift",
            failures,
        )

    # Source checkouts contain tiny Finder helpers, not the frozen product.
    # They must never fall back to dependency installation or command-line
    # recovery; their only valid recovery action is a native Releases dialog.
    for executable in sorted(repo.glob("*.app/Contents/MacOS/*")):
        helper = executable.read_text(encoding="utf-8", errors="ignore").lower()
        for forbidden in (
            "desktop/setup.py",
            "python3",
            "node.js",
            "npm ",
            ".venv",
            "terminal",
        ):
            require(
                forbidden not in helper,
                f"{executable.relative_to(repo)} requires {forbidden!r}",
                failures,
            )
        require(
            "osascript" in helper and "/releases" in helper,
            f"{executable.relative_to(repo)} is not a Finder-only release helper",
            failures,
        )

    readme = (repo / "desktop" / "README.md").read_text(encoding="utf-8")
    require(
        "Setup & Repair" in readme and "no Terminal" in readme,
        "desktop installation guide does not describe the UI-only setup path",
        failures,
    )

    ratio = contrast(config["accent"], config["foreground"])
    require(ratio >= 4.5, f"accent contrast is only {ratio:.2f}:1", failures)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    failures = verify(repo)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"{repo.name}: branding, native bundle, and accessibility contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
