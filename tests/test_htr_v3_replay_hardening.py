from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_htr_v3_replay_hardening.py"
RECEIPT = ROOT / "data" / "htr" / "runs" / "2026-09-13_htr_v3_frozen_replay_hardening_receipt.json"


def run_receipt(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--receipt", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def write_mutation(tmp_path: Path, mutate) -> Path:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    mutate(doc)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_positive_receipt_passes() -> None:
    result = run_receipt(RECEIPT)
    assert result.returncode == 0, result.stderr
    assert '"certification": "PASS"' in result.stdout
    assert '"merge_authorized": false' in result.stdout


def test_negative_merge_authorization_fails(tmp_path: Path) -> None:
    path = write_mutation(tmp_path, lambda doc: doc["merge_governance"].update(merge_authorized=True))
    assert run_receipt(path).returncode != 0


def test_negative_matcher_symmetric_difference_fails(tmp_path: Path) -> None:
    path = write_mutation(tmp_path, lambda doc: doc["matcher_equivalence"].update(symmetric_difference=1))
    assert run_receipt(path).returncode != 0


def test_negative_pair_binding_promotion_fails(tmp_path: Path) -> None:
    path = write_mutation(tmp_path, lambda doc: doc["invariants"].update(pair_binding_promotion=1))
    assert run_receipt(path).returncode != 0


def test_negative_transitive_context_inheritance_fails(tmp_path: Path) -> None:
    path = write_mutation(tmp_path, lambda doc: doc["invariants"].update(transitive_context_inheritance=1))
    assert run_receipt(path).returncode != 0


def test_negative_identity_promotion_fails(tmp_path: Path) -> None:
    def mutate(doc: dict) -> None:
        doc["invariants"]["name_identity_promotion"] = 1
    path = write_mutation(tmp_path, mutate)
    assert run_receipt(path).returncode != 0


def test_negative_candidate_arithmetic_fails(tmp_path: Path) -> None:
    path = write_mutation(tmp_path, lambda doc: doc["incremental_recurrence"].update(candidate_rows=3734))
    assert run_receipt(path).returncode != 0


def test_negative_pair_group_arithmetic_fails(tmp_path: Path) -> None:
    path = write_mutation(tmp_path, lambda doc: doc["incremental_recurrence"].update(unresolved_groups=865))
    assert run_receipt(path).returncode != 0


def test_negative_v2_relation_conservation_fails(tmp_path: Path) -> None:
    path = write_mutation(tmp_path, lambda doc: doc["v2_pair_binding_continuation"].update(source_row_relations_conserved=1737))
    assert run_receipt(path).returncode != 0


def test_negative_context_partition_fails(tmp_path: Path) -> None:
    path = write_mutation(tmp_path, lambda doc: doc["v2_pair_binding_continuation"].update(fuzzy_only_additional_groups=29))
    assert run_receipt(path).returncode != 0


def test_negative_open_residue_cannot_be_promoted(tmp_path: Path) -> None:
    def mutate(doc: dict) -> None:
        doc["open_required_residue"]["direct_documentary_pair_binding"] = "PASS"
    path = write_mutation(tmp_path, mutate)
    assert run_receipt(path).returncode != 0


def test_negative_frozen_hash_drift_fails(tmp_path: Path) -> None:
    def mutate(doc: dict) -> None:
        doc["frozen_inputs"]["tiger_roads_zip"] = "0" * 64
    path = write_mutation(tmp_path, mutate)
    assert run_receipt(path).returncode != 0
