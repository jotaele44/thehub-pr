"""Research API against a real ingested store.

Positive: the overview, record pages and case reconstruction serve the OVNIS
research rows the committed fixture holds; a finding row, once present, shows up
in the timeline's findings mode and in a FINDING search. Negative: every computed
pair is a CANDIDATE, kinds with no records say NONE_RECORDED, and an unknown
kind, a bad cursor or an unknown case is refused.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import server.backend.main as backend_main  # noqa: E402
from hub.ingest import ingest_aggregate  # noqa: E402

AGGREGATE = Path(__file__).resolve().parents[1] / "data" / "aggregate"


def _client(aggregate: Path, tmp_path: Path, monkeypatch):
    db = tmp_path / "hub.db"
    ingest_aggregate(aggregate, db)
    monkeypatch.setattr(backend_main, "DB_PATH", db)
    return TestClient(backend_main.app)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    with _client(AGGREGATE, tmp_path, monkeypatch) as test_client:
        yield test_client


def _all(client, kind, **params):
    records, cursor = [], None
    while True:
        body = client.get(f"/api/research/records/{kind}",
                          params={**params, "limit": 200, **({"cursor": cursor} if cursor else {})}).json()
        records += body["records"]
        cursor = body["next_cursor"]
        if cursor is None:
            return body, records


def test_overview_reports_what_the_store_holds(client):
    body = client.get("/api/research").json()
    assert body["contract"] == "federation-research-v1" and body["producer"] == "ovnis-pr"
    kinds = body["kinds"]
    assert set(kinds) == {"topics", "findings", "hypotheses", "contradictions", "adjudications", "queue",
                          "episodes", "reports"}
    for kind, numbers in kinds.items():
        assert numbers["kind_status"] == ("RECORDED" if numbers["total"] else "NONE_RECORDED"), kind
    # The committed fixture samples OVNIS's computed pairs and case reports.
    assert kinds["adjudications"]["total"] > 0 and kinds["reports"]["total"] > 0
    assert kinds["adjudications"]["computed_candidates"] == kinds["adjudications"]["total"]


def test_every_computed_pair_is_an_unreviewed_candidate(client):
    page, pairs = _all(client, "adjudications")
    assert page["total"] == len(pairs)
    for pair in pairs:
        assert pair["status"] == "CANDIDATE" and pair["origin"] == "COMPUTED"
        assert pair["epistemic_class"] == "COMPUTED"
        assert len(pair["case_ids"]) == 2
        assert pair["attributes"]["signals"]["date_relation"] in ("IDENTICAL_RECORDED_DATE", "COMPATIBLE_PRECISION")


def test_case_reconstruction_for_a_paired_case(client):
    _, pairs = _all(client, "adjudications")
    case_id = pairs[0]["case_ids"][0]
    body = client.get(f"/api/research/case/{case_id}").json()
    assert body["case"]["case_id"] == case_id
    assert body["case"]["temporal_precision"] in ("YEAR_ONLY", "MONTH_YEAR", "DATE_ONLY", "EXACT_TIMESTAMP", "UNKNOWN")
    assert any(a["record_id"] == pairs[0]["record_id"] for a in body["adjudications"])
    for adjudication in body["adjudications"]:
        assert adjudication["reviewed"] is False
        assert adjudication["other_case"]["case_id"] != case_id
    assert body["report_status"] in ("HELD", "NOT_HELD")


def test_case_with_a_held_report_carries_its_body(client):
    _, reports = _all(client, "reports")
    report = reports[0]
    case_id = report["case_ids"][0]
    body = client.get(f"/api/research/case/{case_id}").json()
    assert body["report_status"] == "HELD"
    assert body["report"]["case_id"] == case_id
    assert body["report"]["receipt"]["report_sha256"] == report["attributes"]["report"]["receipt"]["report_sha256"]
    assert body["unresolved"] == body["report"]["unresolved"]


def test_refusals(client):
    assert client.get("/api/research/records/patterns").status_code == 422
    assert client.get("/api/research/records/findings", params={"cursor": "abc"}).status_code == 422
    assert client.get("/api/research/records/findings", params={"limit": 0}).status_code == 422
    assert client.get("/api/research/case/NO-SUCH-CASE").status_code == 404
    empty = client.get("/api/research/records/findings").json()
    assert empty["kind_status"] == "NONE_RECORDED" and empty["records"] == []


def test_a_recorded_finding_reaches_the_timeline_and_search(tmp_path, monkeypatch):
    aggregate = tmp_path / "aggregate"
    shutil.copytree(AGGREGATE, aggregate)
    observations = [json.loads(line) for line in (aggregate / "observations.jsonl").read_text().splitlines() if line]
    case = next(o for o in observations if o.get("observation_type") == "uap_case" and (o.get("attributes") or {}).get("case_id"))
    case_id = case["attributes"]["case_id"]
    finding = {
        "entity_id": "ent_" + "f" * 32, "source_id": case["source_id"], "name": "The report cites a harbour pilot log",
        "normalized_name": "the report cites a harbour pilot log", "entity_type": "finding", "jurisdiction": "PR",
        "external_ids": {"ovnis_finding_id": "FIND-TEST"},
        "attributes": {"statement": "The report cites a harbour pilot log", "status": "CANDIDATE",
                       "epistemic_class": "CURATED", "case_ids": [case_id], "origin": "CURATED"},
        "confidence": 0.9, "lineage": {"producer_script": "test", "producer_phase": "TEST", "source_inputs": []},
        "evidence_state": {"contract": "federation-evidence-state-v1", "data_stage": "FINDING",
                           "epistemic_class": "CURATED"},
        "synthetic": False, "created_at": "2026-10-03T00:00:00Z", "extracted_at": "2026-10-03T00:00:00Z",
        "_producers": ["ovnis-pr"],
    }
    with (aggregate / "entities.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(finding) + "\n")

    with _client(aggregate, tmp_path, monkeypatch) as client:
        timeline = client.get("/api/timeline", params={"findings_only": "true"}).json()
        assert timeline["findings_status"] == "OK" and timeline["findings_total"] == 1
        assert [e["case_id"] for e in timeline["events"]] == [case_id]
        assert timeline["events"][0]["findings"][0]["finding_id"] == "FIND-TEST"

        search = client.get("/api/search", params={"q": "harbour pilot", "type": "finding"}).json()
        assert search["type_status"] == "OK"
        assert [r["finding_status"] for r in search["results"]] == ["CANDIDATE"]

        overview = client.get("/api/research").json()
        assert overview["kinds"]["findings"] == {"total": 1, "kind_status": "RECORDED",
                                                 "status_counts": {"CANDIDATE": 1}}
        reconstruction = client.get(f"/api/research/case/{case_id}").json()
        assert [f["record_id"] for f in reconstruction["findings"]] == ["FIND-TEST"]
