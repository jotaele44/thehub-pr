from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from evidence_engine.producer_package_admission import (
    record_producer_package_admission,
)
from h07_support import valid_bundle

SCHEMA_DIR = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "contracts"
    / "skywatcher_ai"
)


def _schemas() -> dict[str, dict]:
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
    }


def _registry(schemas: dict[str, dict]) -> Registry:
    registry = Registry()
    for name, schema in schemas.items():
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(name, resource)
        registry = registry.with_resource(schema["$id"], resource)
    return registry


def test_h07_input_contracts_accept_valid_h06_bundle(tmp_path: Path) -> None:
    record, run, package, lineage, _ = valid_bundle(tmp_path)
    schemas = _schemas()
    registry = _registry(schemas)
    fixtures = {
        "bounded_producer_job_record.v1.schema.json": record,
        "producer_run_receipt.v1.schema.json": run,
        "producer_package_manifest.v1.schema.json": package,
        "producer_output_lineage.v1.schema.json": lineage,
    }
    for name, fixture in fixtures.items():
        validator = Draft202012Validator(
            schemas[name],
            registry=registry,
            format_checker=FormatChecker(),
        )
        assert list(validator.iter_errors(fixture)) == []


def test_h07_emitted_admission_receipt_matches_frozen_contract(
    tmp_path: Path,
) -> None:
    record, run, package, lineage, package_root = valid_bundle(tmp_path)
    receipt = record_producer_package_admission(
        tmp_path / "storage",
        "contract-admission",
        record,
        run,
        package,
        lineage,
        package_root,
        completed_at="2026-07-31T01:10:00Z",
        schema_dir=SCHEMA_DIR,
    )
    schemas = _schemas()
    validator = Draft202012Validator(
        schemas["producer_package_admission_receipt.v1.schema.json"],
        registry=_registry(schemas),
        format_checker=FormatChecker(),
    )
    assert list(validator.iter_errors(receipt)) == []


def test_h07_contracts_do_not_define_active_or_answer_surfaces() -> None:
    names = {
        "bounded_producer_job_record.v1.schema.json",
        "producer_run_receipt.v1.schema.json",
        "producer_package_manifest.v1.schema.json",
        "producer_output_lineage.v1.schema.json",
        "producer_package_admission_receipt.v1.schema.json",
    }
    schemas = _schemas()
    source = "\n".join(
        json.dumps(schemas[name], sort_keys=True)
        for name in sorted(names)
    )
    assert '"active_snapshot_promoted": {"const": true}' not in source
    assert '"answer_eligible": {"const": true}' not in source
    assert "acquisition_receipt.v1" not in source
