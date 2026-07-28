#!/usr/bin/env python3
"""Generate every derived program icon from a repo's branding master.

Each PRII repo keeps its artwork at ``assets/branding/icon.png`` — the delivered
square master, committed verbatim. This script derives everything else from it:
the rounded-mask PNGs the web surfaces use, the multi-size ``icon.ico`` that
serves both the favicon and the Windows PyInstaller ``EXE``, and the
``AppIcon.icns`` that macOS reads out of the ``PRII-<SLUG>.app`` bundle.

The masters are full-bleed squares (MoneySweep's has rounded corners already
baked in over black), so every derivative gets one shared squircle mask. That
keeps the seven icons a family in the Dock and in UI tiles, and clips
MoneySweep's black corners away.

Run it from a checkout of thehub-pr against a sibling producer checkout, the
same way ``render_federation_templates.py`` is invoked:

    pip install -r tools/requirements-icons.txt
    python3 tools/build_program_icons.py --repo ../aguayluz-pr
    python3 tools/build_program_icons.py --all --check

Output is deterministic: ``--check`` regenerates into a temp dir and byte-compares,
so CI or a reviewer can prove the committed binaries match the master.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import filecmp
import math
import statistics
import colorsys
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - dependency guard
    sys.exit("Pillow is required: pip install -r tools/requirements-icons.txt")

# Every repo in the federation, hub included, with the two consumer locations
# that hold their own copy of the art: the repo's Vite frontend and the
# hand-committed macOS bundle. Paths are relative to this file's repo root's
# parent, i.e. the sibling-checkout layout the federation assumes.
#
# The consumer copies are generated, not hand-placed. Without that, `--check`
# could pass on assets/branding/ while the shipped UI and .app still carried
# stale artwork.
PROGRAMS = {
    "aguayluz-pr": {"frontend": "dashboard", "bundle": "PRII-AGUAYLUZ.app"},
    "centinelas-pr": {"frontend": "frontend", "bundle": "PRII-CENTINELAS.app"},
    "moneysweep-pr": {"frontend": "dashboard", "bundle": "PRII-MONEYSWEEP.app"},
    "ovnis-pr": {"frontend": "dashboard", "bundle": "PRII-OVNIS.app"},
    "skywatcher-pr": {"frontend": "frontend", "bundle": "PRII-SKYWATCHER.app"},
    "spiderweb-pr": {"frontend": "server/frontend", "bundle": "PRII-SPIDERWEB.app"},
    # The hub ships a second bundle that deliberately mirrors the first.
    "thehub-pr": {
        "frontend": "server/frontend",
        "bundle": "PRII-THEHUB.app",
        "extra_bundles": ["PRII Federation.app"],
    },
}

# Deliberate accessible UI accents. Artwork sampling remains useful as an audit
# signal, but product colours are stable API and must not drift when an image
# encoder or sampling implementation changes.
BRAND_ACCENTS = {
    "aguayluz-pr": "#12E0D6",
    "centinelas-pr": "#E3680F",
    "skywatcher-pr": "#0B9DEE",
    "spiderweb-pr": "#DC1606",
    "thehub-pr": "#0B39CA",
}

# Served by the app over HTTP: apple-touch-icon and the PWA manifest pair. The
# favicon is a normal file so browsers, installed PWAs, and package audits all
# consume the same generated source.
PUBLIC_FILES = ("icon-32.png", "icon-180.png", "icon-192.png", "icon-512.png")

# Imported as a module by the frontend and inlined into the bundle, so the
# offline single-file export stays self-contained.
SRC_ASSET = "icon-64.png"

# spiderweb-pr's no-build dashboard is copied file-by-file into static exports,
# so it keeps real files rather than module imports.
STANDALONE = {
    "spiderweb-pr": (
        "dashboard",
        ("icon-32.png", "icon-64.png", "icon-180.png"),
    )
}

MASTER = Path("assets/branding/icon.png")

# Web/UI sizes. 180 is apple-touch-icon, 192/512 are the PWA manifest pair, and
# 256 doubles as the hub's federation tile.
PNG_SIZES = (512, 256, 192, 180, 64, 32)

# Favicon + Windows EXE icon in one file.
ICO_SIZES = (16, 32, 48, 64, 128, 256)

# Matches the chunk set already present in the committed bundles, which is
# exactly what Pillow's ICNS encoder emits.
ICNS_SIZE = 1024

# Squircle exponent. 4-5 reads as the macOS/iOS continuous corner; 2 would be an
# ellipse and a large exponent approaches a plain square.
SQUIRCLE_N = 5.0
SUPERSAMPLE = 4


def squircle_mask(size: int) -> Image.Image:
    """An antialiased superellipse mask — the macOS continuous-corner shape."""
    hi = size * SUPERSAMPLE
    mask = Image.new("L", (hi, hi), 0)
    draw = ImageDraw.Draw(mask)
    r = hi / 2.0
    # |x/r|^n + |y/r|^n = 1, solved per scanline so the corners stay continuous
    # instead of the circular-arc corners ImageDraw.rounded_rectangle would give.
    for py in range(hi):
        y = (py + 0.5 - r) / r
        t = 1.0 - abs(y) ** SQUIRCLE_N
        if t <= 0:
            continue
        x = t ** (1.0 / SQUIRCLE_N)
        draw.line([(r - x * r, py), (r + x * r - 1, py)], fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def rounded(master: Image.Image, size: int) -> Image.Image:
    """Downscale the master to ``size`` and apply the shared squircle mask."""
    im = master.convert("RGBA").resize((size, size), Image.LANCZOS)
    im.putalpha(squircle_mask(size))
    return im


def sample_accent(master: Image.Image) -> str:
    """Derive the program's accent from its own artwork.

    Drops the black silhouette, the blown-out sun, and the washed halo, then
    takes a saturation-weighted circular mean of hue so a large bright region
    cannot drag the result off the colour the tile actually reads as.
    """
    im = master.convert("RGB").resize((200, 200), Image.LANCZOS)
    pts = []
    for r8, g8, b8 in im.get_flattened_data():
        h, s, v = colorsys.rgb_to_hsv(r8 / 255, g8 / 255, b8 / 255)
        if not (0.30 <= v <= 0.97) or s < 0.35:
            continue
        pts.append((h, s, v))
    if not pts:
        return "#888888"
    x = sum(math.cos(2 * math.pi * h) * s for h, s, _ in pts)
    y = sum(math.sin(2 * math.pi * h) * s for h, s, _ in pts)
    hue = (math.atan2(y, x) / (2 * math.pi)) % 1.0
    sat = min(1.0, max(statistics.median(p[1] for p in pts), 0.55))
    val = min(0.92, max(statistics.median(p[2] for p in pts), 0.55))
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def build(master_path: Path, out_dir: Path) -> list[Path]:
    master = Image.open(master_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for size in PNG_SIZES:
        dest = out_dir / f"icon-{size}.png"
        rounded(master, size).save(dest, format="PNG", optimize=True)
        written.append(dest)

    ico = out_dir / "icon.ico"
    rounded(master, max(ICO_SIZES)).save(
        ico, format="ICO", sizes=[(s, s) for s in ICO_SIZES]
    )
    written.append(ico)

    icns = out_dir / "AppIcon.icns"
    rounded(master, ICNS_SIZE).save(icns, format="ICNS")
    written.append(icns)

    return written


def sha256(path: Path) -> str:
    """Return a lowercase SHA-256 digest for a committed branding artifact."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(
    master_path: Path,
    built: list[Path],
    out_dir: Path,
    *,
    accent: str,
) -> Path:
    """Record source provenance and every deterministic derivative digest."""
    with Image.open(master_path) as master:
        dimensions = list(master.size)
        mode = master.mode
    manifest = {
        "schema": "prii-branding/v1",
        "source": "icon.png",
        "source_sha256": sha256(master_path),
        "source_dimensions": dimensions,
        "source_mode": mode,
        "accent": accent,
        "derivatives": {
            path.name: {"sha256": sha256(path)} for path in sorted(built)
        },
    }
    destination = out_dir / "manifest.json"
    destination.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def consumer_targets(repo: Path, name: str, staged: Path) -> list[tuple[Path, Path]]:
    """Every committed copy of the art outside assets/branding/, as (built, dest).

    Each of these is a real file another surface loads, so the generator writes
    them and --check verifies them. Otherwise a master change could leave the
    shipped UI or the .app bundle on stale artwork with --check still green.
    """
    cfg = PROGRAMS[name]
    out: list[tuple[Path, Path]] = []

    # macOS reads Contents/Resources/AppIcon.icns out of the committed bundle.
    for bundle in [cfg["bundle"], *cfg.get("extra_bundles", [])]:
        out.append((staged / "AppIcon.icns", repo / bundle / "Contents/Resources/AppIcon.icns"))

    frontend = repo / cfg["frontend"]
    for name_ in PUBLIC_FILES:
        out.append((staged / name_, frontend / "public" / name_))
    out.append((staged / SRC_ASSET, frontend / "src" / "assets" / SRC_ASSET))

    if name in STANDALONE:
        subdir, files = STANDALONE[name]
        for name_ in files:
            out.append((staged / name_, repo / subdir / name_))

    return out


def sync(pairs: list[tuple[Path, Path]], check: bool) -> list[str]:
    """Copy each built file to its destination, or list the ones that differ."""
    drifted: list[str] = []
    for built, dest in pairs:
        if check:
            if not dest.is_file() or not filecmp.cmp(built, dest, shallow=False):
                drifted.append(str(dest))
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(built.read_bytes())
    return drifted


def process(repo: Path, check: bool) -> bool:
    master_path = repo / MASTER
    if not master_path.is_file():
        print(f"  !! missing master: {master_path}")
        return False

    out_dir = repo / MASTER.parent
    sampled_accent = sample_accent(Image.open(master_path))
    accent = BRAND_ACCENTS.get(repo.name, sampled_accent).upper()

    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp)
        built = build(master_path, staged)
        manifest = write_manifest(
            master_path,
            built,
            staged,
            accent=accent,
        )
        pairs = [(b, out_dir / b.name) for b in built]
        pairs.append((manifest, out_dir / manifest.name))
        pairs += consumer_targets(repo, repo.name, staged)
        drifted = sync(pairs, check)

    if drifted:
        print(f"  DRIFT ({len(drifted)}): " + ", ".join(drifted[:4]) + (" …" if len(drifted) > 4 else ""))
        return False
    verb = "verified" if check else "wrote"
    sample_note = "" if accent.lower() == sampled_accent else f" (sample {sampled_accent})"
    print(f"  accent {accent}{sample_note}  ->  {verb} {len(pairs)} files")
    return True


def sync_hub_tiles(repos: dict[str, Path], check: bool) -> bool:
    """The Hub renders every program, so it vendors all seven 256px tiles.

    One copy, under the hub frontend's public/ dir: the React app loads it from
    the build output and the desktop launcher serves it through
    /api/local/federation/icon/{repo}.
    """
    hub = repos.get("thehub-pr")
    if hub is None:
        return True
    tiles = hub / "server/frontend/public/branding"
    drifted: list[str] = []
    for name, repo in repos.items():
        source = repo / "assets/branding/icon-256.png"
        if not source.is_file():
            print(f"  !! hub tile source missing: {source}")
            return False
        dest = tiles / f"{name}.png"
        if check:
            if not dest.is_file() or not filecmp.cmp(source, dest, shallow=False):
                drifted.append(str(dest))
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source.read_bytes())
    if drifted:
        print(f"hub tiles DRIFT ({len(drifted)}): " + ", ".join(drifted))
        return False
    print(f"hub federation tiles: {'verified' if check else 'wrote'} {len(repos)}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", action="append", default=[], help="path to a repo checkout")
    ap.add_argument("--all", action="store_true", help="every federation repo, as siblings")
    ap.add_argument("--check", action="store_true", help="verify committed output matches")
    args = ap.parse_args()

    if args.all:
        siblings = Path(__file__).resolve().parents[2]
        repos = [siblings / name for name in PROGRAMS]
    elif args.repo:
        repos = [Path(r).resolve() for r in args.repo]
    else:
        # argparse's error() exits, but returning explicitly keeps it obvious --
        # to a reader and to static analysis -- that `repos` is always bound below.
        print("error: pass --repo <path> or --all", file=sys.stderr)
        ap.print_usage(sys.stderr)
        return 2

    ok = True
    done: dict[str, Path] = {}
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
        done[repo.name] = repo

    # The hub's federation tiles need every program's art, so only refresh them
    # when the whole set was processed -- a single-repo run cannot know the rest.
    if len(done) == len(PROGRAMS):
        ok &= sync_hub_tiles(done, args.check)

    if not ok and args.check:
        print("\nIcons are out of date. Re-run without --check and commit the result.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
