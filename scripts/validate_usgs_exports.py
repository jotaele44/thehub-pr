"""Validate the frozen USGS test export; never activates payloads."""

import argparse
import gzip
from collections import Counter
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hub.usgs_exports import assess_usgs_export  # noqa: E402
from hub.usgs_readiness import assess_usgs_readiness  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package",
        type=Path,
        default=ROOT / "data/usgs/producer_exports/spiderweb-native-v1",
    )
    parser.add_argument(
        "--input-manifest",
        type=Path,
        default=ROOT / "data/usgs/producer_inputs/spiderweb-native.v1.json",
    )
    parser.add_argument("--write-receipts", action="store_true")
    args = parser.parse_args()
    report = assess_usgs_export(args.package, args.input_manifest, ROOT)
    readiness = assess_usgs_readiness(ROOT)
    reviewed = {a["asset_id"]: a for a in readiness["assets"]}
    kml_ids = {a["asset_id"].rsplit(":", 1)[0] + ":2" for a in readiness["assets"]}
    if args.write_receipts:
        (ROOT / "registry/usgs/export_validation.v1.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        inventory = json.loads(
            gzip.decompress(
                (ROOT / "data/usgs/continuation_inventory.v1.json.gz").read_bytes()
            )
        )
        spec = json.loads(args.input_manifest.read_text())
        exported = {a["asset_id"] for a in spec["assets"]}
        rows = []
        for asset in inventory["assets"]:
            rows.append(
                {
                    "asset_id": asset["asset_id"],
                    "byte_state": asset["payload_state"],
                    "adapter_state": "PASS"
                    if asset["asset_id"] in exported
                    else "OPEN",
                    "adapter_scope": "DOCUMENTARY_TEST_ONLY"
                    if asset["asset_id"] in exported
                    else "UNVERIFIED",
                    "additional_manifestation_review": "AUDIT_ONLY" if asset["asset_id"] in kml_ids else "NOT_APPLICABLE",
                    "consumer_fitness": "OPEN",
                    "PR_coverage": "UNRESOLVED",
                    "geometry_CRS_Z_M": "OPEN",
                    "usage_constraints": "RECORDED_NONE" if asset["asset_id"] in reviewed else "OPEN",
                    "native_geometry_format": "PASS" if asset["asset_id"] in reviewed else "OPEN",
                    "cross_format_consistency": "FAIL" if asset["asset_id"] in reviewed else "OPEN",
                    "source_extent": reviewed[asset["asset_id"]]["declared_bbox_state"] if asset["asset_id"] in reviewed else "OPEN",
                    "version_lineage": "OPEN",
                    "domain_semantics": "OPEN",
                    "production_export": "BLOCKED",
                    "activation_state": "BLOCKED",
                }
            )
        if len(rows) != inventory["file_count"] or len(
            {r["asset_id"] for r in rows}
        ) != len(rows):
            raise ValueError("Activation matrix asset denominator mismatch")
        matrix = {
            "contract": "prii.usgs-activation-matrix/v1",
            "source_inventory_sha256": spec["source_inventory_sha256"],
            "file_count": len(rows),
            "root_releases": inventory["root_count"],
            "byte_states": dict(Counter(r["byte_state"] for r in rows)),
            "test_export_asset_count": len(exported),
            "source_review_sha256": readiness["source_review_sha256"],
            "source_review_state": readiness["review_state"],
            "kml_adjudication": readiness["kml_adjudication"],
            "cross_format_failed_assets": readiness["cross_format_failures"],
            "production_eligible": 0,
            "activated": 0,
            "activation_state": "BLOCKED",
            "gate_policy": "All domain and producer production gates must pass against frozen evidence before a separate activation release",
            "assets": rows,
        }
        packed = gzip.compress((json.dumps(matrix, indent=2) + "\n").encode(), mtime=0)
        (ROOT / "registry/usgs/activation_matrix.v1.json.gz").write_bytes(packed)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
