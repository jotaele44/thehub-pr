"""Federation Constellation API against a real ingested store."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import server.backend.main as backend_main  # noqa: E402
from hub.constellation import SAMPLE_LIMIT  # noqa: E402
from hub.ingest import ingest_aggregate  # noqa: E402

AGGREGATE = Path(__file__).resolve().parents[1] / "data" / "aggregate"
SUMMARY = json.loads((AGGREGATE / "graph_summary.json").read_text())


@pytest.fixture(scope="module")
def body(tmp_path_factory):
    db = tmp_path_factory.mktemp("constellation") / "hub.db"
    ingest_aggregate(AGGREGATE, db)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(backend_main, "DB_PATH", db)
        with TestClient(backend_main.app) as client:
            response = client.get("/api/constellation")
            assert response.status_code == 200
            payload = response.json()
            sample = next(n for n in payload["lenses"]["content"]["nodes"] if n.get("samples"))["samples"][0]
            evidence = client.get(f"/api{sample['href']}")
            payload["_evidence_status"] = evidence.status_code
            yield payload


def _content(body):
    return {n["id"]: n for n in body["lenses"]["content"]["nodes"]}


def _stored_rows():
    counts: Counter = Counter()
    for stream in ("sources", "entities", "relationships", "observations", "alerts"):
        for line in (AGGREGATE / f"{stream}.jsonl").read_text().splitlines():
            for producer in json.loads(line).get("_producers") or []:
                counts[(producer, stream)] += 1
    return counts


def test_exported_totals_match_graph_summary(body):
    nodes = _content(body)
    app_of = {a["program_id"]: a["id"] for a in body["apps"]}
    for program, streams in SUMMARY["producers"].items():
        for stream, total in streams.items():
            assert nodes[f"content:{app_of[program]}:{stream}"]["total"] == total
    for stream, total in SUMMARY["streams"].items():
        assert nodes[f"content:thehub:stream:{stream}"]["total"] == total
    assert body["totals"]["exported"] == sum(SUMMARY["streams"].values())
    assert body["store_status"] == "AVAILABLE"


def test_stored_counts_are_the_rows_the_store_holds(body):
    nodes = _content(body)
    app_of = {a["program_id"]: a["id"] for a in body["apps"]}
    for (program, stream), count in _stored_rows().items():
        assert nodes[f"content:{app_of[program]}:{stream}"]["stored"] == count


def test_samples_are_real_stored_rows(body):
    ids = {json.loads(line).get(key)
           for stream, key in (("sources", "source_id"), ("entities", "entity_id"), ("relationships", "relationship_id"),
                               ("observations", "observation_id"), ("alerts", "alert_id"), ("correlations", "relationship_id"))
           for line in (AGGREGATE / f"{stream}.jsonl").read_text().splitlines()}
    sampled = [s for n in body["lenses"]["content"]["nodes"] for s in n.get("samples") or []]
    assert sampled
    assert all(s["id"] in ids for s in sampled)
    assert all(len(n.get("samples") or []) <= SAMPLE_LIMIT for n in body["lenses"]["content"]["nodes"])
    assert body["_evidence_status"] == 200


def test_lineage_links_code_to_content(body):
    nodes = _content(body)
    assert nodes["content:moneysweep:entities"]["lineage"][0]["script"] == "moneysweep/federation/canonical_v1_bridge.py"
    links = {(link["code"], link["content"]) for link in body["links"]}
    assert ("moneysweep.bridge", "content:moneysweep:entities") in links
    assert ("aguayluz.export", "content:aguayluz:alerts") in links


def test_correlations_are_counted_as_synthetic_candidates(body):
    rows = [json.loads(line) for line in (AGGREGATE / "correlations.jsonl").read_text().splitlines()]
    nodes = _content(body)
    strategies = [n for n in nodes.values() if n["kind"] == "correlation"]
    assert sum(n["total"] for n in strategies) == len(rows) == body["totals"]["correlations"]
    assert all(n["synthetic"] for n in strategies)
    pairs = [e for e in body["lenses"]["content"]["edges"] if e["kind"] == "correlation"]
    assert pairs and all(e["synthetic"] for e in pairs)
    assert sum(e["weight"] for e in pairs) <= len(rows)


def test_an_empty_store_serves_the_code_lens(tmp_path, monkeypatch):
    monkeypatch.setattr(backend_main, "DB_PATH", tmp_path / "empty.db")
    with TestClient(backend_main.app) as client:
        payload = client.get("/api/constellation").json()
    assert payload["store_status"] == "EMPTY"
    assert payload["lenses"]["code"]["nodes"]
    assert not [n for n in payload["lenses"]["content"]["nodes"] if n["kind"] == "stream"]
