"""Spatial API against a real ingested store.

Positive: the committed fixture's declared points are served with their
precision and category, and Location Intel lists what the Hub holds around a
point, nearest first. Negative: undeclared coordinates and OVNIS cases are not
drawn, municipality references are passed through as recorded, and a bad bbox
or coordinate is refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import server.backend.main as backend_main  # noqa: E402
from hub.ingest import ingest_aggregate  # noqa: E402

AGGREGATE = Path(__file__).resolve().parents[1] / "data" / "aggregate"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "hub.db"
    ingest_aggregate(AGGREGATE, db)
    monkeypatch.setattr(backend_main, "DB_PATH", db)
    with TestClient(backend_main.app) as test_client:
        yield test_client


def test_features_are_declared_points_only(client):
    body = client.get("/api/spatial/features").json()
    assert body["contract"] == "federation-spatial-features-v1" and body["type"] == "FeatureCollection"
    assert body["matched"] > 0 and body["matched"] == len(body["features"])
    for feature in body["features"]:
        assert feature["geometry"]["type"] == "Point"
        assert feature["properties"]["geometry_precision"] in ("OBSERVED_POINT", "INTERPRETED_POINT", "REPRESENTATIVE_POINT")
        assert feature["properties"]["producer"] != "ovnis-pr"  # OVNIS declares no point precision
    assert sum(body["precision_counts"].values()) == body["matched"]
    assert body["coordinates_without_point_precision"].get("ovnis-pr", 0) > 0
    not_drawn = sum(group["count"] for group in body["not_drawn"])
    assert body["loaded"] == body["matched"] + body["excluded_synthetic"] + body["outside_bbox"] + not_drawn


def test_ovnis_references_are_passed_through_as_recorded(client):
    body = client.get("/api/spatial/features").json()
    refs = [r for r in body["area_references"] if r["producer"] == "ovnis-pr"]
    assert refs and all(r["category"] == "uap_case" for r in refs)
    # In the store OVNIS records place values on its uap_case observations, never on the case entities.
    assert {r["stream"] for r in refs} == {"observations"}
    cases = next(g for g in body["not_drawn"]
                 if (g["producer"], g["stream"], g["category"]) == ("ovnis-pr", "observations", "uap_case"))
    assert cases["municipality_recorded"] == sum(r["count"] for r in refs) < cases["count"]
    # OVNIS records regions ("southwest", "island-wide") as well as municipalities; the API does not judge.
    assert {r["municipality_as_recorded"] for r in refs} & {"southwest", "vieques"}
    # The producer's own object_type is counted as recorded, never re-labelled.
    assert all(sum(r["object_type_counts"].values()) == r["count"] for r in refs)


def test_bbox_and_category_filters(client):
    everything = client.get("/api/spatial/features").json()
    kind = everything["categories"][0]["category"]
    only = client.get("/api/spatial/features", params={"category": kind}).json()
    assert only["matched"] > 0 and {f["properties"]["category"] for f in only["features"]} == {kind}
    lon, lat = everything["features"][0]["geometry"]["coordinates"]
    box = f"{lon - 0.001},{lat - 0.001},{lon + 0.001},{lat + 0.001}"
    boxed = client.get("/api/spatial/features", params={"bbox": box}).json()
    assert 1 <= boxed["matched"] <= everything["matched"]


def test_location_intel_lists_nearby_rows(client):
    feature = client.get("/api/spatial/features").json()["features"][0]
    lon, lat = feature["geometry"]["coordinates"]
    body = client.get("/api/spatial/intel", params={"lat": lat, "lon": lon, "radius_m": 2000,
                                                    "municipality": "VIEQUES"}).json()
    assert body["nearby"][0]["distance_m"] == 0.0
    assert body["nearby_total"] == sum(body["category_counts"].values())
    assert [r["distance_m"] for r in body["nearby"]] == sorted(r["distance_m"] for r in body["nearby"])
    assert all(r["municipality_as_recorded"].lower() == "vieques" for r in body["municipality_area_references"])


def test_refusals(client):
    assert client.get("/api/spatial/features", params={"bbox": "1,2,3"}).status_code == 422
    assert client.get("/api/spatial/features", params={"limit": 0}).status_code == 422
    assert client.get("/api/spatial/intel", params={"lat": 95, "lon": 0}).status_code == 422
    assert client.get("/api/spatial/intel", params={"lat": 18, "lon": -66, "radius_m": 1}).status_code == 422
    assert client.get("/api/spatial/intel").status_code == 422
