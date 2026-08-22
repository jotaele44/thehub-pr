import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def _validate(schema_path: str, instance_path: str) -> None:
    schema = json.loads((ROOT / schema_path).read_text())
    instance = json.loads((ROOT / instance_path).read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def test_federation_manifest_matches_contract():
    _validate("contracts/repository-audit-manifest.schema.json", "manifests/federation.json")
    manifest = json.loads((ROOT / "manifests/federation.json").read_text())
    assert len(manifest["repositories"]) == 7
    assert len({r["commit"] for r in manifest["repositories"]}) == 7
    assert all(len(r["commit"]) == 40 for r in manifest["repositories"])


def test_runtime_certification_schema_is_valid():
    schema = json.loads((ROOT / "contracts/runtime-certification.schema.json").read_text())
    Draft202012Validator.check_schema(schema)


def test_controlled_fixture_evidence_matches_trace_contract():
    _validate("contracts/executability-trace.schema.json", "evidence/first-controlled-audit.json")


def test_repository_static_evidence_matches_trace_contract():
    _validate("contracts/executability-trace.schema.json", "evidence/thehub-ledger-export-static.json")


def test_initial_inventory_graph_matches_contract():
    _validate("contracts/federation-executability-graph.schema.json", "evidence/federation-initial-static-graph.json")
