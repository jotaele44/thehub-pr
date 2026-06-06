import copy
import json

from hub.manifest import load_and_validate_manifest, validate_repo_manifest


def test_real_contract_sweeper_manifest_conforms(fixtures_dir):
    """The actual federation.json that landed on Contract-Sweeper main (PR #199)
    must validate against the Hub's repo_federation_manifest_v1 schema."""
    data, errors = load_and_validate_manifest(fixtures_dir / "contract_sweeper_federation.json")
    assert errors == [], errors
    assert data["hub_parent"] == "thehub-pr"


def _base(fixtures_dir):
    return json.loads((fixtures_dir / "contract_sweeper_federation.json").read_text())


def test_wrong_hub_parent_is_rejected(fixtures_dir):
    bad = _base(fixtures_dir)
    bad["hub_parent"] = "some-other-hub"
    errors = validate_repo_manifest(bad)
    assert any("hub_parent" in e for e in errors)


def test_missing_offline_command_is_rejected(fixtures_dir):
    bad = _base(fixtures_dir)
    del bad["hub_callable_commands"]["test_suite"]
    errors = validate_repo_manifest(bad)
    assert any("test_suite" in e for e in errors)


def test_missing_readiness_gate_is_rejected(fixtures_dir):
    bad = _base(fixtures_dir)
    del bad["federation_readiness_gate"]
    errors = validate_repo_manifest(bad)
    assert any("federation_readiness_gate" in e for e in errors)


def test_bad_schema_version_is_rejected(fixtures_dir):
    bad = _base(fixtures_dir)
    bad["schema_version"] = "repo_federation_manifest_v2"
    errors = validate_repo_manifest(bad)
    assert errors
