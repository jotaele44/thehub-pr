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


def test_collect_repo_state_flags_malformed_federation_json(tmp_path):
    (tmp_path / "federation.json").write_text("{not json", encoding="utf-8")
    state = state_mod.collect_repo_state(tmp_path)
    # A malformed manifest is distinct from a missing one: present-but-corrupt
    # must not be treated as "present" (that would let a corrupt repo produce
    # a cleaner report than a repo with no manifest at all).
    assert state["federation_json_present"] is False
    assert state["federation_json_malformed"] is True
    assert state["federation"] == {}


def test_collect_repo_state_no_malformed_flag_when_valid(tmp_path):
    (tmp_path / "federation.json").write_text('{"program_id": "acme-pr"}', encoding="utf-8")
    state = state_mod.collect_repo_state(tmp_path)
    assert state["federation_json_present"] is True
    assert state["federation_json_malformed"] is False


def test_collect_repo_state_no_malformed_flag_when_absent(tmp_path):
    state = state_mod.collect_repo_state(tmp_path)
    assert state["federation_json_present"] is False
    assert state["federation_json_malformed"] is False
