"""Event timeline API against a real ingested store."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import server.backend.main as backend_main  # noqa: E402
from hub.event_timeline import recorded_date  # noqa: E402
from hub.ingest import ingest_aggregate  # noqa: E402

AGGREGATE = Path(__file__).resolve().parents[1] / "data" / "aggregate"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "hub.db"
    ingest_aggregate(AGGREGATE, db)
    monkeypatch.setattr(backend_main, "DB_PATH", db)
    with TestClient(backend_main.app) as test_client:
        yield test_client


def _all_events(client, **params):
    events, cursor = [], None
    while True:
        body = client.get("/api/timeline", params={**params, "limit": 200, **({"cursor": cursor} if cursor else {})}).json()
        events += body["events"]
        cursor = body["next_cursor"]
        if cursor is None:
            return body, events


def test_timeline_orders_the_stored_ovnis_cases(client):
    body, events = _all_events(client)
    assert body["producer_status"] == "AVAILABLE" and len(events) == body["matched"] > 0
    keys = [recorded_date({"date_local": e["date"]})[2] for e in events if e["date"]]
    assert keys == sorted(keys)
    assert [e["date"] for e in events[len(keys):]] == [None] * body["undated"]
    newest = client.get("/api/timeline", params={"sort": "newest", "limit": 1}).json()["events"][0]
    assert recorded_date({"date_local": newest["date"]})[2][0] == max(k[0] for k in keys)


def test_page_events_cite_their_source_and_link_provenance(client):
    events = client.get("/api/timeline", params={"limit": 20}).json()["events"]
    cited = [e for e in events if e["source"]]
    assert cited, "every stored OVNIS case observation cites a stored source"
    for event in cited:
        assert client.get(f"/api{event['evidence_href']}").status_code == 200
        assert client.get(f"/api{event['source']['evidence_href']}").status_code == 200


def test_category_filter_and_counts(client):
    body = client.get("/api/timeline").json()
    category = body["categories"][0]["category"]
    filtered = client.get("/api/timeline", params={"category": category, "limit": 200}).json()
    assert filtered["matched"] == body["categories"][0]["count"]
    assert {e["category"] for e in filtered["events"]} == {category}


def test_findings_mode_reports_none_recorded(client):
    body = client.get("/api/timeline", params={"findings_only": True}).json()
    assert body["events"] == [] and body["findings_status"] == "NO_FINDINGS_RECORDED"


def test_bad_parameters_are_rejected(client):
    assert client.get("/api/timeline", params={"sort": "random"}).status_code == 422
    assert client.get("/api/timeline", params={"cursor": "x"}).status_code == 422
    assert client.get("/api/timeline", params={"limit": 1000}).status_code == 422


def test_timeline_route_is_not_shadowed_by_the_spa_catch_all():
    paths = [getattr(route, "path", None) for route in backend_main.app.router.routes]
    assert "/api/timeline" in paths
    catch_all = [i for i, p in enumerate(paths) if p and "{full_path" in p]
    assert not catch_all or paths.index("/api/timeline") < catch_all[0]
