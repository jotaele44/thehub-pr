"""Verify live Spiderweb V2 source bytes against the frozen authority manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from hub.grid_v2 import (
    AUTHORITY_COMMIT, CRS, GRID_ID, GRID_MANIFEST_SHA256, GRID_VERSION,
    BINDING_SCHEMA_SHA256, CELL_SCHEMA_SHA256, MASK_SCHEMA_SHA256,
    GridV2PinError,
)

REQUIRED_FILES = {
    "Cell_Schema_SHA256": ("schemas/pr_grid_geographic_v2_cell.schema.json", CELL_SCHEMA_SHA256),
    "Binding_Schema_SHA256": ("schemas/pr_grid_geographic_v2_binding.schema.json", BINDING_SCHEMA_SHA256),
    "Mask_Schema_SHA256": ("schemas/pr_grid_geographic_v2_mask.schema.json", MASK_SCHEMA_SHA256),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_authority_root(root: Path) -> dict[str, Any]:
    """Fail closed if the geometry authority's exact source manifests differ."""
    try:
        path = root / "registry/spatial/v2/pr_grid_geographic_v2.manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise GridV2PinError("Spiderweb V2 manifest is not an object")
        unhashed = dict(manifest)
        observed_sha = unhashed.pop("Grid_Manifest_SHA256", None)
        canonical = (
            json.dumps(unhashed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        if observed_sha != GRID_MANIFEST_SHA256 or _sha(canonical) != GRID_MANIFEST_SHA256:
            raise GridV2PinError("Spiderweb authority grid manifest hash mismatch")
        for field, expected in (
            ("Grid_ID", GRID_ID), ("Grid_Version", GRID_VERSION), ("CRS", CRS),
        ):
            if manifest.get(field) != expected:
                raise GridV2PinError(f"Spiderweb authority mismatch: {field}")
        for field, (rel, expected) in REQUIRED_FILES.items():
            if manifest.get(field) != expected or _sha((root / rel).read_bytes()) != expected:
                raise GridV2PinError(f"Spiderweb authority schema mismatch: {field}")
        source = root / "registry/spatial/v2/pr_grid_geographic_v2.source.json"
        if _sha(source.read_bytes()) != manifest.get("Source_Manifest_SHA256"):
            raise GridV2PinError("Spiderweb frozen geometry source hash mismatch")
        schema = root / "schemas/pr_grid_geographic_v2_manifest.schema.json"
        if _sha(schema.read_bytes()) != manifest.get("Manifest_Schema_SHA256"):
            raise GridV2PinError("Spiderweb manifest schema hash mismatch")
    except (OSError, ValueError, TypeError) as exc:
        raise GridV2PinError(f"Spiderweb source verification BLOCKED: {exc}") from exc
    return {
        "Authority": "spiderweb-pr",
        "Authority_Commit_Pin": AUTHORITY_COMMIT,
        "Grid_ID": GRID_ID,
        "Grid_Version": GRID_VERSION,
        "Grid_Manifest_SHA256": GRID_MANIFEST_SHA256,
        "Source_Bytes_Verified": True,
        "Authority_Commit_Object_Verified": False,
        "Verification_State": "SOURCE_BYTES_PASS",
    }
