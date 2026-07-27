from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime
from typing import Any, Iterable

STREAM_COLLECTIONS = {
    "federal_documents": "FederalDocuments",
    "federal_document_releases": "FederalDocumentReleases",
    "document_findings": "DocumentFindings",
    "case_activity_candidates": "CaseActivityCandidates",
    "case_activity_assessments": "CaseActivityAssessments",
}
ID_FIELDS = {
    "federal_documents": "document_id",
    "federal_document_releases": "release_id",
    "document_findings": "finding_id",
    "case_activity_candidates": "candidate_id",
    "case_activity_assessments": "assessment_id",
}


def project_stream(conn: sqlite3.Connection, stream: str, rows: Iterable[dict[str, Any]], now: str) -> dict[str, int]:
    if stream not in STREAM_COLLECTIONS:
        raise ValueError(f"unsupported federal-record stream: {stream}")
    collection = STREAM_COLLECTIONS[stream]
    id_field = ID_FIELDS[stream]
    inserted = updated = unchanged = 0
    for row in rows:
        entity_id = str(row[id_field])
        canonical = json.dumps(row, sort_keys=True, separators=(",", ":"))
        current = conn.execute(
            "SELECT data FROM entities WHERE entity_type=? AND entity_id=?",
            (collection, entity_id),
        ).fetchone()
        if current is None:
            conn.execute(
                "INSERT INTO entities (entity_type, entity_id, data, updated_at) VALUES (?,?,?,?)",
                (collection, entity_id, canonical, now),
            )
            inserted += 1
        elif current[0] == canonical:
            unchanged += 1
        else:
            conn.execute(
                "UPDATE entities SET data=?, updated_at=? WHERE entity_type=? AND entity_id=?",
                (canonical, now, collection, entity_id),
            )
            updated += 1
    conn.commit()
    return {"inserted": inserted, "updated": updated, "unchanged": unchanged}


def _parse_day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def _candidate_id(case_id: str, document_id: str, finding_id: str) -> str:
    raw = f"{case_id}\0{document_id}\0{finding_id}".encode()
    return "cand_" + hashlib.sha256(raw).hexdigest()[:32]


def correlate_case(case: dict[str, Any], finding: dict[str, Any], document: dict[str, Any]) -> dict[str, Any] | None:
    basis: list[str] = []
    score = 0.0
    case_id = str(case.get("id") or case.get("case_id") or "")
    text = json.dumps(finding, sort_keys=True).lower()
    if case_id and case_id.lower() in text:
        basis.append("DIRECT_CASE_IDENTIFIER")
        score += 0.65

    case_municipality = str(case.get("municipality") or "").strip().lower()
    municipalities = {str(v).strip().lower() for v in finding.get("municipalities", [])}
    if case_municipality and case_municipality in municipalities:
        basis.append("MUNICIPALITY_MATCH")
        score += 0.2

    case_facilities = {str(v).strip().lower() for v in case.get("facilities", [])}
    finding_facilities = {str(v).strip().lower() for v in finding.get("facilities", [])}
    shared_facilities = sorted(case_facilities & finding_facilities)
    if shared_facilities:
        basis.append("FACILITY_MATCH")
        score += 0.25

    case_day = _parse_day(case.get("event_date") or case.get("date"))
    start_day = _parse_day(document.get("document_date_start"))
    temporal_distance: int | None = None
    if case_day and start_day:
        temporal_distance = abs((case_day - start_day).days) * 86400
        if temporal_distance <= 86400:
            basis.append("TEMPORAL_OVERLAP")
            score += 0.25
        elif temporal_distance <= 31 * 86400:
            basis.append("BACKGROUND_ASSOCIATION")
            score += 0.05

    if not basis or score < 0.2:
        return None
    finding_id = str(finding["finding_id"])
    document_id = str(document["document_id"])
    return {
        "candidate_id": _candidate_id(case_id, document_id, finding_id),
        "case_entity_id": str(case.get("entity_id") or case.get("id")),
        "document_id": document_id,
        "finding_id": finding_id,
        "candidate_basis": sorted(set(basis)),
        "temporal_distance_seconds": temporal_distance,
        "spatial_distance_km": None,
        "shared_facilities": shared_facilities,
        "shared_entities": [],
        "candidate_score": min(score, 1.0),
        "generated_by": "thehub-pr",
        "requires_human_review": True,
        "lineage": {
            "producer_script": "server/backend/federal_records.py",
            "producer_phase": "PHASE_2_CORRELATION",
            "source_inputs": [case_id, finding_id, document_id],
        },
        "synthetic": bool(case.get("synthetic") or finding.get("synthetic")),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "extracted_at": datetime.utcnow().isoformat() + "Z",
    }


def generate_candidates(
    conn: sqlite3.Connection,
    cases: Iterable[dict[str, Any]],
    findings: Iterable[dict[str, Any]],
    documents: Iterable[dict[str, Any]],
    now: str,
) -> dict[str, int]:
    docs = {str(row["document_id"]): row for row in documents}
    candidates: list[dict[str, Any]] = []
    for case in cases:
        for finding in findings:
            document = docs.get(str(finding.get("document_id")))
            if document is None:
                continue
            candidate = correlate_case(case, finding, document)
            if candidate is not None:
                candidates.append(candidate)
    return project_stream(conn, "case_activity_candidates", candidates, now)


def assessment_surfaces(assessments: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    rows = list(assessments)
    return {
        "contradictions": [r for r in rows if r.get("classification") == "CONTRADICTORY" or r.get("contradicts_case_claim")],
        "data_gaps": [r for r in rows if r.get("classification") == "DATA_GAP"],
        "no_known_match": [r for r in rows if r.get("classification") == "NO_KNOWN_MATCH"],
    }
