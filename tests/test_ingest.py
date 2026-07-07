"""Tests for the aggregate -> entity-store ingest bridge (hub.ingest)."""
import json
import sqlite3

from hub.aggregate import aggregate
from hub.ingest import ingest_aggregate

from tests.conftest import ENT_AGENCY, ENT_RECIPIENT, REL, SRC


def _rows(db, collection):
    """Return {entity_id: parsed data} for one collection."""
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


def test_ingest_loads_streams_into_collections(valid_package, tmp_path):
    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    assert summary["collections"] == {
        "Sources": 1, "Entities": 2, "Relationships": 1, "FederationSummary": 1,
    }
    assert summary["total"] == 5
    assert summary["skipped"] == {}

    # Entities keyed by canonical entity_id, payload preserved incl. _producers.
    entities = _rows(db, "Entities")
    assert set(entities) == {ENT_AGENCY, ENT_RECIPIENT}
    agency = entities[ENT_AGENCY]
    assert agency["id"] == ENT_AGENCY          # id injected for the server read path
    assert agency["name"] == "FEMA"            # canonical payload intact
    assert agency["_producers"] == ["moneysweep-pr"]

    assert set(_rows(db, "Sources")) == {SRC}
    assert set(_rows(db, "Relationships")) == {REL}
    # graph_summary folded into a single FederationSummary row.
    summary_rows = _rows(db, "FederationSummary")
    assert set(summary_rows) == {"graph_summary"}
    assert "streams" in summary_rows["graph_summary"]


def test_ingest_is_idempotent(valid_package, tmp_path):
    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)
    db = tmp_path / "hub.db"

    first = ingest_aggregate(agg, db)
    total_after_first = _count(db)
    second = ingest_aggregate(agg, db)

    # INSERT OR REPLACE on (entity_type, entity_id) -> no duplicate rows.
    assert first["collections"] == second["collections"]
    assert _count(db) == total_after_first


def test_ingest_maps_correlations_by_relationship_id(valid_package, tmp_path):
    agg = tmp_path / "agg"
    aggregate({"moneysweep-pr": valid_package}, agg)
    # Hand-write a correlation row (federation_relationship shape) as correlate would.
    corr = {
        "relationship_id": "rel_ffffffffffffffffffffffffffffffff",
        "source_id": SRC, "source_entity_id": ENT_AGENCY,
        "target_entity_id": ENT_RECIPIENT, "relationship_type": "entity_correlation",
        "evidence_source_id": SRC, "confidence": 0.8,
        "lineage": {"producer_script": "src/hub/correlate.py",
                    "producer_phase": "HUB_CORRELATE", "source_inputs": []},
        "synthetic": True, "created_at": "1970-01-01T00:00:00Z",
        "extracted_at": "1970-01-01T00:00:00Z",
    }
    (agg / "correlations.jsonl").write_text(json.dumps(corr) + "\n")

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    assert summary["collections"]["Correlations"] == 1
    assert set(_rows(db, "Correlations")) == {"rel_ffffffffffffffffffffffffffffffff"}


def test_ingest_skips_rows_missing_canonical_id(tmp_path):
    agg = tmp_path / "agg"
    agg.mkdir()
    good = {"entity_id": ENT_AGENCY, "name": "FEMA"}
    bad = {"name": "no id here"}
    (agg / "entities.jsonl").write_text(
        json.dumps(good) + "\n" + json.dumps(bad) + "\n"
    )

    db = tmp_path / "hub.db"
    summary = ingest_aggregate(agg, db)

    assert summary["collections"]["Entities"] == 1
    assert summary["skipped"] == {"Entities": 1}
    assert set(_rows(db, "Entities")) == {ENT_AGENCY}


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
    # Empty aggregate dir -> non-zero exit.
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["ingest", "--in", str(empty), "--db", str(db)]) == 1
