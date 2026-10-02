"""Event timeline over the OVNIS case corpus: positive and negative cases."""

from __future__ import annotations

import pytest

from hub.event_timeline import build_timeline, era, parse_cursor, recorded_date


def case(obs_id, date, *, category="UAP", precision=None, synthetic=False, producer="ovnis-pr", **extra):
    row = {
        "observation_id": obs_id, "entity_id": f"ent_{obs_id}", "source_id": f"src_{obs_id}",
        "observation_type": "uap_case", "date_local": date, "object_type": category,
        "location_name": f"Place {obs_id}", "synthetic": synthetic, "_producers": [producer],
        "attributes": {"case_id": f"PRUAP-{obs_id}", "description": f"Narrative {obs_id}"},
    }
    if precision:
        row["evidence_state"] = {"contract": "federation-evidence-state-v1", "temporal_precision": precision}
    row.update(extra)
    return row


ROWS = [
    case("a", "1967-03-02", precision="DATE_ONLY"),
    case("b", "1967", precision="YEAR_ONLY", category="USO"),
    case("c", "1967-03", precision="MONTH_YEAR"),
    case("d", "1954-11-20", precision="EXACT_TIMESTAMP", time_local="21:30", category="Lights"),
    case("e", "", category="USO"),
    case("f", "2001-05-05", synthetic=True),
    case("g", "1999-01-01", producer="skywatcher-pr"),
]


def ids(result):
    return [e["observation_id"] for e in result["events"]]


def test_year_only_and_month_dates_are_never_given_more_precision():
    result = build_timeline(ROWS)
    by_id = {e["observation_id"]: e for e in result["events"]}
    assert by_id["b"]["date"] == "1967" and by_id["b"]["temporal_precision"] == "YEAR_ONLY"
    assert by_id["c"]["date"] == "1967-03" and by_id["c"]["temporal_precision"] == "MONTH_YEAR"
    assert by_id["b"]["time"] is None and by_id["a"]["time"] is None
    assert by_id["d"]["time"] == "21:30" and by_id["d"]["temporal_precision"] == "EXACT_TIMESTAMP"


def test_oldest_orders_by_period_start_with_coarser_records_first():
    assert ids(build_timeline(ROWS, sort="oldest")) == ["d", "b", "c", "a", "e"]


def test_newest_reverses_dated_events_and_keeps_undated_last():
    assert ids(build_timeline(ROWS, sort="newest")) == ["a", "c", "b", "d", "e"]


def test_undated_cases_are_kept_and_counted_not_dropped():
    result = build_timeline(ROWS)
    assert result["undated"] == 1
    undated = result["events"][-1]
    assert undated["date"] is None and undated["temporal_precision"] == "UNKNOWN" and undated["era"] is None


def test_only_ovnis_case_rows_are_timeline_events():
    result = build_timeline(ROWS + [{"observation_type": "adsb_contact", "observation_id": "x"}])
    assert "g" not in ids(result) and "x" not in ids(result)
    assert result["loaded_events"] == 6


def test_synthetic_rows_are_excluded_by_default_and_counted():
    result = build_timeline(ROWS)
    assert "f" not in ids(result) and result["excluded_synthetic"] == 1
    assert "f" in ids(build_timeline(ROWS, include_synthetic=True))


def test_category_counts_and_filter():
    result = build_timeline(ROWS, categories=["USO"])
    assert ids(result) == ["b", "e"]
    assert {c["category"]: c["count"] for c in result["categories"]} == {"Lights": 1, "UAP": 2, "USO": 2}
    assert result["selected_categories"] == ["USO"] and result["matched"] == 2


def test_findings_mode_says_none_are_recorded_instead_of_showing_an_empty_result():
    result = build_timeline(ROWS, findings_only=True)
    assert result["events"] == [] and result["matched"] == 0
    assert result["findings_total"] == 0 and result["findings_status"] == "NO_FINDINGS_RECORDED"


def test_findings_mode_keeps_only_cases_an_ovnis_finding_names():
    links = {"ent_c": [{"finding_id": "fnd_1", "status": "CANDIDATE"}]}
    result = build_timeline(ROWS, findings_only=True, finding_links=links)
    assert ids(result) == ["c"] and result["events"][0]["findings"] == links["ent_c"]
    assert result["findings_total"] == 1 and result["findings_status"] == "OK"


def test_rendering_keeps_geography_source_bounded_and_links_provenance():
    event = next(e for e in build_timeline(ROWS)["events"] if e["observation_id"] == "a")
    assert event["place"] == {"municipality": None, "location_name": "Place a"}
    assert event["case_id"] == "PRUAP-a" and event["narrative"] == "Narrative a"
    assert event["era"] == "1960s" and event["category"] == "UAP"
    assert event["evidence_href"] == "/evidence/Observations/a" and event["entity_href"] == "/entity/ent_a"
    assert "latitude" not in event and "longitude" not in event


def test_missing_narrative_is_none_not_invented():
    row = case("z", "1980-01-01")
    row["attributes"] = {}
    event = build_timeline([row])["events"][0]
    assert event["narrative"] is None and event["case_id"] is None and event["title"] == "Place z"


def test_precision_falls_back_to_the_recorded_date_shape_when_undeclared():
    assert recorded_date({"date_local": "1975"})[1] == "YEAR_ONLY"
    assert recorded_date({"date_local": "1975-06", "date_precision": "month"})[1] == "MONTH_YEAR"
    assert recorded_date({"date_local": "June 1975"}) == (None, None, None)
    assert era("1999-12-31") == "1990s" and era(None) is None


def test_pagination_is_bounded_and_complete():
    first = build_timeline(ROWS, limit=2)
    second = build_timeline(ROWS, limit=2, offset=int(first["next_cursor"]))
    third = build_timeline(ROWS, limit=2, offset=int(second["next_cursor"]))
    assert ids(first) + ids(second) + ids(third) == ids(build_timeline(ROWS))
    assert third["next_cursor"] is None


def test_bad_sort_and_cursor_are_rejected():
    with pytest.raises(ValueError):
        build_timeline(ROWS, sort="random")
    with pytest.raises(ValueError):
        parse_cursor("-1")
    assert parse_cursor(None) == 0


def test_no_ovnis_rows_reports_no_data():
    result = build_timeline([])
    assert result["producer_status"] == "NO_DATA" and result["events"] == [] and result["loaded_events"] == 0
