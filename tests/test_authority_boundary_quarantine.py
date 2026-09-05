from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUARANTINE = ROOT / "registry/federation/legacy_identity_registry_quarantine.json"


def test_legacy_identity_registry_is_quarantined_from_production_imports() -> None:
    q = json.loads(QUARANTINE.read_text(encoding="utf-8"))
    assert q["state"] == "LEGACY_NONAUTHORITATIVE_TEST_FIXTURE"
    assert q["superseding_authority"] == "prii-federation-spatial-identity"

    offenders: list[str] = []
    for path in (ROOT / "src").rglob("*.py"):
        if path.as_posix().endswith("src/hub/identity_registry.py"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "hub.identity_registry" in text or "from .identity_registry" in text or "import identity_registry" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"quarantined Hub identity registry imported by production code: {offenders}"


def test_pixel_grid_is_noncanonical_and_admin_geometry_is_pinned() -> None:
    grid = json.loads((ROOT / "registry/spatial/pr_grid_full_cell_index_saturated.manifest.json").read_text())
    assert grid["canonical_ground_geometry"] is False
    assert grid["georeferenced"] is False
    assert grid["authority_class"] == "NONCANONICAL_LEGACY_IMAGE_SPACE"

    admin = json.loads((ROOT / "registry/spatial/federation_admin_geometry.manifest.json").read_text())
    assert admin["authority_plane"] == "prii-federation-spatial-identity"
    assert admin["source_vintage"] == "2023"
    assert admin["canonical_crs"] == "urn:ogc:def:crs:OGC:1.3:CRS84"
    assert {x["expected_feature_count"] for x in admin["layers"]} == {78, 901}
