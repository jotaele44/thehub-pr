import importlib.util
import json
import re
from copy import deepcopy
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "query_federation_spatial_registry.py"
)
spec = importlib.util.spec_from_file_location(
    "query_federation_spatial_registry", SCRIPT
)
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
        "unresolved": [
            {"scope": "coastline_archipelago", "reason": "open", "state": "OPEN"}
        ],
    }


def sample_bridge():
    return {
        "contract_version": "federation-spatial-archipelago-evidence-bridge/1.1",
        "durable_freeze": {
            "tag": "pr-archipelago-freeze-2026-08-22",
            "source_evidence_preservation": "PASS",
        },
        "frozen_manifestations": {},
        "source_manifestation_denominator": {
            "source_manifestations": 42891,
            "retained": 148,
            "excluded": 5961,
            "candidate": 36782,
            "unresolved": 0,
            "arithmetic_closed": True,
        },
        "current_geometry_audit": {},
        "canonical_gates": {
            "canonical_identity_denominator_closed": False,
            "canonical_geometry_denominator_closed": False,
            "known_unresolved_sige_identity_bindings": 4,
            "runtime_activation": "BLOCKED",
            "CURRENT_PR_ARCHIPELAGO": "OPEN",
            "GEOMETRIC_CURRENT": "OPEN",
        },
        "v1_1_ingestion_state": {
            "strict_source_manifestation_rows": "BLOCKED_PENDING_EXACT_RETRIEVAL_TIMESTAMP_MAPPING_FOR_LEGACY_RECEIPTS"
        },
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


def test_bridge_summary_is_read_only_and_preserves_open_canonical_gates():
    data = sample_bridge()
    before = deepcopy(data)
    result = module.bridge_summary(data)
    assert result == {
        "contract_version": "federation-spatial-archipelago-evidence-bridge/1.1",
        "source_evidence_preservation": "PASS",
        "durable_release_tag": "pr-archipelago-freeze-2026-08-22",
        "source_manifestations": 42891,
        "retained": 148,
        "excluded": 5961,
        "candidate": 36782,
        "unresolved_source_partition": 0,
        "source_arithmetic_closed": True,
        "canonical_identity_denominator_closed": False,
        "canonical_geometry_denominator_closed": False,
        "known_unresolved_sige_identity_bindings": 4,
        "runtime_activation": "BLOCKED",
        "current_pr_archipelago": "OPEN",
        "geometric_current": "OPEN",
        "strict_v1_1_ingestion": "BLOCKED_PENDING_EXACT_RETRIEVAL_TIMESTAMP_MAPPING_FOR_LEGACY_RECEIPTS",
    }
    assert data == before


def test_scope_and_ids_are_exact_not_fuzzy():
    data = sample_registry()
    assert module.query_scope(data, "coastline_archipelago") == data["unresolved"]
    assert module.query_scope(data, "coastline") == []
    assert (
        module.query_canonical(data, "pr:municipio:001") == data["canonical_entities"]
    )
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


def test_bridge_rejects_wrong_contract_and_missing_required_sections(tmp_path):
    wrong = tmp_path / "wrong-bridge.json"
    wrong.write_text(json.dumps({"contract_version": "wrong/1.0"}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported spatial evidence bridge contract"):
        module.load_bridge(wrong)

    malformed = sample_bridge()
    del malformed["canonical_gates"]
    path = tmp_path / "malformed-bridge.json"
    path.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical_gates must be an object"):
        module.load_bridge(path)


@pytest.mark.parametrize(
    "payload, expected",
    [
        ([], "root must be an object"),
        (
            {
                "contract_version": "federation-spatial-contract/1.1",
                "source_manifestations": {},
                "geometry_manifestations": [],
                "canonical_entities": [],
                "identity_bindings": [],
                "unresolved": [],
            },
            "source_manifestations must be an array",
        ),
        (
            {
                "contract_version": "federation-spatial-contract/1.1",
                "source_manifestations": ["not-an-object"],
                "geometry_manifestations": [],
                "canonical_entities": [],
                "identity_bindings": [],
                "unresolved": [],
            },
            "source_manifestations[0] must be an object",
        ),
    ],
)
def test_load_rejects_malformed_registry_shapes(tmp_path, payload, expected):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=re.escape(expected)):
        module.load_registry(path)
