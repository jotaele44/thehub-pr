"""Tests for tools/require_docs_sync.py against a fake GitHub API (no network)."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[1] / "tools" / "require_docs_sync.py"


def _load():
    spec = importlib.util.spec_from_file_location("_require_docs_sync", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rds = _load()
REPO = "jotaele44/example-pr"
BASE = f"repos/{REPO}"
CLASSIC = f"{BASE}/branches/main/protection/required_status_checks"


def ruleset(checks, **over):
    rs = {
        "id": 7,
        "name": "main-protection",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "required_status_checks": [{"context": c} for c in checks],
                },
            },
        ],
        "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
    }
    rs.update(over)
    return rs


class FakeApi:
    """GET answers from a path -> response map; anything absent is an API error."""

    def __init__(self, responses, workflow=True):
        self.responses = copy.deepcopy(responses)
        if workflow:
            self.responses[f"{BASE}/contents/{rds.WORKFLOW}?ref=main"] = {"path": rds.WORKFLOW}
        self.calls = []

    def __call__(self, method, path, body):
        self.calls.append((method, path, body))
        return copy.deepcopy(self.responses.get(path)) if method == "GET" else {}


def test_federation_repos_are_the_hub_and_every_registered_producer():
    repos = rds.federation_repos()
    assert repos[0] == "jotaele44/thehub-pr"
    assert {"jotaele44/moneysweep-pr", "jotaele44/spiderweb-pr"} <= set(repos)
    assert len(repos) == len(set(repos))


def test_repo_without_the_workflow_is_skipped():
    description, action = rds.plan(REPO, FakeApi({}, workflow=False))
    assert action is None and description.startswith("skip:")


def test_held_repo_is_skipped_with_its_reason(monkeypatch):
    monkeypatch.setitem(rds.HELD, "example-pr", "cron.yml pushes to main")
    description, action = rds.plan(REPO, FakeApi({}))
    assert action is None and "cron.yml pushes to main" in description


def test_check_is_appended_to_an_existing_ruleset_keeping_everything_else():
    existing = ruleset(["ruff", "mypy"])
    api = FakeApi({f"{BASE}/rulesets": [{"id": 7}], f"{BASE}/rulesets/7": existing})
    _, (method, path, body) = rds.plan(REPO, api)
    assert (method, path) == ("PUT", f"{BASE}/rulesets/7")
    assert body["bypass_actors"] == existing["bypass_actors"]
    assert body["rules"][0] == {"type": "deletion"}
    params = body["rules"][1]["parameters"]
    assert params["strict_required_status_checks_policy"] is True
    assert params["required_status_checks"] == [
        {"context": "ruff"},
        {"context": "mypy"},
        {"context": "docs-sync", "integration_id": rds.ACTIONS_APP_ID},
    ]


@pytest.mark.parametrize(
    "over",
    [
        {"enforcement": "evaluate"},
        {"target": "tag"},
        {"conditions": {"ref_name": {"include": ["refs/heads/release"], "exclude": []}}},
    ],
)
def test_ruleset_that_does_not_enforce_on_main_is_not_used(over):
    api = FakeApi({f"{BASE}/rulesets": [{"id": 7}], f"{BASE}/rulesets/7": ruleset(["ruff"], **over)})
    _, (method, path, _) = rds.plan(REPO, api)
    assert (method, path) == ("POST", f"{BASE}/rulesets")


def test_check_is_appended_to_classic_protection_keeping_strictness_and_app_pins():
    classic = {"strict": False, "checks": [{"context": "lint", "app_id": 15368}]}
    api = FakeApi({f"{BASE}/rulesets": [], CLASSIC: classic})
    _, (method, path, body) = rds.plan(REPO, api)
    assert (method, path) == ("PATCH", CLASSIC)
    assert body == {
        "strict": False,
        "checks": [
            {"context": "lint", "app_id": 15368},
            {"context": "docs-sync", "app_id": rds.ACTIONS_APP_ID},
        ],
    }


def test_unprotected_repo_gets_a_ruleset_requiring_only_docs_sync():
    _, (method, path, body) = rds.plan(REPO, FakeApi({f"{BASE}/rulesets": []}))
    assert (method, path) == ("POST", f"{BASE}/rulesets")
    assert body["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    [rule] = body["rules"]
    assert rule["parameters"]["required_status_checks"] == [
        {"context": "docs-sync", "integration_id": rds.ACTIONS_APP_ID}
    ]


@pytest.mark.parametrize(
    "responses",
    [
        {f"{BASE}/rulesets": [{"id": 7}], f"{BASE}/rulesets/7": ruleset(["docs-sync"])},
        {f"{BASE}/rulesets": [], CLASSIC: {"strict": False, "checks": [{"context": "docs-sync"}]}},
    ],
)
def test_already_required_is_a_no_op(responses):
    description, action = rds.plan(REPO, FakeApi(responses))
    assert action is None and description.startswith("already required")


def test_dry_run_writes_nothing(monkeypatch, capsys):
    monkeypatch.setattr(rds, "federation_repos", lambda: [REPO])
    api = FakeApi({f"{BASE}/rulesets": []})
    assert rds.main([], api=api) == 0
    assert all(method == "GET" for method, _, _ in api.calls)
    assert "would: create ruleset" in capsys.readouterr().out


def test_apply_writes_and_reports_a_refused_change(monkeypatch, capsys):
    monkeypatch.setattr(rds, "federation_repos", lambda: [REPO])
    api = FakeApi({f"{BASE}/rulesets": []})
    refused = lambda method, path, body: None if method != "GET" else api(method, path, body)  # noqa: E731
    assert rds.main(["--apply"], api=refused) == 1
    assert "FAILED" in capsys.readouterr().out
