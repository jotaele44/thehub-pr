"""Source refusal survives rehashed reports and exact-release identity mistakes."""
import gzip
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hub.usgs_readiness import assess_usgs_readiness

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evidence(tmp_path):
    paths = ["registry/usgs/source_review.v1.json",
             "data/usgs/source_review_inputs/review_input.v1.json",
             "data/usgs/producer_inputs/spiderweb-native.v1.json",
             "data/usgs/continuation_inventory.v1.json.gz",
             "registry/usgs/activation_matrix.v1.json.gz",
             "registry/usgs/kml_adjudication.v2.json",
             "data/usgs/kml_review_inputs/input.v1.json"]
    for spec_path in paths[1:3]:
        spec = json.loads((ROOT / spec_path).read_text())
        entries = spec["assets"] + ([spec["release_metadata"]] if "release_metadata" in spec else [])
        paths += [e.get("path", e.get("raw_file")) for e in entries]
    kml = json.loads((ROOT / paths[6]).read_text())
    paths += [e["path"] for e in kml["assets"] + kml["supporting_documents"]]
    paths += ["registry/usgs/nested_file_inventory.v1.json.gz",
              "data/usgs/snapshots/20261016_all_item_metadata.zip"]
    for name in paths:
        dst = tmp_path / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dst)
    return tmp_path


def test_source_truth_blocks_all_assets_despite_native_format_pass(evidence):
    r = assess_usgs_readiness(evidence)
    assert (r["inventory_file_count"], r["activated"], r["production_eligible"]) == (2286, 0, 0)
    assert r["release_manifestation_closure"]["intersection"] == 14
    assert r["release_manifestation_closure"]["symmetric_difference"] == 0
    assert r["release_manifestation_closure"]["full_file_closure"] == "OPEN"
    assert r["release_manifestation_closure"]["nested_reference_observations"] == 46
    assert r["nested_reference_inventory"]["reference_locations"]["facets"] == 850
    assert r["nested_reference_inventory"]["non_array_files_fields"] == 702
    assert r["kml_adjudication"]["features"] == 92
    assert r["kml_adjudication"]["exact_geometry_objects"] == 36
    assert r["kml_adjudication"]["authority_state"] == "UNRESOLVED"
    assert r["constraints_recorded"] == "PASS"
    assert r["native_geometry_format_pass"] == 3
    assert r["cross_format_failures"] == 3 and r["extent_failures"] == 2
    assert r["staging_eligibility"] == r["exact_release_certification"] == "BLOCKED"


@pytest.mark.parametrize("attack", ["fake_pass", "swapped_csv", "rehash_input", "missing_asset", "fake_kml_pass", "swapped_kml"])
def test_unreviewed_rehashed_evidence_cannot_close_gates(evidence, attack):
    specpath = evidence / "data/usgs/source_review_inputs/review_input.v1.json"
    spec = json.loads(specpath.read_text())
    report = evidence / "registry/usgs/source_review.v1.json"
    if attack == "fake_kml_pass":
        path = evidence / "registry/usgs/kml_adjudication.v2.json"
        r = json.loads(path.read_text())
        r.update(certification="PASS", scientific_staging="PASS")
        path.write_text(json.dumps(r))
    elif attack == "swapped_kml":
        m = json.loads((evidence / "data/usgs/kml_review_inputs/input.v1.json").read_text())
        (evidence / m["assets"][0]["path"]).write_bytes(gzip.compress(b"replacement"))
    elif attack == "fake_pass":
        r = json.loads(report.read_text())
        r.update(state="PASS", cross_format_failures=0, staging_eligibility="PASS")
        report.write_text(json.dumps(r))
    elif attack == "swapped_csv":
        (evidence / spec["assets"][1]["path"]).write_bytes(gzip.compress(b"replacement"))
    elif attack == "rehash_input":
        spec["raw_numeric_serialization_tolerance"] = "100"
        raw = json.dumps(spec).encode()
        specpath.write_bytes(raw)
        r = json.loads(report.read_text())
        r["review_input_sha256"] = hashlib.sha256(raw).hexdigest()
        report.write_text(json.dumps(r))
    else:
        (evidence / spec["assets"][0]["path"]).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        assess_usgs_readiness(evidence)


def test_exact_commit_and_clean_tree_required_but_do_not_certify_conflicts(evidence, monkeypatch):
    spec = importlib.util.spec_from_file_location("certify_usgs_release", ROOT / "scripts/certify_usgs_release.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    cli.ROOT = evidence
    sums = {str(p.relative_to(evidence)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in evidence.rglob("*") if p.is_file()}
    (evidence / "registry/usgs/SHA256SUMS.json").write_text(json.dumps(sums))
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=evidence, text=True).strip()
    git("init", "-q")
    git("add", ".")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "Fixture")
    head = git("rev-parse", "HEAD")
    out = evidence.parent / "assessment.json"
    monkeypatch.setattr(sys, "argv", ["certify", "--expected-commit", "0" * 40, "--out", str(out)])
    with pytest.raises(ValueError, match="commit mismatch"):
        cli.main()
    monkeypatch.setattr(sys, "argv", ["certify", "--expected-commit", head, "--out", str(out)])
    assert cli.main() == 2
    r = json.loads(out.read_text())
    assert r["software_identity"] == "PASS" and r["certification"] == "BLOCKED"
    out.unlink()
    shadow = evidence / "src/hub/unreviewed.py"
    shadow.parent.mkdir(parents=True)
    shadow.write_text("# unreviewed implementation")
    with pytest.raises(ValueError, match="modified"):
        cli.main()
    shadow.unlink()
    (evidence / "registry/usgs/source_review.v1.json").write_text("{}")
    with pytest.raises(ValueError, match="modified"):
        cli.main()
