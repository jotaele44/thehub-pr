"""Evidence Object API (server/backend/evidence_api.py) against a real ingested store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import server.backend.main as backend_main  # noqa: E402
from hub.evidence_object import row_sha256, validate_evidence_object  # noqa: E402
from hub.ingest import ingest_aggregate  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
AGGREGATE = REPO_ROOT / "data" / "aggregate"


def _first(stream: str, predicate=lambda row: True) -> dict:
    for line in (AGGREGATE / f"{stream}.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if predicate(row):
            return row
    raise AssertionError(f"no matching {stream} row")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "hub.db"
    ingest_aggregate(AGGREGATE, db)
    monkeypatch.setattr(backend_main, "DB_PATH", db)
    with TestClient(backend_main.app) as test_client:
        yield test_client


def test_observation_evidence_object_resolves_with_lineage(client):
    row = _first("observations", lambda r: r.get("date_precision") == "year" and not r.get("synthetic"))
    response = client.get(f"/api/evidence/Observations/{row['observation_id']}")
    assert response.status_code == 200
    body = response.json()
    assert validate_evidence_object(body) == []
    assert body["id"] == f"evo:observations:{row['observation_id']}"
    assert body["temporal_precision"] == "YEAR_ONLY"
    assert "T" not in body["observed_at"]
    assert body["audit_metadata"]["row_sha256"] == row_sha256(row)
    assert body["source_state"] in {"SOURCE_BOUND", "SOURCE_REPORTED"}


def test_source_and_relationship_collections(client):
    source = _first("sources")
    body = client.get(f"/api/evidence/Sources/{source['source_id']}").json()
    assert body["stream"] == "sources"
    assert validate_evidence_object(body) == []

    correlation = _first("correlations", lambda r: r.get("match_basis") == "location")
    body = client.get(f"/api/evidence/Correlations/{correlation['relationship_id']}").json()
    edges = [e for e in body["lineage"]["edges"] if e["from"].startswith("entity:")]
    assert edges and {e["edge_state"] for e in edges} == {"CANDIDATE"}


def test_synthetic_rows_stay_flagged(client):
    row = _first("observations", lambda r: r.get("synthetic") is True)
    body = client.get(f"/api/evidence/Observations/{row['observation_id']}").json()
    assert body["synthetic"] is True


def test_unknown_collection_and_record_are_404_not_fabricated(client):
    assert client.get("/api/evidence/Tweets/x").status_code == 404
    missing = client.get("/api/evidence/Observations/obs_does_not_exist")
    assert missing.status_code == 404
    assert "not found" in missing.json()["detail"]


def test_extension_routes_are_not_shadowed_by_the_spa_catch_all():
    paths = [getattr(route, "path", None) for route in backend_main.app.router.routes]
    assert paths.count("/api/evidence/{collection}/{record_id}") == 1
    if "/{full_path:path}" in paths:
        catch_all = paths.index("/{full_path:path}")
        assert catch_all == len(paths) - 1
        assert paths.index("/api/evidence/{collection}/{record_id}") < catch_all
        assert paths.index("/api/gis/proxy") < catch_all
