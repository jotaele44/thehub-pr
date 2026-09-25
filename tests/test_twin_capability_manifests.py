"""Tests for the Twin observed / Federation-derived capability manifests.

Positive: the committed manifests validate, the observed census closes at
223 and the reconciliation blocks match their rows. Negative: every rule in
hub.twin_manifest rejects the malformed manifest it exists to catch.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from hub import twin_manifest as tm

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "validate_twin_manifests", REPO_ROOT / "scripts" / "validate_twin_manifests.py"
)
vtm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vtm)


def _load(rel: Path) -> dict:
    return json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def observed() -> dict:
    return _load(tm.OBSERVED_RELPATH)


@pytest.fixture(scope="module")
def derived() -> dict:
    return _load(tm.DERIVED_RELPATH)


@pytest.fixture(scope="module")
def observed_schema() -> dict:
    return _load(tm.OBSERVED_SCHEMA_RELPATH)


@pytest.fixture(scope="module")
def derived_schema() -> dict:
    return _load(tm.DERIVED_SCHEMA_RELPATH)


def _elements(doc: dict) -> list:
    return [r["element"] for r in doc["capabilities"]]


# ── positive ──────────────────────────────────────────────────────────────────


def test_committed_manifests_validate():
    assert tm.check_repo(REPO_ROOT) == []


def test_observed_census_closes_at_223(observed):
    rec = tm.reconcile_observed(observed)
    assert rec["OBSERVED_TOTAL"] == 223
    assert rec["ACCOUNTED_FOR"] == 223
    assert rec["UNACCOUNTED"] == 0
    assert rec["census_closed"] is True
    assert observed["reconciliation"] == rec


def test_every_observed_row_has_one_in_scope_owner(observed):
    for row in observed["capabilities"]:
        assert row["canonical_repo"] in tm.IN_SCOPE_REPOS
        assert row["producer"] == row["canonical_repo"]
        assert "centinelas" not in json.dumps(row["consumers"])


def test_every_derived_row_is_federation_derived(derived):
    assert derived["capabilities"], "derived manifest must not be empty"
    assert {r["origin"] for r in derived["capabilities"]} == {"FEDERATION_DERIVED"}
    assert derived["reconciliation"] == tm.reconcile_derived(derived)


def test_bundle_only_modules_are_not_counted(observed):
    for module in observed["unrecorded_bundle_modules"]:
        assert module["counted_in_denominator"] is False
        assert module["evidence_status"] == "NOT_OBSERVED"


def test_cli_passes_on_committed_repo(capsys):
    assert vtm.main(["--root", str(REPO_ROOT)]) == 0
    assert "twin manifests OK" in capsys.readouterr().out


# ── negative: observed ────────────────────────────────────────────────────────


def test_222_rows_fail(observed, observed_schema):
    doc = copy.deepcopy(observed)
    doc["capabilities"].pop()
    errors = tm.validate_observed(doc, observed_schema)
    assert any("expected 223 rows" in e for e in errors)
    assert tm.reconcile_observed(doc)["census_closed"] is False


def test_duplicate_capability_id_fails(observed):
    doc = copy.deepcopy(observed)
    doc["capabilities"][1]["capability_id"] = doc["capabilities"][0]["capability_id"]
    errors = tm.validate_observed(doc)
    assert any("duplicate capability_id" in e for e in errors)


def test_non_contiguous_census_numbers_fail(observed):
    doc = copy.deepcopy(observed)
    doc["capabilities"][5]["census_number"] = 99
    assert any("contiguously" in e for e in tm.validate_observed(doc))


def test_out_of_scope_owner_fails(observed, observed_schema):
    doc = copy.deepcopy(observed)
    doc["capabilities"][0]["canonical_repo"] = "centinelas-pr"
    doc["capabilities"][0]["producer"] = "centinelas-pr"
    errors = tm.validate_observed(doc, observed_schema)
    assert any("not an in-scope Federation repo" in e for e in errors)


def test_split_ownership_fails(observed):
    doc = copy.deepcopy(observed)
    doc["capabilities"][0]["producer"] = "ovnis-pr"
    assert any("exactly one canonical owner" in e for e in tm.validate_observed(doc))


def test_not_applicable_without_rationale_fails(observed):
    doc = copy.deepcopy(observed)
    row = next(r for r in doc["capabilities"] if r["implementation_status"] == "NOT_APPLICABLE")
    row.pop("rationale")
    assert any("requires a rationale" in e for e in tm.validate_observed(doc))


def test_blocked_without_blocker_fails(observed):
    doc = copy.deepcopy(observed)
    row = next(r for r in doc["capabilities"] if r["implementation_status"] == "BLOCKED")
    row.pop("blocker")
    assert any("requires a blocker" in e for e in tm.validate_observed(doc))


def test_extend_without_equivalent_fails(observed):
    doc = copy.deepcopy(observed)
    row = next(r for r in doc["capabilities"] if r["implementation_status"] == "EXTEND")
    row["existing_equivalent"] = None
    assert any("requires an existing_equivalent" in e for e in tm.validate_observed(doc))


def test_new_without_search_terms_fails(observed):
    doc = copy.deepcopy(observed)
    row = next(r for r in doc["capabilities"] if r["implementation_status"] == "NEW")
    row.pop("search_terms_without_equivalent")
    assert any("search_terms_without_equivalent" in e for e in tm.validate_observed(doc))


def test_not_observed_row_cannot_enter_denominator(observed, observed_schema):
    doc = copy.deepcopy(observed)
    doc["capabilities"][0]["evidence_status"] = "NOT_OBSERVED"
    errors = tm.validate_observed(doc, observed_schema)
    assert any("cannot be counted as observed" in e for e in errors)


def test_inconsistent_delivery_state_fails(observed):
    doc = copy.deepcopy(observed)
    row = next(r for r in doc["capabilities"] if r["implementation_status"] == "EXISTING")
    row["delivery_state"] = "DEFERRED"
    assert any("inconsistent with implementation_status" in e for e in tm.validate_observed(doc))


def test_run1_claim_outside_run1_phase_fails(observed):
    doc = copy.deepcopy(observed)
    row = next(r for r in doc["capabilities"] if r["delivery_state"] == "DEFERRED")
    row["delivery_state"] = "SCHEDULED_THIS_RUN"
    assert any("claims run-1 work" in e for e in tm.validate_observed(doc))


def test_implemented_without_tests_fails(observed):
    doc = copy.deepcopy(observed)
    row = next(r for r in doc["capabilities"] if r["delivery_state"] == "SCHEDULED_THIS_RUN")
    row["delivery_state"] = "IMPLEMENTED_THIS_RUN"
    row["tests"] = []
    assert any("requires tests" in e for e in tm.validate_observed(doc))


def test_counted_bundle_module_fails(observed):
    doc = copy.deepcopy(observed)
    doc["unrecorded_bundle_modules"][0]["counted_in_denominator"] = True
    assert any("must stay NOT_OBSERVED" in e for e in tm.validate_observed(doc))


def test_non_list_capabilities_fail():
    assert tm.validate_observed({"capabilities": {}}) == ["observed: capabilities must be a list"]
    assert tm.validate_derived({"capabilities": None}) == ["derived: capabilities must be a list"]


# ── negative: derived ─────────────────────────────────────────────────────────


def test_derived_without_origin_fails(derived, derived_schema, observed):
    doc = copy.deepcopy(derived)
    doc["capabilities"][0]["origin"] = "TWIN"
    errors = tm.validate_derived(doc, _elements(observed), derived_schema)
    assert any("origin must be FEDERATION_DERIVED" in e for e in errors)


def test_derived_entry_duplicating_observed_element_fails(derived, observed):
    doc = copy.deepcopy(derived)
    doc["capabilities"][0]["name"] = observed["capabilities"][11]["element"]  # "Search"
    errors = tm.validate_derived(doc, _elements(observed))
    assert any("duplicates an observed Twin element" in e for e in errors)


def test_derived_alias_collision_fails(derived):
    doc = copy.deepcopy(derived)
    doc["capabilities"][1]["aliases"] = [doc["capabilities"][0]["name"]]
    assert any("appears 2 times" in e for e in tm.validate_derived(doc))


def test_derived_non_contiguous_ids_fail(derived):
    doc = copy.deepcopy(derived)
    doc["capabilities"][2]["capability_id"] = "FDX-999"
    assert any("contiguous" in e for e in tm.validate_derived(doc))


def test_derived_blocked_without_blocker_fails(derived):
    doc = copy.deepcopy(derived)
    row = next(r for r in doc["capabilities"] if r["implementation_status"] == "BLOCKED")
    row.pop("blocker")
    assert any("requires a blocker" in e for e in tm.validate_derived(doc))


# ── reconciliation plumbing ───────────────────────────────────────────────────


def _copy_repo(tmp_path: Path) -> Path:
    for rel in (tm.OBSERVED_RELPATH, tm.DERIVED_RELPATH, tm.OBSERVED_SCHEMA_RELPATH, tm.DERIVED_SCHEMA_RELPATH):
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / rel, dest)
    return tmp_path


def test_stale_reconciliation_is_reported_and_write_repairs_it(tmp_path, capsys):
    root = _copy_repo(tmp_path)
    path = root / tm.OBSERVED_RELPATH
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["reconciliation"]["NEW"] = -1
    path.write_text(json.dumps(doc), encoding="utf-8")

    assert any("reconciliation block is stale" in e for e in tm.check_repo(root))
    assert vtm.main(["--root", str(root)]) == 1
    assert "stale" in capsys.readouterr().err

    assert tm.check_repo(root, write=True) == []
    assert tm.check_repo(root) == []


def test_open_census_is_reported(tmp_path):
    root = _copy_repo(tmp_path)
    path = root / tm.OBSERVED_RELPATH
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["capabilities"].pop()
    path.write_text(json.dumps(doc), encoding="utf-8")
    errors = tm.check_repo(root, write=True)
    assert any("census is not closed" in e for e in errors)


def test_non_object_manifest_is_rejected(tmp_path):
    root = _copy_repo(tmp_path)
    (root / tm.DERIVED_RELPATH).write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        tm.check_repo(root)


def test_non_object_rows_and_mismatched_ids_fail(observed, derived):
    doc = copy.deepcopy(observed)
    doc["capabilities"][3]["capability_id"] = "TWIN-900"
    doc["capabilities"][4]["reference"] = "FEDERATION_DERIVED"
    doc["capabilities"].append("not-a-row")
    errors = tm.validate_observed(doc)
    assert any("does not match census_number" in e for e in errors)
    assert any("reference must be TWIN" in e for e in errors)
    assert "observed: every capability must be an object" in errors

    ddoc = copy.deepcopy(derived)
    ddoc["capabilities"].append(7)
    assert "derived: every capability must be an object" in tm.validate_derived(ddoc)
