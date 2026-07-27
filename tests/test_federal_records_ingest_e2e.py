import hashlib
import json
import sqlite3
from pathlib import Path

from tools.ingest_federal_records import ingest, init_entities


def _write_jsonl(path: Path, rows: list[dict]) -> str:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_centininelas_hub_candidate_ingest_is_idempotent(tmp_path: Path):
    package = tmp_path / "package"
    package.mkdir()
    db = tmp_path / "hub.db"
    conn = sqlite3.connect(db)
    init_entities(conn)
    case = {
        "id": "OVNIS-1984-001",
        "entity_id": "ent_" + "9" * 32,
        "municipality": "Ceiba",
        "event_date": "1984-05-01",
        "facilities": ["Roosevelt Roads"],
    }
    conn.execute(
        "INSERT INTO entities(entity_type, entity_id, data, updated_at) VALUES (?,?,?,?)",
        ("Cases", case["id"], json.dumps(case), "2026-07-27T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    lineage = {"producer_script": "fixture", "producer_phase": "TEST", "source_inputs": ["fixture"]}
    document_id = "doc_" + "1" * 32
    release_id = "relv_" + "2" * 32
    documents = [{
        "document_id": document_id,
        "originating_agency": "Department of the Navy",
        "repository": "NARA",
        "title": "Synthetic Roosevelt Roads activity record",
        "document_date_start": "1984-05-01",
        "document_date_end": None,
        "document_type": "memorandum",
        "jurisdiction": "PR",
        "canonical_identity_basis": ["TEST-001"],
        "confidence": 1.0,
        "lineage": lineage,
        "synthetic": True,
        "created_at": "2026-07-27T16:00:00Z",
        "extracted_at": "2026-07-27T16:00:00Z",
    }]
    findings = [{
        "finding_id": "find_" + "3" * 32,
        "document_id": document_id,
        "release_id": release_id,
        "page_start": 1,
        "page_end": 1,
        "finding_type": "FEDERAL_MILITARY_ACTIVITY",
        "matched_form": "Roosevelt Roads",
        "canonical_entity": "Naval Station Roosevelt Roads",
        "municipalities": ["Ceiba"],
        "facilities": ["Roosevelt Roads"],
        "coordinates": [],
        "subject_categories": ["military operations"],
        "context_summary": "OVNIS-1984-001 activity near Roosevelt Roads",
        "evidence_tier": "T1",
        "automated_confidence": 0.95,
        "reviewer_confidence": 0.95,
        "review_status": "human_verified",
        "cointelpro_disposition": "NOT_COINTELPRO",
        "citation": {"page": 1, "source_url": "https://example.test/record.pdf", "content_sha256": "a" * 64},
        "lineage": lineage,
        "synthetic": True,
        "created_at": "2026-07-27T16:00:00Z",
        "extracted_at": "2026-07-27T16:00:00Z",
    }]
    entries = []
    for stream, rows in (("federal_documents", documents), ("document_findings", findings)):
        filename = f"{stream}.jsonl"
        digest = _write_jsonl(package / filename, rows)
        entries.append({
            "filename": filename,
            "stream": stream,
            "record_count": len(rows),
            "sha256": digest,
            "schema_id": f"federation_{'document_finding' if stream == 'document_findings' else 'federal_document'}.schema.json",
        })
    manifest = {
        "package_id": "pkg_" + "4" * 32,
        "producer": "centinelas-pr",
        "export_contract_version": "1.1.0",
        "mode": "test",
        "created_at": "2026-07-27T16:00:00Z",
        "federation": {"producer_repo": "centinelas-pr", "hub_parent": "thehub-pr"},
        "files": entries,
    }
    (package / "manifest.json").write_text(json.dumps(manifest))

    first = ingest(package, db)
    second = ingest(package, db)
    assert first["streams"]["federal_documents"]["inserted"] == 1
    assert first["streams"]["generated_candidates"]["inserted"] == 1
    assert second["streams"]["federal_documents"]["unchanged"] == 1
    assert second["streams"]["generated_candidates"]["unchanged"] == 1
