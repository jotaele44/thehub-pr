import json
import sqlite3

from server.backend.federal_records import (
    assessment_surfaces,
    correlate_case,
    generate_candidates,
    project_stream,
)


def _db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE entities (entity_type TEXT, entity_id TEXT, data TEXT, updated_at TEXT, PRIMARY KEY(entity_type, entity_id))")
    return conn


def test_projection_is_idempotent():
    conn = _db()
    row = {"document_id": "doc_" + "1" * 32, "title": "Puerto Rico record"}
    first = project_stream(conn, "federal_documents", [row], "2026-07-27T00:00:00Z")
    second = project_stream(conn, "federal_documents", [row], "2026-07-27T00:00:01Z")
    assert first == {"inserted": 1, "updated": 0, "unchanged": 0}
    assert second == {"inserted": 0, "updated": 0, "unchanged": 1}
    stored = conn.execute("SELECT data FROM entities").fetchone()[0]
    assert json.loads(stored)["title"] == "Puerto Rico record"


def test_direct_and_context_correlation_requires_review():
    case = {"id": "OVNIS-1984-001", "entity_id": "ent_" + "2" * 32, "municipality": "Ceiba", "event_date": "1984-05-01", "facilities": ["Roosevelt Roads"]}
    document = {"document_id": "doc_" + "1" * 32, "document_date_start": "1984-05-01"}
    finding = {
        "finding_id": "find_" + "3" * 32,
        "document_id": document["document_id"],
        "context_summary": "OVNIS-1984-001 activity near Roosevelt Roads",
        "municipalities": ["Ceiba"],
        "facilities": ["Roosevelt Roads"],
    }
    candidate = correlate_case(case, finding, document)
    assert candidate is not None
    assert candidate["requires_human_review"] is True
    assert candidate["candidate_score"] == 1.0
    assert "DIRECT_CASE_IDENTIFIER" in candidate["candidate_basis"]


def test_candidate_replay_and_surfaces():
    conn = _db()
    cases = [{"id": "CASE-1", "entity_id": "ent_" + "4" * 32, "municipality": "Ponce"}]
    documents = [{"document_id": "doc_" + "5" * 32}]
    findings = [{"finding_id": "find_" + "6" * 32, "document_id": documents[0]["document_id"], "context_summary": "Ponce", "municipalities": ["Ponce"]}]
    assert generate_candidates(conn, cases, findings, documents, "now")["inserted"] == 1
    assert generate_candidates(conn, cases, findings, documents, "later")["unchanged"] == 1
    surfaces = assessment_surfaces([
        {"classification": "CONTRADICTORY"},
        {"classification": "DATA_GAP"},
        {"classification": "NO_KNOWN_MATCH"},
    ])
    assert len(surfaces["contradictions"]) == 1
    assert len(surfaces["data_gaps"]) == 1
    assert len(surfaces["no_known_match"]) == 1
