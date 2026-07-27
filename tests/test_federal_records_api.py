import json
import sqlite3
from pathlib import Path

from server.backend import mcp_api


def _seed(path: Path):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE entities (entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, "
        "data TEXT NOT NULL, updated_at TEXT NOT NULL, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    rows = [
        (
            "FederalDocuments",
            "doc_" + "1" * 32,
            {
                "document_id": "doc_" + "1" * 32,
                "title": "Roosevelt Roads activity",
                "document_date_start": "1988-01-30",
                "municipalities": ["Ceiba"],
                "facilities": ["Roosevelt Roads"],
            },
        ),
        (
            "CaseActivityAssessments",
            "assess_" + "2" * 32,
            {
                "assessment_id": "assess_" + "2" * 32,
                "case_id": "OVNIS-1988-001",
                "classification": "DATA_GAP",
            },
        ),
    ]
    for entity_type, entity_id, row in rows:
        conn.execute(
            "INSERT INTO entities VALUES (?,?,?,?)",
            (entity_type, entity_id, json.dumps(row), "2026-07-27T16:00:00Z"),
        )
    conn.commit()
    conn.close()


def test_indexes_and_filtered_rows(tmp_path, monkeypatch):
    path = tmp_path / "hub.db"
    _seed(path)
    monkeypatch.setattr(mcp_api, "DB_PATH", path)
    mcp_api.ensure_federal_indexes(path)
    rows = mcp_api._federal_rows(
        "FederalDocuments",
        municipality="Ceiba",
        facility="Roosevelt Roads",
        date_from="1988-01-01",
        date_to="1988-12-31",
    )
    assert len(rows) == 1
    assert rows[0]["document_id"].startswith("doc_")
    conn = sqlite3.connect(path)
    indexes = {row[1] for row in conn.execute("PRAGMA index_list('entities')")}
    conn.close()
    assert "idx_entities_type_updated" in indexes
    assert "idx_entities_type_id" in indexes


def test_case_scope_does_not_cross_match(tmp_path, monkeypatch):
    path = tmp_path / "hub.db"
    _seed(path)
    monkeypatch.setattr(mcp_api, "DB_PATH", path)
    assert len(mcp_api._federal_rows("CaseActivityAssessments", case_id="OVNIS-1988-001")) == 1
    assert mcp_api._federal_rows("CaseActivityAssessments", case_id="OVNIS-1990-999") == []
