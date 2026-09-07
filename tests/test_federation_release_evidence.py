from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "release_evidence", Path(__file__).resolve().parents[1] / "scripts/federation_release_evidence.py"
)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def blob(root, name, content):
    p = root / name
    p.write_text(content)
    return {"path": name, "sha256": release.digest(p)}


@pytest.fixture
def bundle(tmp_path):
    b = release.pending_bundle({repo: "a" * 40 for repo in release.REPOSITORIES})
    artifact = blob(tmp_path, "execution.log", "observed execution evidence\n")
    for section in ("axes", "platforms"):
        for index, row in enumerate(b[section]):
            receipt = {
                "repository": row["repository"], "head_sha": "a" * 40,
                "dimension": row["dimension"], "section": section,
                "generation": release.GENERATION, "state": "PASS", "residue": [],
                "command": ["test-driver"], "environment": {"platform": row["dimension"]},
                "started_utc": "2026-09-07T00:00:00Z", "completed_utc": "2026-09-07T00:01:00Z",
                "scope": "fixture only", "evidence_kind": "executed", "exit_code": 0,
                "inputs": [artifact], "outputs": [artifact], "log": artifact,
            }
            if section == "platforms":
                receipt["journey"] = dict.fromkeys(release.JOURNEY, "PASS")
            row.update(state="PASS", claim_type="FACT", residue=[], receipts=[
                blob(tmp_path, f"{section}-{index}.json", json.dumps(receipt))
            ])
    for field in ("scope_residue", "pr_disposition_residue", "source_residue"):
        b[field] = []
    return b


def test_full_integrity_fixture_is_audit_only(bundle, tmp_path):
    result = release.assess(bundle, tmp_path)
    assert result["state"] == "PASS", result
    assert result["certification"] == "AUDIT_ONLY"
    assert result["counts"]["axes"]["PASS"] == 49
    assert result["counts"]["platforms"]["PASS"] == 21


def test_pending_matrix_never_passes(tmp_path):
    b = release.pending_bundle({r: "a" * 40 for r in release.REPOSITORIES})
    assert release.assess(b, tmp_path)["state"] == "BLOCKED"


@pytest.mark.parametrize("section", ["axes", "platforms"])
def test_duplicate_cannot_replace_missing_identity(bundle, tmp_path, section):
    bundle[section][1] = bundle[section][0]
    result = release.assess(bundle, tmp_path)
    assert result["state"] == "FAIL"
    assert any("missing cell" in e for e in result["errors"])


def test_stale_head_is_rejected(bundle, tmp_path):
    bundle["heads"]["thehub-pr"] = "b" * 40
    assert release.assess(bundle, tmp_path)["state"] == "FAIL"


def test_tampered_execution_log_is_rejected(bundle, tmp_path):
    (tmp_path / "execution.log").write_text("different bytes")
    assert release.assess(bundle, tmp_path)["state"] == "FAIL"


@pytest.mark.parametrize("mutation", ["journey", "platform", "kind", "residue", "exit", "traversal"])
def test_invalid_platform_receipts_fail_closed(bundle, tmp_path, mutation):
    row = bundle["platforms"][0]
    path = tmp_path / row["receipts"][0]["path"]
    receipt = json.loads(path.read_text())
    if mutation == "journey":
        del receipt["journey"]["rollback"]
    elif mutation == "platform":
        receipt["environment"]["platform"] = "other"
    elif mutation == "kind":
        receipt["evidence_kind"] = "syntax_only"
    elif mutation == "residue":
        receipt["residue"] = ["unresolved"]
    elif mutation == "exit":
        receipt["exit_code"] = 1
    else:
        receipt["log"]["path"] = "../outside.log"
    path.write_text(json.dumps(receipt))
    row["receipts"][0]["sha256"] = release.digest(path)
    assert release.assess(bundle, tmp_path)["state"] == "FAIL"


def test_duplicate_json_keys_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"state":"FAIL","state":"PASS"}')
    with pytest.raises(ValueError, match="duplicate JSON key"):
        release.read_json(path)


def test_missing_top_level_residue_is_not_zero(bundle, tmp_path):
    del bundle["source_residue"]
    assert release.assess(bundle, tmp_path)["state"] == "BLOCKED"
