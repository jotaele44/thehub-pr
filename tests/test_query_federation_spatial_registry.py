import importlib.util
import json
from copy import deepcopy
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "query_federation_spatial_registry.py"
spec = importlib.util.spec_from_file_location("query_federation_spatial_registry", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def sample_registry():
    return {
        "contract_version": "federation-spatial-contract/1.1",
        "source_manifestations": [{"manifestation_id": "src-1"}],
        "geometry_manifestations": [{"geometry_manifestation_id": "geom-1"}],
        "canonical_entities": [{"canonical_id": "pr:municipio:001"}],
        "identity_bindings": [{"binding_id": "bind-1"}],
        "unresolved": [{"scope": "coastline_archipelago", "reason": "open", "state": "OPEN"}],
    }


def test_summary_is_read_only_and_exact():
    data = sample_registry()
    before = deepcopy(data)
    result = module.summary(data)
    assert result == {
        "contract_version": "federation-spatial-contract/1.1",
        "source_manifestations": 1,
        "geometry_manifestations": 1,
        "canonical_entities": 1,
        "identity_bindings": 1,
        "unresolved": 1,
    }
    assert data == before


def test_scope_and_ids_are_exact_not_fuzzy():
    data = sample_registry()
    assert module.query_scope(data, "coastline_archipelago") == data["unresolved"]
    assert module.query_scope(data, "coastline") == []
    assert module.query_canonical(data, "pr:municipio:001") == data["canonical_entities"]
    assert module.query_canonical(data, "001") == []
    assert module.query_source(data, "src-1") == data["source_manifestations"]
    assert module.query_source(data, "src") == []


def test_load_rejects_wrong_contract(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"contract_version": "wrong/1.0"}), encoding="utf-8")
    try:
        module.load_registry(path)
    except ValueError as exc:
        assert "unsupported spatial registry contract" in str(exc)
    else:
        raise AssertionError("wrong contract must fail closed")
