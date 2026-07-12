"""The committed PRII skill packet passes the shared validator.

Master gate: run scripts/validate_skills.py over the real repo and assert zero
errors across all ten checks. Uses the subprocess form (mirroring
tests/test_mcp_candidates.py) so it is robust to sys.path — the validator is a
standalone CLI and the main pytest job collects this test without scripts/ being
importable."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

TEN_CHECKS = {
    "skill-structure",
    "skill-registry",
    "command-resolution",
    "path-resolution",
    "boundary-policy",
    "mode-safety",
    "coverage-accounting",
    "export-contract",
    "activation",
    "drift",
}


def _run_validator():
    result = subprocess.run(
        [sys.executable, "scripts/validate_skills.py", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_committed_packet_passes_every_check():
    result = _run_validator()
    assert result["ok"] is True, f"skill packet validation failed: {result['errors']}"


def test_all_ten_checks_ran():
    result = _run_validator()
    assert set(result["errors"]) == TEN_CHECKS


def test_activation_check_requires_a_matrix(tmp_path):
    # The activation matrix is the routing-coverage artifact; a missing or empty
    # matrix must fail the check, not silently pass. Run the validator against a
    # temp root carrying the registry but no matrix.
    (tmp_path / "skill-registry.yaml").write_text(
        (REPO_ROOT / "skill-registry.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_skills.py",
            "--root",
            str(tmp_path),
            "--check",
            "activation",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is False and data["errors"]["activation"]


def test_registry_validates_against_declared_schema():
    # The registry declares a schema; it must actually conform to it, including
    # the top-level packet_config block (the pure-Python validator does not
    # enforce the schema's additionalProperties, so a jsonschema consumer would).
    jsonschema = pytest.importorskip("jsonschema")
    schema_path = REPO_ROOT / "schemas" / "skills" / "prii_skill_contract.schema.json"
    schema = json.loads(schema_path.read_text())
    registry = yaml.safe_load((REPO_ROOT / "skill-registry.yaml").read_text())
    jsonschema.validate(registry, schema)
