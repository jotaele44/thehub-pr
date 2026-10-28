"""Real frozen descriptor checks, cache invariants and network refusal cases."""

import hashlib
import io
import json
import urllib.error
import zipfile
from pathlib import Path

import pytest

from hub.usgs_facet_snapshot import (
    PLAN_SHA256, acquire_facet_snapshot, load_facet_plan, verify_facet_archive,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "registry/usgs/facet_acquisition_plan.v1.json"
WKT = b'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'


class Response(io.BytesIO):
    status = 200
    headers = {"Content-Type": "application/octet-stream"}


def fake_opener(calls):
    target_by_url = {
        t["raw_descriptor"]["url"]: t for t in load_facet_plan(PLAN)["targets"]
    }

    def open_url(request, timeout):
        calls.append(request.full_url)
        name = target_by_url[request.full_url]["raw_descriptor"]["name"]
        if name.endswith(".cpg"):
            return Response(b"UTF-8")
        if name.endswith(".prj"):
            return Response(WKT)
        raise urllib.error.HTTPError(
            request.full_url, 503, "unavailable", {}, io.BytesIO(b"error")
        )

    return open_url


def test_real_frozen_cpg_and_prj_bytes_pass_without_promoting_other_components(
    tmp_path,
):
    calls = []
    r = acquire_facet_snapshot(
        PLAN, tmp_path / "snapshot", "fixture", fake_opener(calls)
    )
    assert len(calls) == 16 and r["target_count"] == 16
    assert r["byte_states"] == {"PASS": 6, "FAIL": 0, "BLOCKED": 10}
    assert r["state"] == r["scientific_staging"] == "BLOCKED" and r["activated"] == 0
    assert r["captured_response_bytes"] <= r["byte_budget"] == 1048576
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (tmp_path / "snapshot").iterdir()
    }

    def never(*a, **kw):
        raise AssertionError("Cached pass/failure must never issue another request")

    assert acquire_facet_snapshot(PLAN, tmp_path / "snapshot", "fixture", never) == r
    assert before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (tmp_path / "snapshot").iterdir()
    }


@pytest.mark.parametrize("failure", ["checksum", "oversize", "redirect", "timeout"])
def test_source_failures_remain_frozen_evidence(tmp_path, failure):
    def response(request, timeout):
        if failure == "redirect":
            raise urllib.error.HTTPError(
                request.full_url,
                302,
                "redirect",
                {"Location": "https://other.example/file"},
                io.BytesIO(b"redirect"),
            )
        if failure == "timeout":
            raise TimeoutError("timeout")
        return Response(b"ABCDE" if failure == "checksum" else b"X" * 500000)

    r = acquire_facet_snapshot(PLAN, tmp_path / "run", "failure", response)
    assert r["byte_states"]["PASS"] == 0
    assert r["activated"] == 0 and r["state"] == "BLOCKED"
    assert r["captured_response_bytes"] <= 1048576
    if failure in ("redirect", "timeout"):
        assert r["byte_states"]["BLOCKED"] == 16
    else:
        assert r["byte_states"]["FAIL"] > 0


@pytest.mark.parametrize(
    "mutation", ["body", "receipt", "summary", "orphan", "missing_pair", "identity"]
)
def test_corrupt_or_incomplete_cached_evidence_refuses_before_any_network(
    tmp_path, mutation
):
    out = tmp_path / "run"
    acquire_facet_snapshot(PLAN, out, "frozen", fake_opener([]))
    if mutation == "body":
        (out / "15.response.bin").write_bytes(b"changed")
    elif mutation == "receipt":
        p = out / "15.receipt.json"
        r = json.loads(p.read_text())
        r["reference_id"] = "foreign"
        p.write_text(json.dumps(r))
    elif mutation == "summary":
        p = out / "summary.json"
        r = json.loads(p.read_text())
        r["state"] = "PASS"
        p.write_text(json.dumps(r))
    elif mutation == "missing_pair":
        (out / "15.receipt.json").unlink()
        (out / "15.response.bin").unlink()
    elif mutation == "orphan":
        (out / "15.receipt.json").unlink()
    else:
        p = out / "snapshot.json"
        r = json.loads(p.read_text())
        r["snapshot_id"] = "foreign"
        p.write_text(json.dumps(r))

    def never(*a, **kw):
        raise AssertionError("No network while cached evidence is inconsistent")

    with pytest.raises(ValueError):
        acquire_facet_snapshot(PLAN, out, "frozen", never)


def test_plan_identity_snapshot_id_and_unknown_files_are_not_overwritten(tmp_path):
    changed = tmp_path / "plan.json"
    changed.write_bytes(PLAN.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Unreviewed"):
        load_facet_plan(changed)
    assert hashlib.sha256(PLAN.read_bytes()).hexdigest() == PLAN_SHA256
    with pytest.raises(ValueError, match="snapshot ID"):
        acquire_facet_snapshot(PLAN, tmp_path / "run", "../escape")
    out = tmp_path / "nonempty"
    out.mkdir()
    (out / "unrelated").write_text("keep")
    with pytest.raises(ValueError, match="Nonempty"):
        acquire_facet_snapshot(PLAN, out, "run")
    assert (out / "unrelated").read_text() == "keep"


ARCHIVE = ROOT / "data/usgs/snapshots/20261028_runner_facets.zip"
ARCHIVE_SHA = "3861e09f6fcf4d0f698faa6d2d7df125b00de8dbf380af3e433c256fa16dbb92"


def test_frozen_runner_archive_replays_source_checks_without_promotion():
    result = verify_facet_archive(ARCHIVE, ARCHIVE_SHA, PLAN)
    assert result["reference_count"] == 16 and result["bytes"] == 378473
    assert result["state"] == "PASS" and result["activated"] == 0
    assert result["scientific_staging"] == result["activation_state"] == "BLOCKED"


@pytest.mark.parametrize("mutation", ["body", "identity", "missing", "promotion", "typed_receipt"])
def test_self_consistently_rehashed_archive_still_requires_frozen_source(tmp_path, mutation):
    with zipfile.ZipFile(ARCHIVE) as z:
        members = {name: z.read(name) for name in z.namelist()}
    summary = json.loads(members["summary.json"])
    receipt = json.loads(members["00.receipt.json"])
    if mutation == "body":
        raw = members["00.response.bin"]
        members["00.response.bin"] = bytes([raw[0] ^ 1]) + raw[1:]
        receipt["sha256"] = hashlib.sha256(members["00.response.bin"]).hexdigest()
    elif mutation == "identity":
        receipt["source_item_id"] = "foreign"
    elif mutation == "missing":
        del members["15.response.bin"]
    elif mutation == "promotion":
        summary["scientific_staging"] = "PASS"
    else:
        # Python dict equality considers 200 and 200.0 equal; preserve JSON types.
        receipt["http_status"] = 200.0
    if mutation != "typed_receipt":
        summary["receipts"][0] = receipt
    members["00.receipt.json"] = json.dumps(receipt).encode()
    members["summary.json"] = json.dumps(summary).encode()
    changed = tmp_path / "changed.zip"
    with zipfile.ZipFile(changed, "w", zipfile.ZIP_DEFLATED) as z:
        for name, raw in members.items():
            z.writestr(name, raw)
    with pytest.raises(ValueError):
        verify_facet_archive(changed, hashlib.sha256(changed.read_bytes()).hexdigest(), PLAN)
