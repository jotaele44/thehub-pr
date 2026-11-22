"""Federation Experience Contract v1 (experience program, gate RC2).

The schemas and the validator live in ``federation-audit/experience-program``.
Every fixture under ``rc2/fixtures/negative`` is a small patch applied to a valid
contract together with the finding it must produce, so a rule that stops being
enforced fails here by name.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("jsonschema")

PROGRAM = Path(__file__).resolve().parents[1] / "federation-audit" / "experience-program"
FIXTURES = PROGRAM / "rc2" / "fixtures"
SCHEMAS = PROGRAM / "rc2" / "schemas"

_spec = importlib.util.spec_from_file_location("rc2_validate", PROGRAM / "scripts" / "rc2_validate.py")
rc2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc2)

NEGATIVE = sorted((FIXTURES / "negative").glob("*.json"))
POSITIVE = sorted((FIXTURES / "positive").glob("*.json"))


def _positive(name: str) -> dict:
    return json.loads((FIXTURES / "positive" / f"{name}.json").read_text(encoding="utf-8"))


def _resolve(document, path: str):
    """Parent container and final key for a JSON-pointer-like path."""
    parts = [part for part in path.split("/") if part != ""]
    node = document
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node, parts[-1]


def _apply(document, operation: dict) -> None:
    parent, key = _resolve(document, operation["path"])
    kind = operation["op"]
    if kind == "remove":
        if isinstance(parent, list):
            del parent[int(key)]
        else:
            del parent[key]
        return
    if kind == "copy":
        value = copy.deepcopy(parent[int(key)] if isinstance(parent, list) else parent[key])
        parent, key = _resolve(document, operation["to"])
    else:
        assert kind == "set", kind
        value = copy.deepcopy(operation["value"])
    if isinstance(parent, list):
        if key == "-":
            parent.append(value)
        else:
            parent[int(key)] = value
    else:
        parent[key] = value


def _build(fixture: dict) -> list:
    documents = [_positive(name) for name in fixture["base"]]
    for operation in fixture["patch"]:
        _apply(documents[operation.get("doc", 0)], operation)
    return documents


def test_there_are_five_well_formed_schemas():
    from jsonschema import Draft202012Validator

    names = sorted(path.name for path in SCHEMAS.glob("*.json"))
    assert names == sorted(rc2.SECTION_SCHEMAS.values())
    for path in SCHEMAS.glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        assert schema["$id"].endswith(path.name)


@pytest.mark.parametrize("path", POSITIVE, ids=lambda p: p.stem)
def test_positive_fixture_is_accepted_alone(path):
    assert rc2.validate([json.loads(path.read_text(encoding="utf-8"))]) == []


def test_positive_fixtures_coexist():
    """Two applications may restate one identical federation-global setting."""
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in POSITIVE]
    assert len(documents) >= 2
    assert rc2.validate(documents) == []


def test_negative_fixtures_cover_every_required_behaviour():
    names = {path.stem for path in NEGATIVE}
    required = {
        "unknown-top-level-field", "null-required-value", "duplicate-action-id",
        "duplicate-setting-id", "cross-app-setting-collision", "global-setting-redefined",
        "unsupported-contract-major", "context-menu-only", "rename-evidence-object",
        "app-setting-in-global-namespace", "secret-with-default", "write-as-guest",
    }
    assert required <= names, sorted(required - names)


@pytest.mark.parametrize("path", NEGATIVE, ids=lambda p: p.stem)
def test_negative_fixture_is_rejected_for_the_stated_reason(path):
    fixture = json.loads(path.read_text(encoding="utf-8"))
    assert fixture["description"] and fixture["expect"]
    # The unpatched base must be clean, so the patch is the only cause.
    base = [_positive(name) for name in dict.fromkeys(fixture["base"])]
    assert rc2.validate(base) == []
    codes = [finding.code for finding in rc2.validate(_build(fixture))]
    assert codes, f"{path.stem} was accepted"
    for expected in fixture["expect"]:
        assert expected in codes, f"{path.stem}: expected {expected}, got {sorted(set(codes))}"


def test_extension_fields_are_the_only_unknown_fields_allowed():
    document = _positive("mucaro-ai")
    document["x-team-note"] = {"anything": [1, None]}
    document["actions"][0]["x-reviewed"] = True
    assert rc2.validate([document]) == []
    document["X-Team-Note"] = 1  # wrong case is still unknown
    assert "schema:contract:additionalProperties" in [f.code for f in rc2.validate([document])]


def test_null_is_accepted_only_where_declared():
    document = _positive("mucaro-ai")
    assert document["actions"][0]["keyboard_binding"] is None  # declared nullable
    assert document["compatibility"]["desktop_runtime"] is None
    for pointer in ("/actions/0/title", "/settings/0/title", "/navigation/groups/0/label",
                    "/compatibility/contract_version", "/interaction/keyboard_complete"):
        broken = _positive("mucaro-ai")
        _apply(broken, {"op": "set", "path": pointer, "value": None})
        assert any(f.code.endswith(":type") for f in rc2.validate([broken])), pointer


def test_serialization_is_deterministic_and_order_independent_for_keys():
    document = _positive("mucaro-ai")
    shuffled = json.loads(json.dumps(document), object_pairs_hook=lambda pairs: dict(reversed(pairs)))
    assert list(shuffled) != list(document)
    assert rc2.canonical(shuffled) == rc2.canonical(document)
    assert rc2.digest(shuffled) == rc2.digest(document)
    assert rc2.canonical(json.loads(rc2.canonical(document))) == rc2.canonical(document)
    assert "\n" not in rc2.canonical(document) and ": " not in rc2.canonical({"a": 1})


def test_serialization_keeps_array_order_and_refuses_non_json_numbers():
    document = _positive("mucaro-ai")
    reordered = copy.deepcopy(document)
    reordered["navigation"]["groups"].reverse()  # navigation order is meaningful
    assert rc2.digest(reordered) != rc2.digest(document)
    with pytest.raises(ValueError):
        rc2.canonical({"value": float("nan")})


def test_a_non_object_document_is_reported_not_raised():
    codes = [finding.code for finding in rc2.validate([["not", "a", "contract"], None])]
    assert codes.count("schema:contract:type") == 2


@pytest.mark.parametrize("bad", [None, "x", 3, []], ids=["null", "string", "number", "list"])
def test_a_section_of_the_wrong_type_is_reported_not_fatal(bad):
    # Any top-level section replaced by a value of the wrong type yields
    # findings; the cross-section checks must not raise on it.
    document = _positive("mucaro-ai")
    for key in [k for k in document if not k.startswith("x-")]:
        broken = copy.deepcopy(document)
        broken[key] = bad
        if bad == [] and key in ("actions", "settings"):
            continue  # an empty list is valid there
        assert rc2.validate([broken]), f"{key}={bad!r} was accepted"
