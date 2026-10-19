"""Exact frozen source-review admission, distinct from scientific certification."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from .usgs_assets import root_membership

# Reviewed immutable snapshot. A rehashed receipt cannot authorize a different review.
REVIEW_SHA256 = "b09f5f34411f9570927202f34067463262f526b29138a232f49193257def44a9"
INPUT_SHA256 = "ecdd787388d5c391c44839bbafe4b9de1763d8b28a30a3bba77772aeb8afb296"


KML_REVIEW_SHA256 = "e65348a25164f53f7cc012c70535ac5c2af00371620ba1672c98699b81de69e9"
KML_INPUT_SHA256 = "a1605b8975a38f84bb726bdb833df705cf2a5d6fac3d99b6c6836828b5ab27d3"

NESTED_REVIEW_SHA256 = "cf13e4a488442c100e647d7ab19f0ea45dffc5822f1c9a571a9243dcc13b03b1"

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
    kml_raw = (root / "registry/usgs/kml_adjudication.v2.json").read_bytes()
    kml_input_raw = (root / "data/usgs/kml_review_inputs/input.v1.json").read_bytes()
    if _sha(kml_raw) != KML_REVIEW_SHA256 or _sha(kml_input_raw) != KML_INPUT_SHA256:
        raise ValueError("Unreviewed KML adjudication/input bytes")
    kml, kml_input = json.loads(kml_raw), json.loads(kml_input_raw)
    if (kml["prior_review_report_sha256"] != REVIEW_SHA256
            or kml_input["source_review_report_sha256"] != REVIEW_SHA256
            or kml_input["source_review_input_sha256"] != INPUT_SHA256
            or kml_input["source_inventory_sha256"] != _sha(inventory_raw)
            or kml["input_sha256"] != KML_INPUT_SHA256):
        raise ValueError("KML/source review binding mismatch")
    if {e["geojson_asset_id"] for e in kml_input["assets"]} != {e["asset_id"] for e in native["assets"]}:
        raise ValueError("KML/source membership mismatch")
    for entry in spec["assets"] + native["assets"] + kml_input["assets"] + kml_input["supporting_documents"] + [spec["release_metadata"]]:
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
    nested_raw = (root / "registry/usgs/nested_file_inventory.v1.json.gz").read_bytes()
    if _sha(nested_raw) != NESTED_REVIEW_SHA256:
        raise ValueError("Unreviewed nested file-reference inventory")
    nested = json.loads(gzip.decompress(nested_raw))
    if _sha((root / "data/usgs/snapshots/20261016_all_item_metadata.zip").read_bytes()) != nested["metadata_archive_sha256"]:
        raise ValueError("Nested metadata archive binding mismatch")
    memberships = root_membership([spec["root_release_id"]], inventory["child_edges"])
    release_ids = {a["asset_id"] for a in inventory["assets"]
                   if spec["root_release_id"] in memberships.get(a["source_item_id"], [])}
    reviewed_ids = {e["asset_id"] for e in spec["assets"] + native["assets"] + kml_input["assets"] + kml_input["supporting_documents"]}
    if release_ids != reviewed_ids:
        raise ValueError("Frozen release file review denominator mismatch")
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
        "release_manifestation_closure": {
            "state": "PASS",
            "scope": "Legacy top-level file descriptors of one NSHM release only",
            "full_file_closure": "OPEN",
            "nested_reference_observations": sum(spec["root_release_id"] in r["root_release_ids"] for r in nested["references"]),
            "intersection": len(release_ids & reviewed_ids),
            "a_only": sorted(release_ids - reviewed_ids),
            "b_only": sorted(reviewed_ids - release_ids),
            "union": len(release_ids | reviewed_ids),
            "symmetric_difference": len(release_ids ^ reviewed_ids),
        },
        "nested_reference_inventory": {
            "metadata_enumeration_state": nested["metadata_enumeration_state"],
            "top_level_baseline_references": nested["top_level_baseline_references"],
            "nested_reference_observations": nested["nested_reference_observations"],
            "reference_locations": nested["reference_locations"],
            "combined_reference_observations": nested["combined_reference_observations"],
            "non_array_files_fields": nested["non_array_files_field_count"],
            "unique_asset_binding_state": "UNRESOLVED",
            "full_payload_closure": "OPEN",
            "scope": "Reference observations are not unique payload assets",
        },
        "kml_adjudication": {
            "state": kml["state"],
            "support_documents": kml["support_documents"]["asset_count"],
            "unit_definitions": "RECORDED",
            "unit_value_validation": "UNRESOLVED",
            "axis_definition": kml["support_documents"]["axis_definition_state"],
            "complete_observation_text": "CSV_PUBLISHER_DIRECTED",
            "fault_changelog_null_key_rows": 1,
            "report_sha256": KML_REVIEW_SHA256,
            "asset_count": kml["asset_count"],
            "features": kml["features"],
            "source_key_intersection": sum(a["kml_to_geojson"]["intersection"] for a in kml["assets"]),
            "source_key_symmetric_difference": sum(a["kml_to_geojson"]["symmetric_difference"] for a in kml["assets"]),
            "exact_geometry_objects": sum(g["exact_comparison_object"] for a in kml["assets"] for g in a["geometry_comparisons"]),
            "geometry_within_numeric_tolerance": sum(g["within_pointwise_tolerance"] for a in kml["assets"] for g in a["geometry_comparisons"]),
            "authority_state": "UNRESOLVED",
            "scientific_staging": "BLOCKED",
        },
        "assets": review["assets"],
    }
