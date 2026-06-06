"""Shared test fixtures: a programmatically-built valid export package.

Building the package at test time (rather than committing JSONL + a hand-computed
sha256) keeps the fixture honest — the manifest's sha256/record_count always match
the bytes on disk, exercising the real integrity checks.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

SRC = "src_0123456789abcdef0123456789abcdef"
ENT_AGENCY = "ent_0123456789abcdef0123456789abce01"
ENT_RECIPIENT = "ent_0123456789abcdef0123456789abce02"
REL = "rel_0123456789abcdef0123456789abcdef"

LINEAGE = {
    "producer_script": "scripts/build_export.py",
    "producer_phase": "TEST_FIXTURE",
    "source_inputs": ["data/in.csv"],
    "extraction_method": "deterministic",
}
_TS = "2026-01-01T00:00:00Z"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows) -> int:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    return len(rows)


def build_package(directory: Path, producer: str = "moneysweep-pr") -> Path:
    directory.mkdir(parents=True, exist_ok=True)

    sources = [{
        "source_id": SRC, "source_type": "federal_grants", "source_name": "USASpending",
        "source_ref": "usaspending_prime", "confidence": 1.0, "lineage": LINEAGE,
        "synthetic": True, "created_at": _TS, "extracted_at": _TS,
    }]
    entities = [
        {
            "entity_id": ENT_AGENCY, "source_id": SRC, "name": "FEMA",
            "normalized_name": "FEDERAL EMERGENCY MANAGEMENT AGENCY",
            "entity_type": "funding_agency", "jurisdiction": "US",
            "external_ids": {"uei": "FEMA00000US1"}, "confidence": 0.98,
            "lineage": LINEAGE, "synthetic": True, "created_at": _TS, "extracted_at": _TS,
        },
        {
            "entity_id": ENT_RECIPIENT, "source_id": SRC, "name": "Acme Recovery LLC",
            "normalized_name": "ACME RECOVERY LLC", "entity_type": "recipient",
            "jurisdiction": "PR", "confidence": 0.91, "lineage": LINEAGE,
            "synthetic": True, "created_at": _TS, "extracted_at": _TS,
        },
    ]
    relationships = [{
        "relationship_id": REL, "source_id": SRC, "source_entity_id": ENT_RECIPIENT,
        "target_entity_id": ENT_AGENCY, "relationship_type": "received_award_from",
        "evidence_source_id": SRC, "confidence": 0.93, "lineage": LINEAGE,
        "synthetic": True, "created_at": _TS, "extracted_at": _TS,
    }]

    n_src = _write_jsonl(directory / "sources.jsonl", sources)
    n_ent = _write_jsonl(directory / "entities.jsonl", entities)
    n_rel = _write_jsonl(directory / "relationships.jsonl", relationships)

    manifest = {
        "package_id": "pkg_0123456789abcdef0123456789abcdef",
        "producer": producer,
        "export_contract_version": "1.2.0",
        "mode": "test",
        "created_at": _TS,
        "extracted_at": _TS,
        "federation": {"producer_repo": producer, "hub_parent": "thehub-pr"},
        "files": [
            {"filename": "sources.jsonl", "stream": "sources", "record_count": n_src,
             "sha256": _sha256(directory / "sources.jsonl"), "schema_id": "federation_source.schema.json"},
            {"filename": "entities.jsonl", "stream": "entities", "record_count": n_ent,
             "sha256": _sha256(directory / "entities.jsonl"), "schema_id": "federation_entity.schema.json"},
            {"filename": "relationships.jsonl", "stream": "relationships", "record_count": n_rel,
             "sha256": _sha256(directory / "relationships.jsonl"), "schema_id": "federation_relationship.schema.json"},
        ],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return directory


@pytest.fixture
def valid_package(tmp_path):
    return build_package(tmp_path / "pkg")


@pytest.fixture
def package_factory():
    """Return the build_package callable so tests can mint extra packages
    (e.g. a second producer) without importing across test modules."""
    return build_package


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"
