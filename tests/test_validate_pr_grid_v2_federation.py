"""Shared-runtime parity rules of scripts/validate_pr_grid_v2_federation.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "validate_pr_grid_v2_federation",
    REPO_ROOT / "scripts" / "validate_pr_grid_v2_federation.py",
)
validator = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(validator)


def _workspace(tmp_path: Path) -> Path:
    for consumer in sorted(validator.EXPECTED_CONSUMERS - {"thehub-pr"}):
        for output_rel, template in validator.SHARED_CONSUMER_FILES.items():
            target = tmp_path / consumer / output_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(template.read_bytes())
    return tmp_path


def test_identical_consumers_pass_without_warnings(tmp_path):
    result = validator._validate_shared_consumer_runtime(_workspace(tmp_path))
    assert result["State"] == "SHARED_RUNTIME_PARITY_PASS"
    assert result["Warnings"] == []


def test_pending_adoption_files_warn_instead_of_failing(tmp_path):
    root = _workspace(tmp_path)
    (root / "aguayluz-pr/federation/spatial/pr_grid_v2_profiles.py").write_text("old\n")
    (root / "ovnis-pr/server/backend/grid_v2_api.py").unlink()
    result = validator._validate_shared_consumer_runtime(root)
    assert result["State"] == "SHARED_RUNTIME_PARITY_PASS_WITH_PENDING_ADOPTION"
    files = result["Files"]
    assert files["federation/spatial/pr_grid_v2_profiles.py"]["Pending_Adoption"] == {
        "aguayluz-pr": "DRIFT"
    }
    assert files["server/backend/grid_v2_api.py"]["Pending_Adoption"] == {"ovnis-pr": "MISSING"}
    assert files["federation/spatial/pr_grid_v2_runtime.py"]["State"] == "BYTE_IDENTICAL_PASS"
    assert len(result["Warnings"]) == 2


@pytest.mark.parametrize("mutation", ["drift", "missing"])
def test_runtime_file_stays_strict(tmp_path, mutation):
    root = _workspace(tmp_path)
    runtime = root / "skywatcher-pr/federation/spatial/pr_grid_v2_runtime.py"
    if mutation == "drift":
        runtime.write_text("drifted\n")
    else:
        runtime.unlink()
    with pytest.raises(validator.GridV2PinError):
        validator._validate_shared_consumer_runtime(root)


def test_pending_adoption_never_covers_the_runtime_contract():
    assert "federation/spatial/pr_grid_v2_runtime.py" not in validator.PENDING_ADOPTION_FILES
    assert validator.PENDING_ADOPTION_FILES <= set(validator.SHARED_CONSUMER_FILES)
