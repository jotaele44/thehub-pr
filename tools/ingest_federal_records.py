#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator

from server.backend.federal_records import generate_candidates, project_stream

REPO_ROOT = Path(__file__).parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
SCHEMA_BY_STREAM = {
    "federal_documents": "federation_federal_document.schema.json",
    "federal_document_releases": "federation_federal_document_release.schema.json",
    "document_findings": "federation_document_finding.schema.json",
    "case_activity_candidates": "federation_case_activity_candidate.schema.json",
    "case_activity_assessments": "federation_case_activity_assessment.schema.json",
}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def validate_rows(stream: str, rows: list[dict]) -> None:
    schema = json.loads((SCHEMA_DIR / SCHEMA_BY_STREAM[stream]).read_text())
    validator = Draft7Validator(schema)
    errors = []
    for index, row in enumerate(rows, start=1):
        errors.extend(f"{stream}:{index}: {error.message}" for error in validator.iter_errors(row))
    if errors:
        raise ValueError("\n".join(errors))


def init_entities(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS entities ("
        "entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, data TEXT NOT NULL, "
        "updated_at TEXT NOT NULL, PRIMARY KEY(entity_type, entity_id))"
    )
    conn.commit()


def ingest(package: Path, db_path: Path) -> dict:
    manifest = json.loads((package / "manifest.json").read_text())
    streams: dict[str, list[dict]] = {}
    for entry in manifest["files"]:
        stream = entry["stream"]
        if stream not in SCHEMA_BY_STREAM:
            continue
        rows = load_jsonl(package / entry["filename"])
        if len(rows) != int(entry["record_count"]):
            raise ValueError(f"record count mismatch for {stream}")
        validate_rows(stream, rows)
        streams[stream] = rows

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    init_entities(conn)
    result: dict[str, dict[str, int]] = {}
    for stream, rows in streams.items():
        result[stream] = project_stream(conn, stream, rows, now)

    cases = [json.loads(row[0]) for row in conn.execute(
        "SELECT data FROM entities WHERE entity_type IN ('Cases','OVNISCases')"
    ).fetchall()]
    documents = streams.get("federal_documents", []) or [json.loads(row[0]) for row in conn.execute(
        "SELECT data FROM entities WHERE entity_type='FederalDocuments'"
    ).fetchall()]
    findings = streams.get("document_findings", []) or [json.loads(row[0]) for row in conn.execute(
        "SELECT data FROM entities WHERE entity_type='DocumentFindings'"
    ).fetchall()]
    if cases and documents and findings:
        result["generated_candidates"] = generate_candidates(conn, cases, findings, documents, now)
    conn.close()
    return {"package_id": manifest["package_id"], "streams": result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "data" / "hub.db")
    args = parser.parse_args()
    print(json.dumps(ingest(args.package, args.db), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
