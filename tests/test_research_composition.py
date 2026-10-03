"""Research composition (hub.research_composition).

Positive: research rows are grouped by kind with their own status, topic cards
count findings and distinct sources, a case is reconstructed from the rows that
name it, and findings link to timeline cases. Negative: an empty ledger is
NONE_RECORDED rather than an empty result, a computed pair stays a CANDIDATE
and unreviewed, repeated citations of one source count once, synthetic rows are
excluded by default, rows from another producer are ignored, and an unknown
kind is rejected.
"""

from __future__ import annotations

import pytest

from hub import research_composition as rc


def _row(entity_type, record_id, *, producer="ovnis-pr", synthetic=False, entity_id=None, **attributes):
    key = dict(rc.KINDS.values())[entity_type]
    return {
        "entity_id": entity_id or f"ent_{record_id.lower()}",
        "entity_type": entity_type,
        "name": attributes.get("title") or attributes.get("statement") or record_id,
        "external_ids": {key: record_id},
        "attributes": attributes,
        "_producers": [producer],
        "synthetic": synthetic,
        "evidence_state": {"epistemic_class": "CURATED", "data_stage": "CANONICAL"},
    }


def _case(case_id, entity_id, source_id="src_a", **attributes):
    return {"entity_id": entity_id, "entity_type": "uap_case", "name": f"Place of {case_id}", "source_id": source_id,
            "external_ids": {"ovnis_case_id": case_id}, "attributes": {"case_id": case_id, **attributes},
            "_producers": ["ovnis-pr"]}


def _pair(adjudication_id, a, b, origin="COMPUTED", status="CANDIDATE", **extra):
    return _row("manifestation_adjudication", adjudication_id, case_a=a, case_b=b, origin=origin, status=status,
                signals={"date_relation": "COMPATIBLE_PRECISION", "place_basis": "MUNICIPALITY",
                         "narrative_similarity": 0.3, "same_source": False}, **extra)


def test_empty_store_reports_none_recorded_not_an_empty_result():
    body = rc.overview([])
    assert body["producer_status"] == "NO_DATA"
    assert {kind: v["kind_status"] for kind, v in body["kinds"].items()} == {kind: "NONE_RECORDED" for kind in rc.KINDS}
    assert body["topics"] == []
    page = rc.records("findings", [])
    assert page["kind_status"] == "NONE_RECORDED" and page["records"] == [] and page["next_cursor"] is None


def test_overview_counts_kinds_statuses_and_origins():
    rows = [
        _row("finding", "FIND-2", status="ACCEPTED"), _row("finding", "FIND-1", status="CANDIDATE"),
        _pair("ADJ-C-1", "PRUAP-0001", "PRUAP-0002"),
        _pair("ADJ-1", "PRUAP-0003", "PRUAP-0004", origin="CURATED", status="DISTINCT"),
        _row("finding", "FIND-9", producer="spiderweb-pr", status="ACCEPTED"),
        _row("finding", "FIND-8", synthetic=True, status="CANDIDATE"),
        {"entity_id": "ent_x", "entity_type": "municipality", "_producers": ["ovnis-pr"]},
    ]
    body = rc.overview(rows)
    assert body["producer_status"] == "AVAILABLE"
    assert body["kinds"]["findings"] == {"total": 2, "kind_status": "RECORDED",
                                         "status_counts": {"ACCEPTED": 1, "CANDIDATE": 1}}
    assert body["kinds"]["adjudications"]["computed_candidates"] == 1
    assert body["kinds"]["adjudications"]["curated_decisions"] == 1
    assert rc.overview(rows, include_synthetic=True)["kinds"]["findings"]["total"] == 3


def test_topic_cards_count_findings_and_distinct_sources():
    topic = _row("research_topic", "TOPIC-USO", title="Submerged objects")
    findings = [
        _row("finding", "FIND-1", status="ACCEPTED", topic_ids=["TOPIC-USO"],
             source_refs=[{"case_id": "PRUAP-0001", "locator": "p1"}, {"source_id": "SRC-0001", "locator": "p2"}]),
        _row("finding", "FIND-2", status="CANDIDATE", topic_ids=["TOPIC-USO"],
             source_refs=[{"case_id": "PRUAP-0002", "locator": "p9"}]),
        _row("finding", "FIND-3", status="CANDIDATE", topic_ids=["TOPIC-OTHER"],
             source_refs=[{"case_id": "PRUAP-0003", "locator": "p1"}]),
    ]
    # PRUAP-0001 and PRUAP-0002 cite the same source document: one source, not two.
    (card,) = rc.topic_cards([topic], findings, {"PRUAP-0001": "src_same", "PRUAP-0002": "src_same"})
    assert card["finding_count"] == 2 and card["finding_ids"] == ["FIND-1", "FIND-2"]
    assert card["finding_status_counts"] == {"ACCEPTED": 1, "CANDIDATE": 1}
    assert card["source_count"] == 2
    assert "count once" in card["source_count_basis"]


def test_records_filter_and_page():
    rows = [_pair(f"ADJ-C-{i}", f"PRUAP-000{i}", f"PRUAP-001{i}") for i in range(5)]
    rows.append(_pair("ADJ-9", "PRUAP-0001", "PRUAP-0002", origin="CURATED", status="SAME_EVENT"))
    first = rc.records("adjudications", rows, origin="COMPUTED", limit=2)
    assert first["total"] == 6 and first["matched"] == 5 and first["next_cursor"] == "2"
    assert {r["status"] for r in first["records"]} == {"CANDIDATE"}
    rest = rc.records("adjudications", rows, origin="COMPUTED", limit=10, offset=2)
    assert len(rest["records"]) == 3 and rest["next_cursor"] is None
    assert [r["record_id"] for r in rc.records("adjudications", rows, status="SAME_EVENT")["records"]] == ["ADJ-9"]
    with pytest.raises(ValueError, match="unknown research kind"):
        rc.records("patterns", rows)


def test_cases_named_covers_every_reference_shape():
    contradiction = _row("contradiction", "CONTRA-1", case_ids=["PRUAP-0001"],
                         claim_a={"text": "a", "source_ref": {"case_id": "PRUAP-0002", "locator": "x"}},
                         claim_b={"text": "b", "source_ref": {"source_id": "SRC-0001", "locator": "y"}})
    report = _row("case_report", "RPT-PRUAP-0005", report={"case_id": "PRUAP-0005"})
    assert rc.cases_named(contradiction) == {"PRUAP-0001", "PRUAP-0002"}
    assert rc.cases_named(report) == {"PRUAP-0005"}
    assert rc.cases_named(_pair("ADJ-C-1", "PRUAP-0007", "PRUAP-0008")) == {"PRUAP-0007", "PRUAP-0008"}


def test_finding_links_attach_findings_to_case_entities():
    findings = [_row("finding", "FIND-1", status="CANDIDATE", statement="One newspaper", case_ids=["PRUAP-0001"]),
                _row("finding", "FIND-2", status="ACCEPTED", source_refs=[{"case_id": "PRUAP-0002", "locator": "p"}]),
                _row("finding", "FIND-3", status="CANDIDATE", case_ids=["PRUAP-9999"])]
    links = rc.finding_links(findings, {"PRUAP-0001": "ent_c1", "PRUAP-0002": "ent_c2"})
    assert [f["finding_id"] for f in links["ent_c1"]] == ["FIND-1"]
    assert links["ent_c2"][0]["status"] == "ACCEPTED"
    assert set(links) == {"ent_c1", "ent_c2"}  # an unknown case links nowhere


def test_case_reconstruction_arranges_without_inferring():
    case = _case("PRUAP-0001", "ent_c1", object_type="UAP", evidence_tier="T3", description="Lights over the bay.")
    observation = {"observation_id": "obs_1", "entity_id": "ent_c1", "observation_type": "uap_case", "date_local": "1972",
                   "location_name": "Bahía", "municipality": None, "evidence_state": {"temporal_precision": "YEAR_ONLY"}}
    research = [
        _pair("ADJ-C-1", "PRUAP-0001", "PRUAP-0002"),
        _pair("ADJ-C-2", "PRUAP-0001", "PRUAP-0404"),
        _row("finding", "FIND-1", status="CANDIDATE", case_ids=["PRUAP-0001"]),
        _row("finding", "FIND-2", status="CANDIDATE", case_ids=["PRUAP-0002"]),
        _row("case_report", "RPT-PRUAP-0001", report={"case_id": "PRUAP-0001", "unresolved": [
            {"kind": "RECORD_GAP", "detail": "municipality not recorded"}]}),
    ]
    other = rc.case_summary(_case("PRUAP-0002", "ent_c2"), None)
    body = rc.case_reconstruction(case, observation=observation, source={"source_id": "src_a", "source_name": "El Vocero"},
                                  research_rows=research, other_cases={"PRUAP-0002": other})
    assert body["case"]["date"] == "1972" and body["case"]["temporal_precision"] == "YEAR_ONLY"
    assert body["case"]["time"] is None and body["case"]["place"]["municipality"] is None
    assert [f["record_id"] for f in body["findings"]] == ["FIND-1"]
    pairs = {a["record_id"]: a for a in body["adjudications"]}
    assert pairs["ADJ-C-1"]["status"] == "CANDIDATE" and pairs["ADJ-C-1"]["reviewed"] is False
    assert pairs["ADJ-C-1"]["other_case"]["held"] is True and pairs["ADJ-C-1"]["other_case"]["case_id"] == "PRUAP-0002"
    assert pairs["ADJ-C-2"]["other_case"] == {"case_id": "PRUAP-0404", "held": False}
    assert body["report_status"] == "HELD" and body["unresolved"][0]["detail"] == "municipality not recorded"
    assert body["source"]["name"] == "El Vocero"

    bare = rc.case_reconstruction(case, research_rows=[])
    assert bare["report_status"] == "NOT_HELD" and bare["report"] is None and bare["unresolved"] == []
    assert bare["case"]["date"] is None and bare["case"]["temporal_precision"] == "UNKNOWN"
    dated = rc.case_summary(_case("PRUAP-0003", "ent_c3", event_date="1967-03"))
    assert (dated["date"], dated["temporal_precision"]) == ("1967-03", "MONTH_YEAR")
