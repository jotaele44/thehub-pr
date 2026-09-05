#!/usr/bin/env python3
"""Generate and certify deterministic raster fixtures with GDAL.

This harness deliberately separates TIFF decoding, COG structure, whole-asset
byte identity, reprojection, and pixel-geometric placement claims.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "gis-cog-cert"
SRC = OUT / "source_6566.tif"
COG = OUT / "fixture_6566.cog.tif"
WGS84 = OUT / "fixture_4326.tif"
RECEIPT = OUT / "receipt.json"


def run(*args: str) -> str:
    proc = subprocess.run(args, check=True, text=True, capture_output=True)
    return proc.stdout


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def gdal_json(path: Path) -> dict:
    return json.loads(run("gdalinfo", "-json", str(path)))


def assert_bbox(info: dict) -> list[float]:
    corners = info.get("cornerCoordinates") or {}
    ul = corners.get("upperLeft")
    lr = corners.get("lowerRight")
    if not (ul and lr and len(ul) >= 2 and len(lr) >= 2):
        raise AssertionError("missing pixel-geometric corner coordinates")
    bbox = [float(ul[0]), float(lr[1]), float(lr[0]), float(ul[1])]
    if not (bbox[0] < bbox[2] and bbox[1] < bbox[3]):
        raise AssertionError(f"degenerate bbox: {bbox}")
    return bbox


def main() -> int:
    if not shutil.which("gdal_create") or not shutil.which("gdal_translate") or not shutil.which("gdalwarp"):
        raise RuntimeError("GDAL CLI is required")
    OUT.mkdir(parents=True, exist_ok=True)

    # Puerto Rico State Plane 2022 / EPSG:6566 fixture. Exact values are fixed so
    # output semantics are deterministic even though compressed bytes are hashed
    # after creation rather than assumed in source control.
    run(
        "gdal_create", "-of", "GTiff", "-outsize", "64", "64", "-bands", "1",
        "-burn", "7", "-ot", "Byte", "-a_srs", "EPSG:6566",
        "-a_ullr", "200000", "300000", "201000", "299000", str(SRC),
    )
    run(
        "gdal_translate", str(SRC), str(COG), "-of", "COG",
        "-co", "BLOCKSIZE=256", "-co", "COMPRESS=DEFLATE", "-co", "OVERVIEWS=IGNORE_EXISTING",
    )

    # Independent validator: the sample validator reads byte/IFD layout rather
    # than trusting the TIFF extension or the writer's COG driver selection.
    validator_stdout = run(sys.executable, "-m", "osgeo_utils.samples.validate_cloud_optimized_geotiff", str(COG))
    if "ERROR" in validator_stdout.upper():
        raise AssertionError(validator_stdout)

    run("gdalwarp", "-overwrite", "-s_srs", "EPSG:6566", "-t_srs", "EPSG:4326", "-r", "near", str(COG), str(WGS84))

    src_info = gdal_json(COG)
    dst_info = gdal_json(WGS84)
    src_bbox = assert_bbox(src_info)
    dst_bbox = assert_bbox(dst_info)
    dst_wkt = json.dumps(dst_info.get("coordinateSystem") or {})
    if "4326" not in dst_wkt and "WGS 84" not in dst_wkt:
        raise AssertionError("reprojected fixture is not bound to WGS84")

    receipt = {
        "schemaVersion": "1.0.0",
        "status": "PASS",
        "validator": "GDAL_COG_VALIDATOR",
        "validatorVersion": run("gdalinfo", "--version").strip(),
        "sourceCrs": "EPSG:6566",
        "targetCrs": "EPSG:4326",
        "fullAssetSha256": sha256(COG),
        "reprojectedSha256": sha256(WGS84),
        "sourcePixelGeometryBbox": src_bbox,
        "targetPixelGeometryBbox": dst_bbox,
        "cogPath": COG.name,
        "reprojectedPath": WGS84.name,
        "claims": {
            "tiffDecodeOnly": False,
            "cogByteLayoutValidated": True,
            "wholeAssetIdentityBound": True,
            "epsg6566Reprojected": True,
            "pixelGeometryPlacementBounded": True,
            "crossSourceCanonicalIdentity": False,
        },
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
