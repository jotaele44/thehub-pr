#!/usr/bin/env python3
"""Fail-closed governance checks for the PRII federation.

Checks:
- exact seven-repository compatibility coverage
- allowed dispositions and no BLOCKED residue
- contract policy shape and SemVer syntax
- registry/dependency-graph membership parity
- impact detection from changed paths
- explicit dispositions for every impacted repository
- documentation drift for canonical producer membership

This script intentionally uses only the Python standard library so governance
can run before project dependencies are installed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "thehub-pr",
    "moneysweep-pr",
    "spiderweb-pr",
    "aguayluz-pr",
    "ovnis-pr",
    "skywatcher-pr",
    "centinelas-pr",
}
PRODUCERS = EXPECTED - {"thehub-pr"}
PASSING_STATES = {"COMPATIBLE", "UPDATED"}
_PRERELEASE_IDENTIFIER = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
    rf"(?:-{_PRERELEASE_IDENTIFIER}(?:\.{_PRERELEASE_IDENTIFIER})*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
REPO_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def fail(msg: str) -> None:
    print(f"GOVERNANCE_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: str):
    with (ROOT / path).open(encoding="utf-8") as f:
        return json.load(f)


def load_yaml(path: str) -> dict:
    try:
        value = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        fail(f"invalid YAML in {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path}: YAML root must be a mapping")
    return value


def changed_files(base: str, head: str) -> list[str]:
    cp = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [x.strip() for x in cp.stdout.splitlines() if x.strip()]


def is_valid_semver(value: object) -> bool:
    return isinstance(value, str) and SEMVER.fullmatch(value) is not None


def yaml_members(path: str, collection: str, key: str) -> set[str]:
    document = load_yaml(path)
    rows = document.get(collection)
    if not isinstance(rows, list):
        fail(f"{path}: {collection} must be a list")

    members: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            fail(f"{path}: {collection}[{index}] must be a mapping")
        member = row.get(key)
        if not isinstance(member, str) or not REPO_ID.fullmatch(member):
            fail(f"{path}: {collection}[{index}].{key} is invalid")
        members.append(member)
    if len(members) != len(set(members)):
        fail(f"{path}: duplicate {key} values")
    return set(members)


def parse_dependency_nodes() -> set[str]:
    return yaml_members("governance/federation_dependencies.yaml", "nodes", "id")


def parse_registry_producers() -> set[str]:
    return yaml_members("registry/producers.yaml", "producers", "program_id")


def impact_set(files: list[str]) -> set[str]:
    impacted: set[str] = set()
    contract_paths = (
        "schemas/",
        "governance/contract_versions.json",
        "governance/federation_dependencies.yaml",
    )
    if any(p.startswith(contract_paths) for p in files):
        impacted |= EXPECTED
    if any(p.startswith("src/hub/") or p.startswith("server/backend/") for p in files):
        impacted.add("thehub-pr")
    if any(p.startswith("registry/") for p in files):
        impacted.add("thehub-pr")
        impacted |= PRODUCERS
    if any(p.startswith("packages/prii_maintenance/") for p in files):
        impacted |= EXPECTED
    return impacted


def check_docs() -> None:
    arch = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8").lower()
    missing = sorted(p for p in PRODUCERS if p not in arch)
    if missing:
        fail("ARCHITECTURE.md producer membership drift: missing " + ", ".join(missing))


def matrix_allowed_states(matrix: dict) -> set[str]:
    raw = matrix.get("allowed_states")
    if (
        not isinstance(raw, list)
        or not raw
        or any(not isinstance(state, str) or not state for state in raw)
        or len(raw) != len(set(raw))
    ):
        fail("compatibility matrix allowed_states must be unique strings")
    allowed = set(raw)
    required = {"UNAFFECTED", "COMPATIBLE", "UPDATED", "BLOCKED"}
    if not required <= allowed:
        fail(
            "compatibility matrix allowed_states missing required policies: "
            + ", ".join(sorted(required - allowed))
        )
    return allowed


def validate_matrix(matrix: dict) -> None:
    repos = matrix.get("repos")
    if not isinstance(repos, dict) or set(repos) != EXPECTED:
        actual = sorted(repos) if isinstance(repos, dict) else []
        fail(
            "compatibility matrix membership mismatch: "
            f"expected={sorted(EXPECTED)} actual={actual}"
        )

    allowed_states = matrix_allowed_states(matrix)
    for repo, row in repos.items():
        if not isinstance(row, dict):
            fail(f"{repo}: compatibility row must be an object")
        state = row.get("state")
        if state not in allowed_states:
            fail(f"{repo}: invalid compatibility state {state!r}")
        if state == "BLOCKED":
            fail(f"{repo}: compatibility state is BLOCKED")


def validate_contract_versions(policy: dict) -> None:
    contracts = policy.get("contracts")
    if not isinstance(contracts, dict) or not contracts:
        fail("contract version policy must contain contracts")
    for name, row in contracts.items():
        if not isinstance(row, dict):
            fail(f"{name}: contract policy must be an object")
        version = row.get("current")
        if not is_valid_semver(version):
            fail(f"{name}: invalid semantic version {version!r}")


def validate_admin_boundary() -> None:
    matrix = load_json("governance/admin_control_plane/privilege_matrix.json")
    if matrix.get("default_effect") != "DENY":
        fail("admin control plane must default to DENY")
    signed = load_json("config/operations_policy.json")
    expected = {row["operation_id"] for row in signed["policy"]["operations"]}
    bindings = matrix.get("operation_bindings")
    if not isinstance(bindings, list):
        fail("admin privilege matrix operation_bindings must be a list")
    ids = [row.get("operation_id") for row in bindings if isinstance(row, dict)]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        fail("admin privilege matrix must classify every signed operation exactly once")
    for row in bindings:
        if row.get("allowed_clients") != ["thehub_workstation"]:
            fail(f"{row.get('operation_id')}: operation execution must be workstation-only")
        if row.get("authority_class") not in {"LOCAL_REPO", "CROSS_REPO", "FEDERATION_GLOBAL"}:
            fail(f"{row.get('operation_id')}: invalid authority class")
        if row.get("audit_required") is not True:
            fail(f"{row.get('operation_id')}: audit must be required")


def validate_impacted_dispositions(
    matrix: dict, files: list[str], *, all_impacted: bool
) -> set[str]:
    impacted = EXPECTED if all_impacted else impact_set(files)
    missing = sorted(
        repo
        for repo in impacted
        if matrix["repos"][repo]["state"] not in PASSING_STATES
    )
    if missing:
        fail(
            "impacted repos lack COMPATIBLE/UPDATED disposition: " + ", ".join(missing)
        )
    return impacted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument(
        "--all",
        action="store_true",
        help="Treat all federation repositories as impacted",
    )
    args = ap.parse_args()

    matrix = load_json("governance/compatibility_matrix.json")
    policy = load_json("governance/contract_versions.json")

    validate_matrix(matrix)
    validate_contract_versions(policy)
    validate_admin_boundary()

    dep_nodes = parse_dependency_nodes()
    if dep_nodes != EXPECTED:
        fail(
            f"dependency graph membership mismatch: expected={sorted(EXPECTED)} actual={sorted(dep_nodes)}"
        )

    registry = parse_registry_producers()
    if registry != PRODUCERS:
        fail(
            f"producer registry mismatch: expected={sorted(PRODUCERS)} actual={sorted(registry)}"
        )

    check_docs()

    files = [] if args.all else changed_files(args.base, args.head)
    impacted = validate_impacted_dispositions(matrix, files, all_impacted=args.all)

    print("GOVERNANCE_PASS")
    print("changed_files=" + str(len(files)))
    print("impacted=" + ",".join(sorted(impacted)))
    print("repos=7 contracts=" + str(len(policy.get("contracts", {}))))


if __name__ == "__main__":
    main()
