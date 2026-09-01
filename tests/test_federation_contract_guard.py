from pathlib import Path
import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "guard", Path("scripts/federation_contract_guard.py")
)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def test_equal_contract_requires_no_bump():
    x = {"type": "object", "properties": {"a": {"type": "string"}}}
    assert guard.bump_class(x, x) == "NONE"


def test_optional_addition_is_minor():
    a = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    b = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["a"],
    }
    assert guard.bump_class(a, b) == "MINOR"


def test_new_required_field_is_major():
    a = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    b = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["a", "b"],
    }
    assert guard.bump_class(a, b) == "MAJOR"


def test_property_removal_is_major():
    a = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
    }
    b = {"type": "object", "properties": {"a": {"type": "string"}}}
    assert guard.bump_class(a, b) == "MAJOR"


def test_enum_narrowing_is_major():
    a = {"enum": ["A", "B"]}
    b = {"enum": ["A"]}
    assert guard.bump_class(a, b) == "MAJOR"


def test_enum_expansion_is_minor():
    a = {"enum": ["A"]}
    b = {"enum": ["A", "B"]}
    assert guard.bump_class(a, b) == "MINOR"


def test_semver_underbump_fails_rank():
    assert guard.RANK[guard.declared_bump("1.0.0", "1.1.0")] < guard.RANK["MAJOR"]


def test_transitive_closure():
    graph = {
        "edges": [
            {"from": "centinelas-pr", "to": "moneysweep-pr"},
            {"from": "moneysweep-pr", "to": "spiderweb-pr"},
            {"from": "spiderweb-pr", "to": "thehub-pr"},
        ]
    }
    assert guard.closure(graph, ["centinelas-pr"]) == [
        "centinelas-pr",
        "moneysweep-pr",
        "spiderweb-pr",
        "thehub-pr",
    ]


def test_unrelated_node_not_in_closure():
    graph = {"edges": [{"from": "a", "to": "b"}, {"from": "x", "to": "y"}]}
    assert guard.closure(graph, ["a"]) == ["a", "b"]
