"""Federated search and entity composition APIs against a real ingested store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import server.backend.main as backend_main  # noqa: E402
from hub.entity_composition import validate_entity_composition  # noqa: E402
from hub.ingest import ingest_aggregate  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
AGGREGATE = REPO_ROOT / "data" / "aggregate"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "hub.db"
    ingest_aggregate(AGGREGATE, db)
    monkeypatch.setattr(backend_main, "DB_PATH", db)
    with TestClient(backend_main.app) as test_client:
        yield test_client


def _rows(stream: str) -> list:
    return [json.loads(line) for line in (AGGREGATE / f"{stream}.jsonl").read_text(encoding="utf-8").splitlines()]


def _entity(predicate) -> dict:
    for row in _rows("entities"):
        if predicate(row):
            return row
    raise AssertionError("no matching entity")


def _composable_ovnis_case() -> dict:
    """An OVNIS case the committed sample holds with both an edge and a linked record.

    The fixture is a bounded sample re-drawn on every refresh, so the anchor is
    chosen from the data rather than pinned to one record's name.
    """
    named = {e for r in _rows("relationships") for e in (r.get("source_entity_id"), r.get("target_entity_id"))}
    linked = {o.get("entity_id") for o in _rows("observations")}
    return _entity(lambda r: "ovnis-pr" in (r.get("_producers") or []) and r["entity_id"] in named
                   and r["entity_id"] in linked)


def test_search_folds_accents_and_links_to_provenance(client):
    body = client.get("/api/search", params={"q": "PENUELAS"}).json()
    titles = {r["title"] for r in body["results"]}
    assert "Peñuelas" in titles
    hit = next(r for r in body["results"] if r["title"] == "Peñuelas")
    assert client.get(f"/api{hit['evidence_href']}").status_code == 200
    assert body["indexed_records"] > 0
    assert {p["producer"] for p in body["producers"]} >= {"aguayluz-pr", "ovnis-pr"}


def test_search_excludes_synthetic_by_default(client):
    hidden = client.get("/api/search", params={"q": "synthetic san juan"}).json()
    shown = client.get("/api/search", params={"q": "synthetic san juan", "include_synthetic": "true"}).json()
    assert hidden["excluded_synthetic"] >= 1
    assert all(not r["synthetic"] for r in hidden["results"])
    assert any(r["synthetic"] for r in shown["results"])
    assert hidden["matched"] == shown["matched"]


def test_search_empty_finding_and_validation(client):
    assert client.get("/api/search").json()["query_status"] == "EMPTY_QUERY"
    finding = client.get("/api/search", params={"q": "san juan", "type": "finding"}).json()
    assert finding["type_status"] == "NO_FINDINGS_RECORDED" and finding["results"] == []
    assert client.get("/api/search", params={"q": "x", "type": "tweet"}).status_code == 422
    assert client.get("/api/search", params={"q": "x", "cursor": "abc"}).status_code == 422
    assert client.get("/api/search", params={"q": "x", "limit": 0}).status_code == 422


def test_search_index_follows_store_writes(client):
    before = client.get("/api/search", params={"q": "zzyzx"}).json()
    assert before["total"] == 0
    backend_main_core = backend_main  # the module object is the preserved core
    with backend_main_core._conn() as conn:
        conn.execute(
            "INSERT INTO entities (entity_type, entity_id, data, updated_at) VALUES (?,?,?,?)",
            ("Entities", "ent_zzyzx", json.dumps({"entity_id": "ent_zzyzx", "name": "Zzyzx Road"}),
             "2999-01-01T00:00:00Z"),
        )
    after = client.get("/api/search", params={"q": "zzyzx"}).json()
    assert [r["record_id"] for r in after["results"]] == ["ent_zzyzx"]


def test_entity_composition_resolves_edges_and_linked_records(client):
    anchor = _composable_ovnis_case()
    response = client.get(f"/api/entity/{anchor['entity_id']}")
    assert response.status_code == 200
    body = response.json()
    assert validate_entity_composition(body) == []
    assert body["anchor"]["producer_record_id"] == anchor["entity_id"]
    assert body["relationships"] and body["linked_records"]
    for item in body["relationships"] + body["linked_records"]:
        assert client.get(f"/api{item['evidence_href']}").status_code == 200
    assert body["identity"]["registry_status"] == "NOT_CONFIGURED"


def test_entity_composition_keeps_hub_correlations_candidate(client):
    correlation = None
    for line in (AGGREGATE / "correlations.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("match_basis") == "location":
            correlation = row
            break
    assert correlation is not None
    body = client.get(f"/api/entity/{correlation['source_entity_id']}").json()
    edge = next(r for r in body["relationships"] if r["record_id"] == correlation["relationship_id"])
    assert edge["collection"] == "Correlations"
    assert edge["edge_state"] == "CANDIDATE"


def test_entity_composition_404_is_not_fabricated(client):
    missing = client.get("/api/entity/ent_does_not_exist")
    assert missing.status_code == 404
    assert "not found" in missing.json()["detail"]


def test_new_routes_are_not_shadowed_by_the_spa_catch_all():
    paths = [getattr(route, "path", None) for route in backend_main.app.router.routes]
    assert paths.count("/api/search") == 1
    assert paths.count("/api/entity/{record_id}") == 1
    spa = [i for i, p in enumerate(paths) if p == "/{full_path:path}"]
    assert all(i > paths.index("/api/search") for i in spa)
