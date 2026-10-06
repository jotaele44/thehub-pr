"""Spatial features (hub.spatial_features).

Positive: a row with a declared point precision becomes a point feature with its
precision, category and evidence links; bbox, category and producer filters
narrow the set; nearby() orders by great-circle distance; every loaded row is
accounted for exactly once. Negative: a row with coordinates but no declared
point precision is counted, not drawn; AREA_REFERENCE and
coordinate-free rows are never drawn as points; a representative point is never
promoted; synthetic rows are excluded by default; invalid coordinates and a bad
bbox are refused.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hub import spatial_features as sf

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def _entity(record_id, lat=None, lon=None, precision=None, *, producer="aguayluz-pr", entity_type="utility_asset",
            municipality=None, synthetic=False, **extra):
    row = {"entity_id": record_id, "entity_type": entity_type, "name": f"Asset {record_id}",
           "_producers": [producer], "synthetic": synthetic, **extra}
    if lat is not None:
        row["location"] = {"lat": lat, "lon": lon}
    if municipality:
        row.setdefault("location", {})["municipality"] = municipality
    if precision:
        row["evidence_state"] = {"geometry_precision": precision, "coordinate_method": "AUTHORITATIVE"}
    return ("entities", "Entities", row)


def test_declared_point_becomes_a_feature_with_its_precision():
    body = sf.build_features([_entity("ent_1", 18.2, -66.5, "OBSERVED_POINT", municipality="Utuado")])
    (feature,) = body["features"]
    assert feature["geometry"] == {"type": "Point", "coordinates": [-66.5, 18.2]}
    props = feature["properties"]
    assert props["geometry_precision"] == "OBSERVED_POINT" and props["geometry_basis"] == "AUTHORITATIVE"
    assert props["category"] == "utility_asset" and props["producer"] == "aguayluz-pr"
    assert props["evidence_href"] == "/evidence/Entities/ent_1" and props["entity_href"] == "/entity/ent_1"
    assert props["municipality"] == "Utuado" and props["object_type"] is None
    assert body["precision_counts"] == {"OBSERVED_POINT": 1}
    assert body["area_references"] == []  # a mapped point is not also an area reference


def _accounted(body):
    return body["matched"] + body["outside_bbox"] + body["excluded_synthetic"] + sum(g["count"] for g in body["not_drawn"])


def test_undeclared_coordinates_are_counted_not_drawn():
    body = sf.build_features([_entity("ent_1", 18.2, -66.5), _entity("ent_2", 18.3, -66.6, producer="ovnis-pr"),
                              _entity("ent_3", 18.3, -66.6, "AREA_REFERENCE")])
    assert body["features"] == []
    assert body["coordinates_without_point_precision"] == {"aguayluz-pr": 2, "ovnis-pr": 1}
    assert body["not_drawn"] == [
        {"producer": "aguayluz-pr", "stream": "entities", "category": "utility_asset", "count": 2,
         "coordinates_without_point_precision": 2, "municipality_recorded": 0, "object_type_counts": {}},
        {"producer": "ovnis-pr", "stream": "entities", "category": "utility_asset", "count": 1,
         "coordinates_without_point_precision": 1, "municipality_recorded": 0, "object_type_counts": {}},
    ]
    assert body["loaded"] == 3 == _accounted(body)


def test_area_reference_and_municipality_only_rows_are_not_points():
    rows = [
        _entity("ent_1", 18.2, -66.5, "AREA_REFERENCE", municipality="Vieques"),
        _entity("ent_2", municipality="southwest", producer="ovnis-pr", entity_type="uap_case", object_type="UAP"),
        _entity("ent_3", municipality="Vieques", producer="ovnis-pr", entity_type="uap_case", object_type="Lights"),
    ]
    body = sf.build_features(rows + [_entity("ent_4", producer="ovnis-pr", entity_type="uap_case",
                                             object_type="Mutilation")])
    assert body["features"] == []
    cases = next(g for g in body["not_drawn"] if g["category"] == "uap_case")
    assert cases == {"producer": "ovnis-pr", "stream": "entities", "category": "uap_case", "count": 3,
                     "coordinates_without_point_precision": 0, "municipality_recorded": 2,
                     "object_type_counts": {"Lights": 1, "Mutilation": 1, "UAP": 1}}
    assert body["area_references"] == [
        {"producer": "aguayluz-pr", "stream": "entities", "category": "utility_asset",
         "municipality_as_recorded": "Vieques", "count": 1, "object_type_counts": {}},
        {"producer": "ovnis-pr", "stream": "entities", "category": "uap_case", "municipality_as_recorded": "Vieques",
         "count": 1, "object_type_counts": {"Lights": 1}},
        {"producer": "ovnis-pr", "stream": "entities", "category": "uap_case", "municipality_as_recorded": "southwest",
         "count": 1, "object_type_counts": {"UAP": 1}},
    ]


def test_representative_point_stays_representative():
    (feature,) = sf.build_features([_entity("ent_1", 18.0, -66.0, "REPRESENTATIVE_POINT")])["features"]
    assert feature["properties"]["geometry_precision"] == "REPRESENTATIVE_POINT"
    (near,) = sf.nearby([feature], 18.0, -66.0, 10)
    assert "representative point" in near["distance_basis"]


def test_filters_bbox_category_producer_and_synthetic():
    rows = [
        _entity("ent_1", 18.2, -66.5, "OBSERVED_POINT"),
        _entity("ent_2", 18.4, -65.9, "OBSERVED_POINT", producer="spiderweb-pr", entity_type="mineral_occurrence"),
        _entity("ent_3", 18.2, -66.4, "OBSERVED_POINT", synthetic=True),
        ("alerts", "Alerts", {"alert_id": "alrt_1", "module": "CONTAMINATION", "_producers": ["aguayluz-pr"],
                              "location": {"lat": 18.1, "lon": -66.1},
                              "evidence_state": {"geometry_precision": "REPRESENTATIVE_POINT"}}),
        ("relationships", "Relationships", {"relationship_id": "rel_1", "location": {"lat": 18, "lon": -66}}),
    ]
    everything = sf.build_features(rows)
    assert everything["matched"] == 3 and everything["excluded_synthetic"] == 1
    assert everything["loaded"] == 4 == _accounted(everything)  # the relationship row is not a mappable stream
    assert {f["properties"]["category"] for f in everything["features"]} == {"utility_asset", "mineral_occurrence",
                                                                             "CONTAMINATION"}
    assert sf.build_features(rows, include_synthetic=True)["matched"] == 4
    boxed = sf.build_features(rows, bbox=(-66.0, 18.3, -65.8, 18.5))
    assert [f["id"] for f in boxed["features"]] == ["evo:entities:ent_2"]
    assert boxed["outside_bbox"] == 2 and boxed["loaded"] == _accounted(boxed)
    assert sf.build_features(rows, categories=["CONTAMINATION"])["matched"] == 1
    assert sf.build_features(rows, producers=["spiderweb-pr"])["matched"] == 1
    capped = sf.build_features(rows, limit=1)
    assert capped["truncated"] is True and len(capped["features"]) == 1


def test_invalid_coordinates_are_ignored():
    rows = [_entity("ent_1", 95.0, -66.5, "OBSERVED_POINT"), _entity("ent_2", True, -66.5, "OBSERVED_POINT")]
    body = sf.build_features(rows)
    assert body["features"] == [] and body["coordinates_without_point_precision"] == {}
    assert body["not_drawn"][0]["count"] == 2


@pytest.mark.parametrize("text", ["1,2,3", "a,b,c,d", "10,10,5,5", "-200,0,10,10"])
def test_bad_bbox_is_refused(text):
    with pytest.raises(ValueError):
        sf.parse_bbox(text)


def test_nearby_orders_by_distance_and_respects_radius():
    rows = [_entity("near", 18.2001, -66.5, "OBSERVED_POINT"), _entity("far", 18.3, -66.5, "OBSERVED_POINT"),
            _entity("mid", 18.205, -66.5, "OBSERVED_POINT")]
    features = sf.build_features(rows)["features"]
    within = sf.nearby(features, 18.2, -66.5, 1000)
    assert [p["record_id"] for p in within] == ["near", "mid"]
    assert 10 < within[0]["distance_m"] < 12 and 550 < within[1]["distance_m"] < 560
    assert sf.parse_bbox(None) is None


def _observation(record_id, *, precision=None, **fields):
    row = {"observation_id": record_id, "observation_type": "uap_case", "_producers": ["ovnis-pr"],
           "location": {"lat": 18.2, "lon": -66.5},
           "evidence_state": {"geometry_precision": "OBSERVED_POINT", **({"temporal_precision": precision} if precision else {})},
           **fields}
    return ("observations", "Observations", row)


def test_each_date_spans_its_declared_precision():
    rows = [
        _observation("obs_year", precision="YEAR_ONLY", date_local="1952",
                     observed_at="1952-01-01T00:00:00-04:00"),
        _observation("obs_month", precision="MONTH_YEAR", date_local="1972-03"),
        _observation("obs_day", precision="DATE_ONLY", date_local="2001-02-03"),
        _observation("obs_instant", precision="EXACT_TIMESTAMP", observed_at="2019-10-01T04:00:00Z"),
        _observation("obs_undated"),
    ]
    props = {f["properties"]["record_id"]: f["properties"] for f in sf.build_features(rows, now=NOW)["features"]}
    year = props["obs_year"]
    # A year-only case stays a whole year: the producer's padded timestamp is not an instant.
    assert (year["observed_at"], year["time_start"], year["time_end"]) == (
        "1952", "1952-01-01T00:00:00.000Z", "1952-12-31T23:59:59.999Z")
    assert year["time_basis"].startswith("whole year")
    assert (props["obs_month"]["time_start"], props["obs_month"]["time_end"]) == (
        "1972-03-01T00:00:00.000Z", "1972-03-31T23:59:59.999Z")
    assert props["obs_day"]["time_end"] == "2001-02-03T23:59:59.999Z"
    assert props["obs_instant"]["time_start"] == props["obs_instant"]["time_end"] == "2019-10-01T04:00:00.000Z"
    assert props["obs_undated"]["time_start"] is None and props["obs_undated"]["time_basis"] == "undated"


def test_validity_window_extent_and_undated_count():
    rows = [
        ("alerts", "Alerts", {"alert_id": "alrt_1", "module": "CONTAMINATION", "_producers": ["aguayluz-pr"],
                              "location": {"lat": 18.1, "lon": -66.1}, "start_at": "2019-10-01T00:00:00Z",
                              "end_at": "2019-12-31T00:00:00Z",
                              "evidence_state": {"geometry_precision": "REPRESENTATIVE_POINT"}}),
        _observation("obs_undated"),
    ]
    body = sf.build_features(rows, now=NOW)
    alert = next(f["properties"] for f in body["features"] if f["properties"]["record_id"] == "alrt_1")
    assert (alert["valid_from"], alert["valid_to"]) == ("2019-10-01T00:00:00Z", "2019-12-31T00:00:00Z")
    assert alert["time_basis"] == "validity window as recorded"
    assert alert["temporal_state"] == "HISTORICAL"  # the window closed before NOW
    assert body["time_extent"] == {"start": "2019-10-01T00:00:00.000Z", "end": "2019-12-31T00:00:00.000Z"}
    assert body["undated"] == 1 and body["read_at"] == "2026-10-04T12:00:00.000Z"


def test_live_needs_a_declared_cadence():
    live = _observation("obs_live", precision="EXACT_TIMESTAMP", observed_at="2026-10-04T11:59:00Z")
    live[2]["evidence_state"].update({"expected_cadence_seconds": 300, "live_feed": True})
    undeclared = _observation("obs_recent", precision="EXACT_TIMESTAMP", observed_at="2026-10-04T11:59:00Z")
    props = {f["properties"]["record_id"]: f["properties"]
             for f in sf.build_features([live, undeclared], now=NOW)["features"]}
    assert props["obs_live"]["temporal_state"] == "LIVE"
    # Recent but without a declared cadence: never called live.
    assert props["obs_recent"]["temporal_state"] == "HISTORICAL"
    assert sf.build_features([], now=NOW)["time_extent"] is None
