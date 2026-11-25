"""The GUI capability schemas agree with the checker and with real manifests.

The schemas describe shape; scripts/check_gui_parity.py enforces meaning. They
are separate artifacts (the checker is dependency-free and rendered into every
repository), so these tests keep them from drifting apart.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
referencing = pytest.importorskip("referencing")

_ROOT = Path(__file__).resolve().parents[1]
_CONTRACTS = _ROOT / "federation-audit" / "contracts"
_MANIFEST_SCHEMA = json.loads((_CONTRACTS / "gui-capabilities.schema.json").read_text())
_FRAGMENT_SCHEMA = json.loads(
    (_CONTRACTS / "gui-capabilities-fragment.schema.json").read_text()
)
_CORE = json.loads(
    (_ROOT / "federation-templates" / "gui" / "core-capabilities.json").read_text()
)

_SPEC = importlib.util.spec_from_file_location(
    "check_gui_parity", _ROOT / "scripts" / "check_gui_parity.py"
)
assert _SPEC and _SPEC.loader
parity = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(parity)

_SIBLINGS = [
    "aguayluz-pr",
    "centinelas-pr",
    "moneysweep-pr",
    "ovnis-pr",
    "skywatcher-pr",
    "spiderweb-pr",
]


def _validator(schema: dict) -> "jsonschema.Draft202012Validator":
    resource = referencing.Resource.from_contents(_MANIFEST_SCHEMA)
    registry = referencing.Registry().with_resource(_MANIFEST_SCHEMA["$id"], resource)
    return jsonschema.Draft202012Validator(schema, registry=registry)


def _errors(schema: dict, instance: dict) -> list[str]:
    return sorted(error.message for error in _validator(schema).iter_errors(instance))


def _capability(**overrides: object) -> dict:
    return {
        "id": "example",
        "classification": "internal",
        "status": "active",
        "requires_terminal": False,
        "rationale": "infrastructure",
        **overrides,
    }


def test_schemas_are_themselves_valid():
    jsonschema.Draft202012Validator.check_schema(_MANIFEST_SCHEMA)
    jsonschema.Draft202012Validator.check_schema(_FRAGMENT_SCHEMA)


def test_hub_manifest_conforms():
    manifest = json.loads((_ROOT / ".federation" / "gui-capabilities.json").read_text())
    assert _errors(_MANIFEST_SCHEMA, manifest) == []


@pytest.mark.parametrize("repo", _SIBLINGS)
def test_sibling_manifest_conforms_when_checked_out(repo):
    """Every producer's committed manifest already fits the schema.

    Skipped where the sibling is not checked out (CI) or has not adopted the
    manifest yet, so this proves the schema describes reality without making
    the hub's tests depend on the workspace layout.
    """
    path = _ROOT.parent / repo / ".federation" / "gui-capabilities.json"
    if not path.is_file():
        pytest.skip(f"{repo} has no manifest in this workspace")
    assert _errors(_MANIFEST_SCHEMA, json.loads(path.read_text())) == []


def test_schema_enums_match_the_checker():
    capability = _MANIFEST_SCHEMA["$defs"]["capability"]["properties"]
    assert set(capability["classification"]["enum"]) == parity.CLASSIFICATIONS
    assert set(capability["status"]["enum"]) == parity.STATUSES
    assert (
        _MANIFEST_SCHEMA["properties"]["schema_version"]["const"]
        == parity.MANIFEST_SCHEMA
    )
    assert set(_FRAGMENT_SCHEMA["properties"]) == parity.FRAGMENT_KEYS


def test_core_capability_table_matches_the_checker():
    declared = {item["id"]: item["classification"] for item in _CORE["capabilities"]}
    assert declared == parity.CORE_CAPABILITIES


def test_fragment_may_only_append():
    good = {"extension_id": "extra", "capabilities": [_capability()]}
    assert _errors(_FRAGMENT_SCHEMA, good) == []
    for forbidden in ("discovery", "policy", "repository"):
        assert _errors(_FRAGMENT_SCHEMA, {**good, forbidden: {}}), forbidden
    assert _errors(_FRAGMENT_SCHEMA, {"capabilities": [_capability()]})
    assert _errors(_FRAGMENT_SCHEMA, {"extension_id": "empty"})


def test_staged_and_internal_capabilities_carry_their_obligations():
    base = {
        "schema_version": parity.MANIFEST_SCHEMA,
        "repository": "example/repo",
        "discovery": {},
        "exceptions": [],
    }
    staged = _capability(classification="user", status="staged")
    assert _errors(_MANIFEST_SCHEMA, {**base, "capabilities": [staged]})
    staged.update(feature_flag="f", tracking="T-1", expires_on="2027-01-01")
    assert _errors(_MANIFEST_SCHEMA, {**base, "capabilities": [staged]}) == []

    internal = _capability()
    del internal["rationale"]
    assert _errors(_MANIFEST_SCHEMA, {**base, "capabilities": [internal]})


def test_exception_must_name_what_it_covers():
    base = {
        "schema_version": parity.MANIFEST_SCHEMA,
        "repository": "example/repo",
        "discovery": {},
        "capabilities": [],
    }
    exception = {
        "id": "gap",
        "reason": "r",
        "owner": "o",
        "tracking": "T-1",
        "expires_on": "2027-01-01",
    }
    assert _errors(_MANIFEST_SCHEMA, {**base, "exceptions": [exception]})
    assert (
        _errors(
            _MANIFEST_SCHEMA,
            {**base, "exceptions": [{**exception, "candidate_files": ["a.py"]}]},
        )
        == []
    )
