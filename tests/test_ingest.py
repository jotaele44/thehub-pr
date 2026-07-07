"""Tests for the aggregate -> entity-store ingest bridge (hub.ingest).

The bridge maps canonical aggregate streams onto the UI's per-domain collection
names and field shapes (UnifiedSources, GraphNodes, GraphEdges, ...).
"""
import json
import sqlite3

from hub.aggregate import aggregate
from hub.ingest import ingest_aggregate


def _ids(path):
    """entity ids present in an aggregate JSONL stream file."""
    field = {"entities": "entity_id", "sources": "source_id",
             "relationships": "relationship_id"}[path.stem]
    return {json.loads(line)[field]
            for line in path.read_text().splitlines() if line.strip()}


def _rows(db, collection):
    """{entity_id: parsed data} for one store collection."""
    conn = sqlite3.connect(db)
    try:
        cur = conn.execute(
            "SELECT entity_id, data FROM entities WHERE entity_type=?", (collection,)
        )
        return {r[0]: json.loads(r[1]) for r in cur.fetchall()}
    finally:
        conn.close()


def _count(db):
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    finally:
        conn.close()


def test_ingest_maps_streams_onto_ui_collections(valid_package, tmp_path):
    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)
    expected_nodes = _ids(agg / "entities.jsonl")
    expected_sources = _ids(agg / "sources.jsonl")
    expected_edges = _ids(agg / "relationships.jsonl")

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    assert summary["collections"] == {
        "UnifiedSources": 1, "GraphNodes": 2, "GraphEdges": 1, "FederationSummary": 1,
    }
    assert summary["total"] == 5
    assert summary["skipped"] == {}

    # entities -> GraphNodes, keyed by canonical entity_id, with UI field names added
    # and the canonical payload + provenance preserved.
    nodes = _rows(db, "GraphNodes")
    assert set(nodes) == expected_nodes
    node = nodes[next(iter(expected_nodes))]
    assert node["node_id"] == node["id"]         # id injected + node_id alias
    assert node["label"] == node["name"]         # UI alias of canonical name
    assert node["node_type"] == node["entity_type"]
    assert node["confidence"] in {"Low", "Medium", "High"}  # banded from numeric
    assert node["_producers"] == ["moneysweep-pr"]          # canonical provenance kept

    # sources -> UnifiedSources with title alias.
    sources = _rows(db, "UnifiedSources")
    assert set(sources) == expected_sources
    src = next(iter(sources.values()))
    assert src["title"] == src["source_name"]
    assert src["program_id"] == "moneysweep-pr"

    # relationships -> GraphEdges with node aliases.
    edges = _rows(db, "GraphEdges")
    assert set(edges) == expected_edges
    edge = next(iter(edges.values()))
    assert edge["edge_id"] == edge["id"]
    assert edge["source_node_id"] == edge["source_entity_id"]
    assert edge["target_node_id"] == edge["target_entity_id"]

    # graph_summary -> single FederationSummary row.
    summary_rows = _rows(db, "FederationSummary")
    assert set(summary_rows) == {"graph_summary"}
    assert "streams" in summary_rows["graph_summary"]


def test_ingest_maps_correlations_to_crossover_links(valid_package, tmp_path):
    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)
    rel_id = "rel_ffffffffffffffffffffffffffffffff"
    corr = {
        "relationship_id": rel_id,
        "source_id": "src_0123456789abcdef0123456789abcdef",
        "source_entity_id": "ent_0123456789abcdef0123456789abce01",
        "target_entity_id": "ent_0123456789abcdef0123456789abce02",
        "relationship_type": "entity_correlation",
        "evidence_source_id": "src_0123456789abcdef0123456789abcdef",
        "confidence": 0.8, "explanation": "shared normalized name",
        "lineage": {"producer_script": "src/hub/correlate.py",
                    "producer_phase": "HUB_CORRELATE", "source_inputs": []},
        "synthetic": True, "created_at": "1970-01-01T00:00:00Z",
        "extracted_at": "1970-01-01T00:00:00Z",
    }
    (agg / "correlations.jsonl").write_text(json.dumps(corr) + "\n")

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    assert summary["collections"]["CrossoverLinks"] == 1
    link = _rows(db, "CrossoverLinks")[rel_id]
    assert link["crossover_id"] == rel_id
    assert link["source_record_id"] == "ent_0123456789abcdef0123456789abce01"
    assert link["correlation_type"] == "entity_correlation"
    assert link["confidence_band"] == "High"
    assert link["status"] == "PendingReview"


def test_ingest_maps_alerts_to_governance(tmp_path):
    agg = tmp_path / "agg"
    agg.mkdir()
    alert = {
        "alert_id": "alrt_0123456789abcdef0123456789abcdef",
        "module": "HYDRO_OPS", "alert_type": "maintenance", "severity": 3,
        "status": "active", "observed_at": "2026-01-01T00:00:00Z",
        "entity_id": "ent_0123456789abcdef0123456789abce01",
    }
    (agg / "alerts.jsonl").write_text(json.dumps(alert) + "\n")

    db = tmp_path / "hub.db"
    ingest_aggregate(agg, db)

    ga = _rows(db, "GovernanceAlerts")["alrt_0123456789abcdef0123456789abcdef"]
    assert ga["review_status"] == "active"
    assert ga["occurred_at"] == "2026-01-01T00:00:00Z"
    assert ga["record_id"] == "ent_0123456789abcdef0123456789abce01"
    assert ga["severity"] == 3


def test_ingest_is_idempotent(valid_package, tmp_path):
    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)
    db = tmp_path / "hub.db"

    first = ingest_aggregate(agg, db)
    total_after_first = _count(db)
    second = ingest_aggregate(agg, db)

    assert first["collections"] == second["collections"]
    assert _count(db) == total_after_first


def test_ingest_skips_rows_missing_canonical_id(tmp_path):
    agg = tmp_path / "agg"
    agg.mkdir()
    good_id = "ent_0123456789abcdef0123456789abce01"
    good = {"entity_id": good_id, "name": "FEMA"}
    bad = {"name": "no id here"}
    (agg / "entities.jsonl").write_text(
        json.dumps(good) + "\n" + json.dumps(bad) + "\n"
    )

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    assert summary["collections"]["GraphNodes"] == 1
    assert summary["skipped"] == {"GraphNodes": 1}
    assert set(_rows(db, "GraphNodes")) == {good_id}


def test_ingest_empty_dir_returns_zero(tmp_path):
    agg = tmp_path / "empty"
    agg.mkdir()
    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)
    assert summary["total"] == 0
    assert summary["collections"] == {}


def test_ingest_cli_reports_and_errors(valid_package, tmp_path):
    from hub.cli import main

    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)
    db = tmp_path / "hub.db"

    assert main(["ingest", "--in", str(agg), "--db", str(db)]) == 0
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["ingest", "--in", str(empty), "--db", str(db)]) == 1
