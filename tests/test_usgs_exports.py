import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from hub.usgs_exports import assess_usgs_export

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data/usgs/producer_exports/spiderweb-native-v1"
INPUT = ROOT / "data/usgs/producer_inputs/spiderweb-native.v1.json"


def test_real_producer_export_membership_and_activation_refusal():
    result = assess_usgs_export(PACKAGE, INPUT, ROOT)
    assert result["state"] == "PASS"
    assert (result["sources"], result["features"]) == (3, 92)
    assert result["membership"] == {
        "intersection": 92,
        "a_only": 0,
        "b_only": 0,
        "union": 92,
        "symmetric_difference": 0,
    }
    assert result["activation_state"] == result["production_export_state"] == "BLOCKED"
    assert result["canonical_locations_emitted"] == result["activated"] == 0
    assert result["open_gates"]


def _copy(tmp_path):
    target = tmp_path / "package"
    shutil.copytree(PACKAGE, target)
    return target


def _rehash(package):
    manifest = json.loads((package / "manifest.json").read_text())
    for f in manifest["files"]:
        raw = (package / f["filename"]).read_bytes()
        f["sha256"] = hashlib.sha256(raw).hexdigest()
        f["record_count"] = len(raw.splitlines())
    digest = hashlib.sha256(
        (
            "|".join(f"{f['filename']}:{f['sha256']}" for f in manifest["files"])
            + "|test"
        ).encode()
    ).hexdigest()[:32]
    manifest["package_id"] = "pkg_" + digest
    raw = json.dumps(manifest, indent=2).encode()
    (package / "manifest.json").write_bytes(raw)
    audit = json.loads((package / "usgs_export_audit.json").read_text())
    audit["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
    (package / "usgs_export_audit.json").write_text(json.dumps(audit))


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "loss",
        "geometry",
        "crs",
        "location",
        "timestamp",
        "id",
        "source",
        "promote",
        "raw_string",
        "time_meaning",
        "boolean",
    ],
)
def test_self_consistent_hashes_cannot_hide_native_loss_or_promotion(
    tmp_path, mutation
):
    package = _copy(tmp_path)
    path = package / "observations.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if mutation == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "loss":
        rows.pop()
    elif mutation == "geometry":
        rows[0]["attributes"]["native_feature"]["geometry"]["coordinates"][0] += 0.001
    elif mutation == "crs":
        rows[0]["attributes"]["native_collection_metadata"]["crs"] = None
    elif mutation == "location":
        rows[0]["location"] = {"lat": 18, "lon": -66}
    elif mutation == "timestamp":
        rows[0]["observed_at"] = "2026-10-17T00:00:00Z"
    elif mutation == "id":
        rows[0]["observation_id"] = "obs_" + "0" * 32
    elif mutation == "source":
        rows[0]["source_id"] = rows[-1]["source_id"]
    elif mutation == "promote":
        rows[0]["attributes"]["activation_state"] = "PASS"
    elif mutation == "raw_string":
        rows[0]["attributes"]["native_feature"]["properties"]["injected"] = "not source"
    elif mutation == "time_meaning":
        rows[0]["attributes"]["timestamp_semantics"] = "GEOLOGICAL_EVENT"
    elif mutation == "boolean":
        rows[0]["attributes"]["native_feature"]["properties"]["SiteID"] = True
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    _rehash(package)
    with pytest.raises(ValueError):
        assess_usgs_export(package, INPUT, ROOT)


@pytest.mark.parametrize(
    "field,value", [("mode", "production"), ("producer", "ovnis-pr")]
)
def test_wrong_producer_or_production_manifest_rejected(tmp_path, field, value):
    package = _copy(tmp_path)
    manifest = json.loads((package / "manifest.json").read_text())
    manifest[field] = value
    (package / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="identity/mode"):
        assess_usgs_export(package, INPUT, ROOT)


def test_source_checksum_and_foreign_root_membership_fail_closed(tmp_path):
    spec = json.loads(INPUT.read_text())
    spec["assets"][0]["root_release_ids"] = ["0" * 24]
    path = tmp_path / "input.json"
    path.write_text(json.dumps(spec))
    # Update the local audit too: the authoritative frozen inventory must still reject.
    package = _copy(tmp_path)
    audit = json.loads((package / "usgs_export_audit.json").read_text())
    audit["input_manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (package / "usgs_export_audit.json").write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="frozen source evidence"):
        assess_usgs_export(package, path, ROOT)
