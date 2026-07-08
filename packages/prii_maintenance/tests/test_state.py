import json

from prii_maintenance import state as state_mod


def test_collect_repo_state_missing_federation_json(tmp_path):
    state = state_mod.collect_repo_state(tmp_path)
    assert state["federation_json_present"] is False
    assert state["federation"] == {}
    assert state["canonical_outputs"] == {}
    assert state["canonical_outputs_present"] == {}


def test_collect_repo_state_reads_canonical_outputs(tmp_path):
    (tmp_path / "out.json").write_text("{}", encoding="utf-8")
    fed = {
        "program_id": "acme-pr",
        "canonical_outputs": {"a": "out.json", "b": "missing.json"},
    }
    (tmp_path / "federation.json").write_text(json.dumps(fed), encoding="utf-8")

    state = state_mod.collect_repo_state(tmp_path)

    assert state["federation_json_present"] is True
    assert state["federation"]["program_id"] == "acme-pr"
    assert state["canonical_outputs_present"] == {"a": True, "b": False}


def test_collect_repo_state_tolerates_invalid_json(tmp_path):
    (tmp_path / "federation.json").write_text("{not json", encoding="utf-8")
    state = state_mod.collect_repo_state(tmp_path)
    assert state["federation_json_present"] is True  # file exists...
    assert state["federation"] == {}  # ...but doesn't parse, so treated as absent
