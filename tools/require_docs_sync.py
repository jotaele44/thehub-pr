#!/usr/bin/env python3
"""Mark ``docs-sync`` a required status check on ``main`` in each federation repo.

ADR 0010, rollout step 3. A passing ``docs-sync`` job only blocks a merge once
``main`` requires it, and that is a repository setting no template or workflow
can set, so a repository administrator runs this once.

Repos are the Hub plus every producer in ``registry/producers.yaml``. Per repo:
  - skipped if ``.github/workflows/docs-sync.yml`` is not on ``main``: a required
    check that never reports would block every pull request;
  - skipped while listed in ``HELD``: a workflow in regular use there pushes
    commits straight to ``main`` with the Actions token, and a required check
    rejects such a push because ``docs-sync`` only ever runs on pull requests;
  - an active ruleset on the default branch that already requires checks gets
    ``docs-sync`` appended to its list;
  - otherwise classic branch protection that already requires checks gets it
    appended;
  - otherwise a new ruleset ``main-required-checks`` is created requiring only
    ``docs-sync``, with the repository-admin bypass moneysweep-pr's ruleset uses.
The check is pinned to the GitHub Actions app, so no other app can satisfy it by
posting a status with the same name. A repo that already requires it is left
alone, so re-running is a no-op.

Usage:
  require_docs_sync.py            # dry run: print what would change
  require_docs_sync.py --apply    # make the changes, then re-read each repo

Needs ``gh`` logged in with admin rights on the repos. PyYAML only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

import yaml

CHECK = "docs-sync"
WORKFLOW = ".github/workflows/docs-sync.yml"
ACTIONS_APP_ID = 15368  # GitHub Actions
ADMIN_ROLE_ID = 5  # RepositoryRole "admin"
NEW_RULESET = "main-required-checks"
REGISTRY = Path(__file__).resolve().parents[1] / "registry" / "producers.yaml"

# Repo name -> why requiring a check on main would break it. Remove the entry once
# the workflow opens a pull request instead of pushing to main, or records docs-sync
# on its commit before pushing (centinelas-pr's scripts/push_to_main.sh).
HELD = {
    "aguayluz-pr": "refresh.yml commits scheduled data refreshes straight to main",
}

# (method, path, body) -> parsed JSON, or None when the API answers with an error.
Api = Callable[[str, str, "dict | None"], "dict | list | None"]


def federation_repos(registry: Path = REGISTRY) -> list[str]:
    """owner/name of the Hub and every registered producer."""
    data = yaml.safe_load(registry.read_text())
    repos = [p["repo"] for p in data["producers"]]
    owner = repos[0].split("/")[0]
    return [f"{owner}/{data['hub']}", *repos]


def gh_api(method: str, path: str, body: dict | None = None) -> dict | list | None:
    cmd = ["gh", "api", "-X", method, path, "-H", "Accept: application/vnd.github+json"]
    if body is not None:
        cmd += ["--input", "-"]
    proc = subprocess.run(
        cmd,
        input=json.dumps(body) if body is not None else None,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def _targets_main(ruleset: dict) -> bool:
    include = ruleset.get("conditions", {}).get("ref_name", {}).get("include", [])
    return any(ref in ("~DEFAULT_BRANCH", "~ALL", "refs/heads/main") for ref in include)


def plan(repo: str, api: Api) -> tuple[str, tuple[str, str, dict] | None]:
    """What to do for one repo: (description, (method, path, body) or None)."""
    base = f"repos/{repo}"
    if api("GET", f"{base}/contents/{WORKFLOW}?ref=main", None) is None:
        return f"skip: no {WORKFLOW} on main; requiring it would block every PR", None
    held = HELD.get(repo.split("/")[1])
    if held:
        return f"held: {held}; a required check would reject those pushes", None

    for summary in api("GET", f"{base}/rulesets", None) or []:
        ruleset = api("GET", f"{base}/rulesets/{summary['id']}", None)
        if (
            not ruleset
            or ruleset.get("target") != "branch"
            or ruleset.get("enforcement") != "active"
            or not _targets_main(ruleset)
        ):
            continue
        rule = next(
            (r for r in ruleset["rules"] if r["type"] == "required_status_checks"), None
        )
        if rule is None:
            continue
        checks = rule["parameters"]["required_status_checks"]
        if any(c["context"] == CHECK for c in checks):
            return f"already required by ruleset '{ruleset['name']}'", None
        checks.append({"context": CHECK, "integration_id": ACTIONS_APP_ID})
        body = {
            k: ruleset[k]
            for k in ("name", "target", "enforcement", "conditions", "rules", "bypass_actors")
        }
        return (
            f"add {CHECK} to ruleset '{ruleset['name']}' ({len(checks)} checks)",
            ("PUT", f"{base}/rulesets/{ruleset['id']}", body),
        )

    path = f"{base}/branches/main/protection/required_status_checks"
    classic = api("GET", path, None)
    if classic:
        checks = [{"context": c["context"], "app_id": c.get("app_id")} for c in classic["checks"]]
        if any(c["context"] == CHECK for c in checks):
            return "already required by branch protection", None
        checks.append({"context": CHECK, "app_id": ACTIONS_APP_ID})
        return (
            f"add {CHECK} to branch protection ({len(checks)} checks)",
            ("PATCH", path, {"strict": classic["strict"], "checks": checks}),
        )

    body = {
        "name": NEW_RULESET,
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": False,
                    "do_not_enforce_on_create": False,
                    "required_status_checks": [
                        {"context": CHECK, "integration_id": ACTIONS_APP_ID}
                    ],
                },
            }
        ],
        "bypass_actors": [
            {"actor_id": ADMIN_ROLE_ID, "actor_type": "RepositoryRole", "bypass_mode": "always"}
        ],
    }
    return (
        f"create ruleset '{NEW_RULESET}' requiring only {CHECK}",
        ("POST", f"{base}/rulesets", body),
    )


def required_on_main(repo: str, api: Api) -> bool:
    """Whether main requires docs-sync, through a ruleset or classic protection."""
    names = [
        c["context"]
        for r in api("GET", f"repos/{repo}/rules/branches/main", None) or []
        if r["type"] == "required_status_checks"
        for c in r["parameters"]["required_status_checks"]
    ]
    classic = api("GET", f"repos/{repo}/branches/main/protection/required_status_checks", None)
    names += [c["context"] for c in (classic or {}).get("checks", [])]
    return CHECK in names


def main(argv: list[str] | None = None, api: Api = gh_api) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="make the changes")
    args = parser.parse_args(argv)

    ok = True
    for repo in federation_repos():
        description, action = plan(repo, api)
        print(repo)
        if action is None:
            print(f"  {description}")
            continue
        print(f"  {'apply' if args.apply else 'would'}: {description}")
        if not args.apply:
            continue
        if api(*action) is None:
            print("  FAILED: the API refused the change (admin rights on this repo?)")
            ok = False
        print(f"  {CHECK} required on main now: {required_on_main(repo, api)}")
    if not args.apply:
        print("\nDry run. Re-run with --apply to make these changes.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
