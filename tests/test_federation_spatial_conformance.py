from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/federation_spatial_conformance.py"

spec = importlib.util.spec_from_file_location("federation_spatial_conformance", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_canonical_matrix_passes_specification_conformance() -> None:
    matrix = module.load_matrix(module.DEFAULT_MATRIX)
    assert module.validate(matrix) == []


def test_missing_repository_fails_closed() -> None:
    matrix = module.load_matrix(module.DEFAULT_MATRIX)
    matrix["roles"] = dict(matrix["roles"])
    matrix["roles"].pop("ovnis-pr")
    errors = module.validate(matrix)
    assert any("repository denominator mismatch" in error for error in errors)


def test_na_is_not_reinterpreted_as_failure_class() -> None:
    matrix = module.load_matrix(module.DEFAULT_MATRIX)
    assert "N/A is not LOW and is not FAIL" in matrix["shared_invariants"]
    assert "N/A" in module.ALLOWED_CLASSES


def test_identity_default_fails_closed() -> None:
    matrix = module.load_matrix(module.DEFAULT_MATRIX)
    matrix["identity_default"] = "IDENTITY_BINDING"
    errors = module.validate(matrix)
    assert "identity_default must fail closed" in errors


def test_required_and_not_required_cannot_overlap() -> None:
    matrix = module.load_matrix(module.DEFAULT_MATRIX)
    role = matrix["roles"]["skywatcher-pr"]
    role["not_required"] = list(role["not_required"]) + [role["required_capabilities"][0]]
    errors = module.validate(matrix)
    assert any("both required and not_required" in error for error in errors)


def test_fixture_denominator_cannot_silently_shrink_below_five() -> None:
    matrix = module.load_matrix(module.DEFAULT_MATRIX)
    matrix["fixture_denominator"]["centinelas-pr"] = ["a", "b", "c", "d"]
    errors = module.validate(matrix)
    assert any("at least five cases" in error for error in errors)
