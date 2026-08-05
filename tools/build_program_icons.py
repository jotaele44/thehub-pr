#!/usr/bin/env python3
"""Generate and verify PRII program icons from each repository's branding master."""

from __future__ import annotations

import argparse
import colorsys
import filecmp
import hashlib
import json
import math
import statistics
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - dependency guard
    sys.exit("Pillow is required: pip install -r tools/requirements-icons.txt")

PROGRAMS = {
    "aguayluz-pr": {"frontend": "dashboard", "bundle": "PRII-AGUAYLUZ.app"},
    "centinelas-pr": {"frontend": "frontend", "bundle": "PRII-CENTINELAS.app"},
    "moneysweep-pr": {"frontend": "dashboard", "bundle": "PRII-MONEYSWEEP.app"},
    "ovnis-pr": {"frontend": "dashboard", "bundle": "PRII-OVNIS.app"},
    "skywatcher-pr": {"frontend": "frontend", "bundle": "PRII-SKYWATCHER.app"},
    "spiderweb-pr": {"frontend": "server/frontend", "bundle": "PRII-SPIDERWEB.app"},
    "thehub-pr": {
        "frontend": "server/frontend",
        "bundle": "PRII-THEHUB.app",
        "extra_bundles": ["PRII Federation.app"],
    },
}

PUBLIC_FILES = ("icon-180.png", "icon-192.png", "icon-512.png")
SRC_ASSET = "icon-64.png"
MASTER = Path("assets/branding/icon.png")
PNG_SIZES = (512, 256, 192, 180, 64, 32)
ICO_SIZES = (16, 32, 48, 64, 128, 256)
ICNS_SIZE = 1024
SQUIRCLE_N = 5.0
SUPERSAMPLE = 4


def squircle_mask(size: int) -> Image.Image:
    """Return an antialiased superellipse mask."""
    high_size = size * SUPERSAMPLE
    mask = Image.new("L", (high_size, high_size), 0)
    draw = ImageDraw.Draw(mask)
    radius = high_size / 2.0
    for y_pixel in range(high_size):
        y_value = (y_pixel + 0.5 - radius) / radius
        remainder = 1.0 - abs(y_value) ** SQUIRCLE_N
        if remainder <= 0:
            continue
        x_value = remainder ** (1.0 / SQUIRCLE_N)
        draw.line(
            [
                (radius - x_value * radius, y_pixel),
                (radius + x_value * radius - 1, y_pixel),
            ],
            fill=255,
        )
    return mask.resize((size, size), Image.Resampling.LANCZOS)


def rounded(master: Image.Image, size: int) -> Image.Image:
    image = master.convert("RGBA").resize(
        (size, size),
        Image.Resampling.LANCZOS,
    )
    image.putalpha(squircle_mask(size))
    return image


def sample_accent(master: Image.Image) -> str:
    image = master.convert("RGB").resize((200, 200), Image.Resampling.LANCZOS)
    points: list[tuple[float, float, float]] = []
    for red, green, blue in image.getdata():
        hue, saturation, value = colorsys.rgb_to_hsv(
            red / 255,
            green / 255,
            blue / 255,
        )
        if not 0.30 <= value <= 0.97 or saturation < 0.35:
            continue
        points.append((hue, saturation, value))
    if not points:
        return "#888888"
    x_axis = sum(
        math.cos(2 * math.pi * hue) * saturation
        for hue, saturation, _ in points
    )
    y_axis = sum(
        math.sin(2 * math.pi * hue) * saturation
        for hue, saturation, _ in points
    )
    hue = (math.atan2(y_axis, x_axis) / (2 * math.pi)) % 1.0
    saturation = min(1.0, max(statistics.median(p[1] for p in points), 0.55))
    value = min(0.92, max(statistics.median(p[2] for p in points), 0.55))
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    return "#%02x%02x%02x" % (
        round(red * 255),
        round(green * 255),
        round(blue * 255),
    )


def build(master_path: Path, output_dir: Path) -> list[Path]:
    master = Image.open(master_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for size in PNG_SIZES:
        destination = output_dir / f"icon-{size}.png"
        rounded(master, size).save(destination, format="PNG", optimize=True)
        written.append(destination)

    ico = output_dir / "icon.ico"
    rounded(master, max(ICO_SIZES)).save(
        ico,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
    )
    written.append(ico)

    icns = output_dir / "AppIcon.icns"
    rounded(master, ICNS_SIZE).save(icns, format="ICNS")
    written.append(icns)

    manifest = output_dir / "icon-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": MASTER.name,
                "source_sha256": hashlib.sha256(master_path.read_bytes()).hexdigest(),
                "sampled_accent": sample_accent(master),
                "mask": {
                    "kind": "superellipse",
                    "exponent": SQUIRCLE_N,
                    "supersample": SUPERSAMPLE,
                },
                "derivatives": {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in written
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(manifest)
    return written


def consumer_targets(
    repo: Path,
    program_name: str,
    staged: Path,
) -> list[tuple[Path, Path]]:
    """Return authoritative generated consumers for one repository.

    A repository's declared frontend is the only web consumer. Legacy duplicate
    surfaces are not regenerated or required.
    """
    config = PROGRAMS[program_name]
    targets: list[tuple[Path, Path]] = []

    for bundle in [config["bundle"], *config.get("extra_bundles", [])]:
        targets.append(
            (
                staged / "AppIcon.icns",
                repo / bundle / "Contents/Resources/AppIcon.icns",
            )
        )

    frontend = repo / config["frontend"]
    for filename in PUBLIC_FILES:
        targets.append(
            (staged / filename, frontend / "public" / filename)
        )
    targets.append(
        (staged / SRC_ASSET, frontend / "src" / "assets" / SRC_ASSET)
    )
    return targets


def equivalent_file(generated: Path, committed: Path) -> bool:
    suffix = generated.suffix.lower()
    if suffix not in {".png", ".ico", ".icns"}:
        return filecmp.cmp(generated, committed, shallow=False)
    try:
        with Image.open(generated) as expected, Image.open(committed) as actual:
            if suffix == ".ico":
                expected_sizes = sorted(expected.ico.sizes())
                actual_sizes = sorted(actual.ico.sizes())
                return expected_sizes == actual_sizes and all(
                    expected.ico.getimage(size).convert("RGBA").tobytes()
                    == actual.ico.getimage(size).convert("RGBA").tobytes()
                    for size in expected_sizes
                )
            if suffix == ".icns":
                expected_sizes = list(expected.icns.itersizes())
                actual_sizes = list(actual.icns.itersizes())
                return expected_sizes == actual_sizes and all(
                    expected.icns.getimage(size).convert("RGBA").tobytes()
                    == actual.icns.getimage(size).convert("RGBA").tobytes()
                    for size in expected_sizes
                )
            return expected.size == actual.size and (
                expected.convert("RGBA").tobytes()
                == actual.convert("RGBA").tobytes()
            )
    except (AttributeError, OSError, ValueError):
        return False


def sync(pairs: list[tuple[Path, Path]], check: bool) -> list[str]:
    drifted: list[str] = []
    for generated, destination in pairs:
        if check:
            if not destination.is_file() or not equivalent_file(generated, destination):
                drifted.append(str(destination))
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(generated.read_bytes())
    return drifted


def committed_manifest_matches(
    generated: Path,
    committed: Path,
    derivatives_dir: Path,
) -> bool:
    try:
        expected = json.loads(generated.read_text(encoding="utf-8"))
        actual = json.loads(committed.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False

    expected_stable = {key: value for key, value in expected.items() if key != "derivatives"}
    actual_stable = {key: value for key, value in actual.items() if key != "derivatives"}
    if expected_stable != actual_stable:
        return False

    expected_names = set(expected.get("derivatives", {}))
    actual_hashes = actual.get("derivatives", {})
    if expected_names != set(actual_hashes):
        return False
    return all(
        (derivatives_dir / filename).is_file()
        and hashlib.sha256((derivatives_dir / filename).read_bytes()).hexdigest()
        == digest
        for filename, digest in actual_hashes.items()
    )


def process(repo: Path, check: bool) -> bool:
    master_path = repo / MASTER
    if not master_path.is_file():
        print(f"  !! missing master: {master_path}")
        return False

    output_dir = repo / MASTER.parent
    accent = sample_accent(Image.open(master_path))
    with tempfile.TemporaryDirectory() as temporary:
        staged = Path(temporary)
        built = build(master_path, staged)
        generated_manifest = staged / "icon-manifest.json"
        committed_manifest = output_dir / "icon-manifest.json"
        pairs = [
            (path, output_dir / path.name)
            for path in built
            if path.name != "icon-manifest.json"
        ]
        pairs.extend(consumer_targets(repo, repo.name, staged))
        drifted = sync(pairs, check)
        if check:
            if not committed_manifest_matches(
                generated_manifest,
                committed_manifest,
                output_dir,
            ):
                drifted.append(str(committed_manifest))
        else:
            sync([(generated_manifest, committed_manifest)], check=False)

    if drifted:
        preview = ", ".join(drifted[:4])
        suffix = " …" if len(drifted) > 4 else ""
        print(f"  DRIFT ({len(drifted)}): {preview}{suffix}")
        return False
    action = "verified" if check else "wrote"
    print(f"  accent {accent}  ->  {action} {len(pairs) + 1} files")
    return True


def sync_hub_tiles(repositories: dict[str, Path], check: bool) -> bool:
    hub = repositories.get("thehub-pr")
    if hub is None:
        return True
    tile_directory = hub / "server/frontend/public/branding"
    drifted: list[str] = []
    for program_name, repo in repositories.items():
        source = repo / "assets/branding/icon-256.png"
        if not source.is_file():
            print(f"  !! hub tile source missing: {source}")
            return False
        destination = tile_directory / f"{program_name}.png"
        if check:
            if not destination.is_file() or not filecmp.cmp(
                source,
                destination,
                shallow=False,
            ):
                drifted.append(str(destination))
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    if drifted:
        print(f"hub tiles DRIFT ({len(drifted)}): " + ", ".join(drifted))
        return False
    action = "verified" if check else "wrote"
    print(f"hub federation tiles: {action} {len(repositories)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", action="append", default=[], help="path to a repo checkout")
    parser.add_argument("--all", action="store_true", help="every federation repo, as siblings")
    parser.add_argument("--check", action="store_true", help="verify committed output matches")
    args = parser.parse_args()

    if args.all:
        siblings = Path(__file__).resolve().parents[2]
        repos = [siblings / name for name in PROGRAMS]
    elif args.repo:
        repos = [Path(repo).resolve() for repo in args.repo]
    else:
        print("error: pass --repo <path> or --all", file=sys.stderr)
        parser.print_usage(sys.stderr)
        return 2

    ok = True
    completed: dict[str, Path] = {}
    for repo in repos:
        print(f"{repo.name}:")
        if repo.name not in PROGRAMS:
            print("  !! not a federation program")
            ok = False
            continue
        if not repo.is_dir():
            print("  !! not a directory")
            ok = False
            continue
        ok &= process(repo, args.check)
        completed[repo.name] = repo

    if len(completed) == len(PROGRAMS):
        ok &= sync_hub_tiles(completed, args.check)

    if not ok and args.check:
        print("\nIcons are out of date. Re-run without --check and commit the result.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
