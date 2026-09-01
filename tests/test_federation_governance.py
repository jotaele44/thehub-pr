from copy import deepcopy

import pytest
import yaml

import scripts.federation_governance as governance


def compatible_matrix() -> dict:
    return {
        "allowed_states": [
            "UNAFFECTED",
            "COMPATIBLE",
            "UPDATED",
            "BLOCKED",
        ],
        "repos": {repo: {"state": "COMPATIBLE"} for repo in governance.EXPECTED},
    }


def test_matrix_requires_exact_federation_membership():
    matrix = compatible_matrix()
    matrix["repos"].pop("ovnis-pr")

    with pytest.raises(SystemExit):
        governance.validate_matrix(matrix)


def test_matrix_rejects_blocked_repo():
    matrix = compatible_matrix()
    matrix["repos"]["skywatcher-pr"]["state"] = "BLOCKED"

    with pytest.raises(SystemExit):
        governance.validate_matrix(matrix)


def test_allowed_states_are_sourced_from_matrix():
    matrix = compatible_matrix()
    matrix["allowed_states"].append("REVIEW")
    matrix["repos"]["thehub-pr"]["state"] = "REVIEW"

    governance.validate_matrix(matrix)


@pytest.mark.parametrize(
    "version",
    ["0.0.0", "1.2.3", "1.2.3-rc.1", "1.2.3+build.5", "1.0.0-x.7+meta"],
)
def test_semver_accepts_semver_2_versions(version):
    assert governance.is_valid_semver(version)


@pytest.mark.parametrize(
    "version",
    ["01.2.3", "1.02.3", "1.2.03", "1.2", "1.2.3-01", "1.2.3+"],
)
def test_semver_rejects_invalid_versions(version):
    assert not governance.is_valid_semver(version)


def test_yaml_members_are_indentation_independent(tmp_path, monkeypatch):
    path = tmp_path / "graph.yaml"
    path.write_text(
        yaml.safe_dump({"nodes": [{"id": "thehub-pr"}, {"id": "ovnis-pr"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(governance, "ROOT", tmp_path)

    assert governance.yaml_members("graph.yaml", "nodes", "id") == {
        "thehub-pr",
        "ovnis-pr",
    }


def test_yaml_members_reject_duplicates(tmp_path, monkeypatch):
    path = tmp_path / "graph.yaml"
    path.write_text(
        "nodes:\n  - id: ovnis-pr\n  - id: ovnis-pr\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(governance, "ROOT", tmp_path)

    with pytest.raises(SystemExit):
        governance.yaml_members("graph.yaml", "nodes", "id")


def test_contract_change_impacts_every_repo():
    assert governance.impact_set(["schemas/example.schema.json"]) == governance.EXPECTED


def test_impacted_repo_requires_passing_disposition():
    matrix = deepcopy(compatible_matrix())
    matrix["repos"]["thehub-pr"]["state"] = "UNAFFECTED"

    with pytest.raises(SystemExit):
        governance.validate_impacted_dispositions(
            matrix,
            ["src/hub/new_policy.py"],
            all_impacted=False,
        )
