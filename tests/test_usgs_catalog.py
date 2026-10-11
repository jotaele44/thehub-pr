"""Positive/negative catalog, HTTP adapter, cache and canonical app route gates."""
import copy
import io
import json
import urllib.error
from pathlib import Path

import pytest

from hub.usgs_acquisition import enumerate_item, fetch_manifest, snapshot_item
from hub.usgs_catalog import catalog_page, load_catalog, validate_catalog

ITEM = "61ae5641d34eb622f69a7220"


def test_denominators_and_no_activation():
    c = load_catalog()
    assert c["counts"]["included"] == 174
    assert c["counts"]["excluded"] == 23
    assert c["counts"]["reviewed_rows"] == 197
    assert c["counts"]["missing_doi"] == 3
    assert sum(c["counts"]["categories"].values()) == 174
    assert all(not r["payload_verified"] and r["activation_state"] == "BLOCKED" for r in c["releases"])
    assert c["source"]["method_raw"][-1]["key"] == "Limit"


@pytest.mark.parametrize("mutation", ["duplicate", "promote", "repo", "excluded"])
def test_invalid_catalog_fails_closed(mutation):
    c = copy.deepcopy(load_catalog())
    if mutation == "duplicate":
        c["releases"][1]["sciencebase_id"] = c["releases"][0]["sciencebase_id"]
    elif mutation == "promote":
        c["releases"][0]["activation_state"] = "PASS"
    elif mutation == "repo":
        c["releases"][0]["consumer_candidates"][0]["repository"] = "someone/other"
    else:
        c["excluded"][0]["sciencebase_id"] = c["releases"][0]["sciencebase_id"]
    with pytest.raises(ValueError):
        validate_catalog(c)


def test_pagination_conserves_rows_and_candidates():
    c = load_catalog()
    rows, offset = [], 0
    while True:
        page = catalog_page(c, offset=offset, limit=13)
        rows.extend(page["records"])
        offset = page["next_offset"]
        if offset is None:
            break
    assert rows == c["releases"]
    assert catalog_page(c, program="spiderweb-pr", limit=200)["total"] == 174
    assert catalog_page(c, query="luminescence")["total"] > 0
    assert catalog_page(c, query="no_such_dataset_12345")["total"] == 0
    with pytest.raises(ValueError):
        catalog_page(c, program="invented")


def test_child_and_item_identity_gates():
    with pytest.raises(ValueError):
        enumerate_item({"id": "wrong"}, ITEM)
    assert enumerate_item({"id": ITEM, "files": []}, ITEM)["enumeration_state"] == "PROVISIONAL"
    manifest = enumerate_item({"id": ITEM, "files": [{"name": "x.zip"}], "hasChildren": False}, ITEM)
    assert manifest["enumeration_state"] == "PASS"
    assert manifest["payload_state"] == "BLOCKED"
    assert manifest["assets"][0]["raw_descriptor"] == {"name": "x.zip"}


def test_transport_failure_is_not_absence_and_is_reused(tmp_path):
    def forbidden(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b"forbidden"))
    first = snapshot_item(ITEM, tmp_path, forbidden)
    assert first["state"] == first["payload_state"] == "BLOCKED"
    assert first["http_status"] == 403
    second = snapshot_item(ITEM, tmp_path, lambda *a, **k: pytest.fail("Frozen input redownloaded"))
    assert first == second
    (tmp_path / ITEM / "response.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        snapshot_item(ITEM, tmp_path, forbidden)


def test_successful_metadata_is_not_payload_admission(tmp_path):
    class Response(io.BytesIO):
        status = 200
        headers = {"Content-Type": "application/json"}
    receipt = snapshot_item(ITEM, tmp_path, lambda *a, **k: Response(json.dumps({
        "id": ITEM, "hasChildren": False, "files": [{"name": "sample.csv"}]
    }).encode()))
    assert receipt["state"] == receipt["enumeration_state"] == "PASS"
    assert receipt["payload_state"] == "BLOCKED"
    assert receipt["asset_descriptor_count"] == 1


def test_unapproved_origin_and_invalid_id_refused(tmp_path):
    with pytest.raises(ValueError):
        fetch_manifest("https://example.com/metadata")
    with pytest.raises(ValueError):
        snapshot_item("../../outside", tmp_path)


def test_canonical_app_api_pagination_and_refusal(monkeypatch):
    from fastapi.testclient import TestClient
    import server.backend.main as main
    from server.backend import usgs_catalog_api
    monkeypatch.setattr(usgs_catalog_api, "SNAPSHOT", Path("/nonexistent/snapshot"))
    with TestClient(main.app) as client:
        response = client.get("/api/usgs/catalog?limit=200")
        assert response.status_code == 200
        assert len(response.json()["records"]) == 174
        assert response.json()["payload_state"] == "BLOCKED"
        assert client.get("/api/usgs/catalog?limit=201").status_code == 422
        assert client.get("/api/usgs/catalog?program=unknown").status_code == 422


def test_frozen_acquisition_is_visible_and_duplicate_receipts_refused(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from server.backend import usgs_catalog_api
    from server.backend.main import app
    with TestClient(app) as client:
        body = client.get("/api/usgs/catalog?limit=200").json()
        assert body["acquisition_summary"]["attempted"] == 174
        assert body["acquisition_summary"]["activated"] == 0
        assert all(r["acquisition"]["http_status"] == 403 for r in body["records"])
        summary = json.loads(usgs_catalog_api.SNAPSHOT.read_text())
        summary["receipts"].append(summary["receipts"][0])
        altered = tmp_path / "summary.json"
        altered.write_text(json.dumps(summary))
        monkeypatch.setattr(usgs_catalog_api, "SNAPSHOT", altered)
        assert client.get("/api/usgs/catalog").status_code == 422
