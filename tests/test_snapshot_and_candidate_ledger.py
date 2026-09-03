from __future__ import annotations

import json
from pathlib import Path

import pytest

from hub.bridge import write_manifest
from hub.correlation_ledger import candidate_ledger_rows, write_candidate_ledger
from hub.snapshot_runtime import build_snapshot_manifest

_TS = "2026-01-01T00:00:00Z"


def _entity(eid: str, *, synthetic: bool = False) -> dict:
    return {
        "entity_id": eid,
        "source_id": "src_" + "a" * 32,
        "name": "Example",
        "normalized_name": "EXAMPLE",
        "entity_type": "recipient",
        "jurisdiction": "PR",
        "confidence": 0.9,
        "lineage": {
            "producer_script": "test",
            "producer_phase": "TEST",
            "source_inputs": ["fixture"],
        },
        "synthetic": synthetic,
        "created_at": _TS,
        "extracted_at": _TS,
    }


def _package(tmp_path: Path, producer: str, eid: str) -> Path:
    pkg = tmp_path / producer
    pkg.mkdir()
    (pkg / "entities.jsonl").write_text(
        json.dumps(_entity(eid), sort_keys=True) + "\n", encoding="utf-8"
    )
    write_manifest(pkg, producer)
    return pkg


def _candidate() -> dict:
    return {
        "relationship_id": "rel_" + "1" * 32,
        "source_id": "src_" + "2" * 32,
        "source_entity_id": "ent_" + "3" * 32,
        "target_entity_id": "ent_" + "4" * 32,
        "relationship_type": "entity_correlation",
        "evidence_source_id": "src_" + "2" * 32,
        "confidence": 0.8,
        "match_basis": "normalized_name",
        "explanation": "candidate only",
        "lineage": {
            "producer_script": "src/hub/correlate.py",
            "producer_phase": "HUB_CORRELATE",
            "source_inputs": ["entities.jsonl"],
        },
        "synthetic": True,
        "created_at": "1970-01-01T00:00:00Z",
        "extracted_at": "1970-01-01T00:00:00Z",
        "identity_assertion": False,
        "identity_adjudication_state": "CANDIDATE",
        "identity_cardinality": "UNRESOLVED",
        "identity_evidence_class": "WEAK_CORRELATION",
    }


def test_candidate_ledger_is_frozen_contract_projection(tmp_path):
    row = _candidate()
    rows = candidate_ledger_rows([row])
    assert len(rows) == 1
    assert rows[0]["decision_type"] == "entity_match_candidate"
    assert rows[0]["candidate_entity_ids"] == sorted(
        [row["source_entity_id"], row["target_entity_id"]]
    )

    correlations = tmp_path / "correlations.jsonl"
    ledger = tmp_path / "entity_resolution_candidates.jsonl"
    correlations.write_text(json.dumps(row) + "\n", encoding="utf-8")
    summary = write_candidate_ledger(correlations, ledger)
    assert summary["candidate_count"] == 1
    assert ledger.read_text(encoding="utf-8").count("\n") == 1


def test_snapshot_id_is_content_deterministic_across_metadata_times(tmp_path):
    package = _package(tmp_path, "producer-a", "ent_" + "a" * 32)
    aggregate = tmp_path / "aggregate"
    aggregate.mkdir()
    (aggregate / "entities.jsonl").write_text(
        json.dumps(_entity("ent_" + "b" * 32), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    kwargs = {
        "packages": {"producer-a": package},
        "aggregate_dir": aggregate,
        "decided_by": "test",
        "decision": "PROMOTE",
    }
    first = build_snapshot_manifest(
        **kwargs, created_at="2026-01-01T00:00:00Z", decided_at="2026-01-01T00:00:01Z"
    )
    second = build_snapshot_manifest(
        **kwargs, created_at="2026-02-01T00:00:00Z", decided_at="2026-02-01T00:00:01Z"
    )
    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["sha256_manifest"] == second["sha256_manifest"]


def test_snapshot_id_changes_when_aggregate_bytes_change(tmp_path):
    package = _package(tmp_path, "producer-a", "ent_" + "a" * 32)
    aggregate = tmp_path / "aggregate"
    aggregate.mkdir()
    path = aggregate / "entities.jsonl"
    path.write_text(json.dumps(_entity("ent_" + "b" * 32)) + "\n", encoding="utf-8")
    first = build_snapshot_manifest(
        {"producer-a": package}, aggregate,
        created_at=_TS, decided_by="test", decided_at=_TS,
    )
    path.write_text(json.dumps(_entity("ent_" + "c" * 32)) + "\n", encoding="utf-8")
    second = build_snapshot_manifest(
        {"producer-a": package}, aggregate,
        created_at=_TS, decided_by="test", decided_at=_TS,
    )
    assert first["snapshot_id"] != second["snapshot_id"]


def test_snapshot_rejects_unaccounted_failed_records(tmp_path):
    package = _package(tmp_path, "producer-a", "ent_" + "a" * 32)
    aggregate = tmp_path / "aggregate"
    aggregate.mkdir()
    with pytest.raises(ValueError, match="unaccounted"):
        build_snapshot_manifest(
            {"producer-a": package}, aggregate,
            created_at=_TS, decided_by="test", decided_at=_TS,
            failed_record_count=1, exclusion_ledger=[],
        )


def test_operational_snapshot_rejects_synthetic_rows(tmp_path):
    package = _package(tmp_path, "producer-a", "ent_" + "a" * 32)
    aggregate = tmp_path / "aggregate"
    aggregate.mkdir()
    (aggregate / "entities.jsonl").write_text(
        json.dumps(_entity("ent_" + "b" * 32, synthetic=True)) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="synthetic"):
        build_snapshot_manifest(
            {"producer-a": package}, aggregate,
            created_at=_TS, decided_by="test", decided_at=_TS,
            operational=True,
        )
