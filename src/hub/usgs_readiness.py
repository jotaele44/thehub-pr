"""Exact frozen source-review admission, distinct from scientific certification."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

# Reviewed immutable snapshot. A rehashed receipt cannot authorize a different review.
REVIEW_SHA256 = "b09f5f34411f9570927202f34067463262f526b29138a232f49193257def44a9"
INPUT_SHA256 = "ecdd787388d5c391c44839bbafe4b9de1763d8b28a30a3bba77772aeb8afb296"


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def assess_usgs_readiness(source_root):
    """Admit exactly the reviewed evidence; retain every unresolved production gate."""
    root = Path(source_root).resolve()
    raw = (root / "registry/usgs/source_review.v1.json").read_bytes()
    if _sha(raw) != REVIEW_SHA256:
        raise ValueError("Unreviewed source-review bytes")
    review = json.loads(raw)
    spec_raw = (root / "data/usgs/source_review_inputs/review_input.v1.json").read_bytes()
    if _sha(spec_raw) != INPUT_SHA256 or review["review_input_sha256"] != INPUT_SHA256:
        raise ValueError("Source-review input binding mismatch")
    spec = json.loads(spec_raw)
    native_raw = (root / spec["native_input_manifest"]).read_bytes()
    if _sha(native_raw) != spec["native_input_sha256"]:
        raise ValueError("Native source binding mismatch")
    native = json.loads(native_raw)
    inventory_raw = gzip.decompress(
        (root / "data/usgs/continuation_inventory.v1.json.gz").read_bytes()
    )
    if _sha(inventory_raw) != native["source_inventory_sha256"]:
        raise ValueError("Frozen source inventory mismatch")
    inventory = json.loads(inventory_raw)
    assets = {a["asset_id"]: a for a in inventory["assets"]}
    if len(assets) != inventory["file_count"]:
        raise ValueError("Duplicate frozen asset identity")
    for entry in spec["assets"] + native["assets"] + [spec["release_metadata"]]:
        path = (root / entry.get("path", entry.get("raw_file"))).resolve()
        path.relative_to(root)
        packed = path.read_bytes()
        if _sha(packed) != entry["packed_sha256"]:
            raise ValueError("Frozen container mismatch")
        payload = gzip.decompress(packed)
        if _sha(payload) != entry["raw_sha256"]:
            raise ValueError("Frozen payload mismatch")
        if "asset_id" in entry:
            frozen = assets[entry["asset_id"]]
            if frozen["raw_descriptor"] != entry.get("descriptor", entry.get("source_descriptor_raw")):
                raise ValueError("Frozen descriptor mismatch")
            if frozen["payload_state"] != "PASS":
                raise ValueError("Source review cannot admit quarantined bytes")
    return {
        "contract": "prii.usgs-readiness/v1",
        "source_review_sha256": REVIEW_SHA256,
        "review_state": review["state"],
        "asset_count": review["asset_count"],
        "native_geometry_format_pass": review["native_geometry_format_pass"],
        "cross_format_failures": review["cross_format_failures"],
        "extent_failures": review["extent_failures"],
        "constraints_recorded": review["constraints"]["state"],
        "remaining_production_gates": review["remaining_production_gates"],
        "inventory_file_count": len(assets),
        "staging_eligibility": "BLOCKED",
        "production_eligible": 0,
        "activated": 0,
        "activation_state": "BLOCKED",
        "exact_release_certification": "BLOCKED",
        "assets": review["assets"],
    }
