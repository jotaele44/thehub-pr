from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "registry" / "development_vectors.yaml"
SCHEMA = ROOT / "schemas" / "development_vector.schema.json"


def test_development_vector_ledger_matches_schema():
    ledger = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(ledger)


def test_snapshot_repository_ids_and_shas_are_unique():
    ledger = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    rows = ledger["snapshot"]["repositories"]
    assert len(rows) == 7
    assert len({row["repo_id"] for row in rows}) == 7
    assert len({row["repo"] for row in rows}) == 7
    assert len({(row["repo"], row["expected_sha"]) for row in rows}) == 7


def test_vector_ids_are_unique_and_dependencies_are_declared():
    ledger = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    vectors = ledger["vectors"]
    ids = [row["vector_id"] for row in vectors]
    assert len(ids) == len(set(ids))
    declared = set(ids)
    for vector in vectors:
        assert set(vector["dependencies"]) <= declared
