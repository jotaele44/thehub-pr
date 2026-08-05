from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema


def test_ontology_static_validation() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "tools/ontology/validate_canon.py", "--root", "."], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout); assert report["valid"] is True; assert report["module_count"] == 7; assert report["repository_pin_count"] == 7


def test_term_and_competency_schemas_validate_examples() -> None:
    root = Path(__file__).resolve().parents[1]
    term_schema = json.loads((root / "federation/ontology/schemas/term-record.schema.json").read_text(encoding="utf-8"))
    term = {"id": "prii:Example", "preferred_label": "Example", "definition": "A sufficiently precise example concept used for schema validation.", "scope": "federation", "layer": "evidence", "owner": "thehub-pr", "status": "proposed", "evidence": [{"repository": "jotaele44/thehub-pr", "commit": "a" * 40, "path": "example.json", "symbol_or_pointer": "Example", "tier": "T1"}], "examples": ["one"], "non_examples": ["none"], "competency_questions": ["CQ-001"]}
    jsonschema.validate(term, term_schema)
    cq_schema = json.loads((root / "federation/ontology/schemas/competency-question.schema.json").read_text(encoding="utf-8"))
    for path in (root / "federation/ontology/competency").glob("CQ-*.json"): jsonschema.validate(json.loads(path.read_text(encoding="utf-8")), cq_schema)


def test_manifest_has_no_drift() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "tools/ontology/generate_canon.py", "--root", ".", "--check"], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
