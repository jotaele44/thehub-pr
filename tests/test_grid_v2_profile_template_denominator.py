"""Freeze the shared PR grid V2 Cell_Profile v1.2 template generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DENOMINATOR = ROOT / "registry/spatial/v2/profile_template_denominator.json"


def _git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload
    ).hexdigest()


def test_profile_template_denominator_matches_canonical_bytes():
    d = json.loads(DENOMINATOR.read_text(encoding="utf-8"))
    assert d["State"] == "FROZEN_TEMPLATE_GENERATION"
    assert d["Authority_Repository"] == "jotaele44/thehub-pr"
    assert d["Authority_Commit"] == "befacc8432f1849a586f036fda8bf133f7374e2d"
    assert d["Profile_Schema_Version"] == "pr-grid-v2-cell-profile/1.2"
    assert d["Producer_Count"] == 5
    assert d["Geometry_Producer"] == "spiderweb-pr"
    assert d["Geometry_Copied_To_Producers"] is False
    assert d["Incremental_Refresh_Supported"] is True

    assert _git_blob_sha1(
        ROOT / "federation-templates/spatial/pr_grid_v2_profiles.py"
    ) == d["Profile_Module_Git_Blob_SHA1"]
    assert _git_blob_sha1(
        ROOT / "federation-templates/spatial/materialize_pr_grid_v2_profiles.py"
    ) == d["Materializer_Git_Blob_SHA1"]
    assert _git_blob_sha1(
        ROOT / "federation-templates/spatial/test_pr_grid_v2_profiles.py"
    ) == d["Profile_Test_Git_Blob_SHA1"]
