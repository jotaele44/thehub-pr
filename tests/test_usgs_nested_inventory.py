import gzip
import hashlib
import json
import warnings
import zipfile
from pathlib import Path

import pytest

from hub.usgs_nested_inventory import inventory_nested_files

ROOT = Path(__file__).resolve().parents[1]


def test_all_frozen_metadata_exposes_nested_references_without_unique_asset_claim():
    baseline = json.loads(
        gzip.decompress(
            (ROOT / "data/usgs/continuation_inventory.v1.json.gz").read_bytes()
        )
    )
    roots = [
        r["sciencebase_id"]
        for r in json.loads((ROOT / "registry/usgs/pr_releases.v1.json").read_text())[
            "releases"
        ]
    ]
    r = inventory_nested_files(
        ROOT / "data/usgs/snapshots/20261016_all_item_metadata.zip",
        "5f0c4f3b4782ed9a9c94511a76fdda0b6ac82e9caba8075219cb15f461b4f280",
        baseline,
        roots,
    )
    assert r["metadata_item_count"] == 463
    assert r["reference_locations"] == {"distributionLinks": 3136, "facets": 850}
    assert r["nested_reference_observations"] == 3986
    assert r["combined_reference_observations"] == 6272
    assert r["non_array_files_field_count"] == 702
    assert all(a["raw_value"] == "" for a in r["non_array_files_fields"])
    assert r["metadata_enumeration_state"] == "OPEN"
    assert r["array_reference_enumeration_state"] == "PASS"
    assert r["unique_asset_binding_state"] == "UNRESOLVED"
    assert r["activated"] == 0 and r["full_payload_closure"] == "OPEN"
    ids = [a["reference_id"] for a in r["references"]]
    assert len(ids) == len(set(ids)) == 3986
    assert all(a["payload_state"] == "UNVERIFIED" for a in r["references"])


@pytest.mark.parametrize(
    "attack",
    [
        "none",
        "wrong_id",
        "duplicate_member",
        "missing_member",
        "bad_descriptor",
        "baseline_swap",
        "non_array",
    ],
)
def test_exact_source_membership_and_nested_multiplicity(tmp_path, attack):
    descriptor = {"name": "same.shp", "size": 20}
    baseline = {
        "child_edges": [],
        "file_count": 1,
        "assets": [
            {
                "asset_id": "root:0",
                "source_item_id": "root",
                "raw_descriptor": descriptor,
            }
        ],
    }
    item = {
        "id": "root",
        "files": [descriptor],
        "facets": [{"files": [descriptor, descriptor]}],
    }
    if attack == "wrong_id":
        item["id"] = "foreign"
    elif attack == "bad_descriptor":
        item["facets"][0]["files"] = ["not-a-descriptor"]
    elif attack == "baseline_swap":
        item["files"] = [{"name": "same.shp", "size": 21}]
    elif attack == "non_array":
        item["facets"][0]["files"] = ""
    path = tmp_path / "source.zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as z:
            if attack != "missing_member":
                z.writestr("root.json", json.dumps(item))
            if attack == "duplicate_member":
                z.writestr("root.json", json.dumps(item))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if attack in ("none", "non_array"):
        r = inventory_nested_files(path, sha, baseline, ["root"])
        if attack == "none":
            assert len(r["references"]) == 2
            assert (
                r["references"][0]["reference_id"] != r["references"][1]["reference_id"]
            )
            assert all(
                a["exact_top_level_descriptor_matches"] == ["root:0"]
                for a in r["references"]
            )
        else:
            assert (
                r["metadata_enumeration_state"] == "OPEN"
                and r["non_array_files_field_count"] == 1
            )
    else:
        with pytest.raises(ValueError):
            inventory_nested_files(path, sha, baseline, ["root"])
    with pytest.raises(ValueError, match="archive mismatch"):
        inventory_nested_files(path, "0" * 64, baseline, ["root"])
