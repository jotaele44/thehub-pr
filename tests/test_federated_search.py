"""Federated lexical search (hub.federated_search).

Positive: multiword AND, accent/case folding, prefix terms, cross-producer
results with provenance links, typed filters, bounded pagination.
Negative: an empty query returns nothing, synthetic rows are excluded and
counted, FINDING is an explicit empty type, unknown types and cursors fail.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hub.federated_search import (
    IN_SCOPE_PRODUCERS,
    SEARCH_TYPES,
    FederatedSearchIndex,
    fold,
    parse_cursor,
    words,
)
from hub.ingest import STREAM_TO_COLLECTION

AGGREGATE = Path(__file__).resolve().parents[1] / "data" / "aggregate"


def _row(stream, record_id, **extra):
    id_field = {"entities": "entity_id", "sources": "source_id", "observations": "observation_id",
                "alerts": "alert_id"}[stream]
    row = {id_field: record_id, "_producers": ["ovnis-pr"], "synthetic": False}
    row.update(extra)
    return (stream, STREAM_TO_COLLECTION[stream], row)


@pytest.fixture()
def index():
    return FederatedSearchIndex.build([
        _row("entities", "e1", name="Peñuelas", entity_type="municipality", _producers=["aguayluz-pr"]),
        _row("entities", "e2", name="Laguna Cartagena", entity_type="wetland", _producers=["spiderweb-pr"]),
        _row("entities", "e3", name="Laguna Tortuguero", entity_type="wetland", _producers=["spiderweb-pr"]),
        _row("sources", "s1", source_name="Cartagena field notes", source_type="field_note"),
        _row("observations", "o1", observation_type="uap_case", location_name="Laguna Cartagena",
             evidence_state={"epistemic_class": "CURATED"}),
        _row("observations", "o2", observation_type="adsb_contact", location_name="Laguna Cartagena",
             evidence_state={"epistemic_class": "MEASURED"}, _producers=["skywatcher-pr"]),
        _row("alerts", "a1", alert_type="outage", module="POWER_OPS", location={"municipality": "Peñuelas"},
             _producers=["aguayluz-pr"]),
        _row("entities", "e4", name="Synthetic Cartagena point", synthetic=True, _producers=["skywatcher-pr"]),
        ("relationships", "Relationships", {"relationship_id": "r1", "relationship_type": "located_in"}),
        _row("entities", "", name="no id"),
    ])


def test_fold_strips_accents_and_case():
    assert fold("Peñuelas MAYAGÜEZ") == "penuelas mayaguez"
    assert words("San Germán, P.R.") == ["san", "german", "p", "r"]


def test_multiword_query_requires_every_term(index):
    body = index.search("laguna cartagena")
    ids = {r["record_id"] for r in body["results"]}
    assert ids == {"e2", "o1", "o2"}
    assert "e3" not in ids  # "laguna" alone is not enough


def test_accent_folding_and_prefix_terms(index):
    assert {r["record_id"] for r in index.search("PENUELAS")["results"]} == {"e1", "a1"}
    assert {r["record_id"] for r in index.search("cartag")["results"]} >= {"e2", "s1"}


def test_results_carry_provenance_links(index):
    result = next(r for r in index.search("laguna cartagena")["results"] if r["record_id"] == "e2")
    assert result["evidence_id"] == "evo:entities:e2"
    assert result["evidence_href"] == "/evidence/Entities/e2"
    assert result["entity_href"] == "/entity/e2"
    assert result["producers"] == ["spiderweb-pr"]
    source = index.search("field notes")["results"][0]
    assert source["kind"] == "SOURCE" and source["entity_href"] is None


def test_kinds_and_type_filters(index):
    kinds = {r["record_id"]: r["kind"] for r in index.search("cartagena", include_synthetic=True)["results"]}
    assert kinds == {"e2": "ENTITY", "s1": "SOURCE", "o1": "TIMELINE", "o2": "READING", "e4": "ENTITY"}
    assert [r["record_id"] for r in index.search("cartagena", kind="READING")["results"]] == ["o2"]
    assert [r["record_id"] for r in index.search("cartagena", kind="SOURCE")["results"]] == ["s1"]
    assert {r["record_id"] for r in index.search("penuelas", kind="TIMELINE")["results"]} == {"a1"}
    assert set(SEARCH_TYPES) == {"ALL", "READING", "FINDING", "TIMELINE", "SOURCE", "ENTITY"}


def test_title_matches_rank_first(index):
    ids = [r["record_id"] for r in index.search("laguna cartagena")["results"]]
    assert ids[0] == "e2"


def test_synthetic_rows_are_excluded_and_counted(index):
    body = index.search("cartagena")
    assert "e4" not in {r["record_id"] for r in body["results"]}
    assert body["excluded_synthetic"] == 1
    assert body["matched"] == body["total"] + body["excluded_synthetic"]
    included = index.search("cartagena", include_synthetic=True)
    assert "e4" in {r["record_id"] for r in included["results"]}
    assert included["excluded_synthetic"] == 0


def test_empty_query_returns_nothing(index):
    for query in ("", "   ", "¿?", "—"):
        body = index.search(query)
        assert body["query_status"] == "EMPTY_QUERY"
        assert body["results"] == [] and body["total"] == 0


def test_finding_is_explicitly_empty(index):
    body = index.search("cartagena", kind="FINDING")
    assert body["type_status"] == "NO_PRODUCER_EMITS_FINDINGS"
    assert body["results"] == []


def test_pagination_is_bounded_and_complete(index):
    first = index.search("cartagena", limit=2)
    assert len(first["results"]) == 2 and first["next_cursor"] == "2"
    rest = index.search("cartagena", limit=2, offset=parse_cursor(first["next_cursor"]))
    assert rest["next_cursor"] is None
    seen = [r["record_id"] for r in first["results"] + rest["results"]]
    assert len(seen) == len(set(seen)) == first["total"]
    assert len(index.search("cartagena", limit=10_000)["results"]) <= 100


def test_unknown_type_and_bad_cursor_are_rejected(index):
    with pytest.raises(ValueError):
        index.search("x", kind="TWEET")
    for cursor in ("-1", "abc", "1.5"):
        with pytest.raises(ValueError):
            parse_cursor(cursor)
    assert parse_cursor(None) == parse_cursor("") == 0


def test_rows_without_ids_and_non_search_streams_are_not_indexed(index):
    assert index.search("no id")["total"] == 0
    assert all(doc.stream != "relationships" for doc in index.docs)
    assert len(index.docs) == 8


def test_producer_availability_reports_no_data_without_inventing(index):
    status = {p["producer"]: p for p in index.search("x")["producers"]}
    assert status["spiderweb-pr"]["status"] == "AVAILABLE"
    assert status["moneysweep-pr"] == {"producer": "moneysweep-pr", "status": "NO_DATA", "indexed_records": 0}
    assert set(IN_SCOPE_PRODUCERS) <= set(status)


def test_committed_aggregate_is_searchable_across_producers():
    rows = []
    for stream in ("entities", "sources", "observations", "alerts"):
        for line in (AGGREGATE / f"{stream}.jsonl").read_text(encoding="utf-8").splitlines():
            rows.append((stream, STREAM_TO_COLLECTION[stream], json.loads(line)))
    index = FederatedSearchIndex.build(rows)
    body = index.search("san juan")
    producers = {p for r in body["results"] for p in r["producers"]}
    assert len(producers) >= 2
    assert body["excluded_synthetic"] >= 1
    assert all(not r["synthetic"] for r in body["results"])
    assert body["indexed_records"] == len(rows)
