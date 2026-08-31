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
ALLOWED_STATES = {"UNAFFECTED", "COMPATIBLE", "UPDATED", "BLOCKED"}
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def fail(msg: str) -> None:
    print(f"GOVERNANCE_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: str):
    with (ROOT / path).open(encoding="utf-8") as f:
        return json.load(f)


def changed_files(base: str, head: str) -> list[str]:
    cp = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [x.strip() for x in cp.stdout.splitlines() if x.strip()]


def parse_dependency_nodes() -> set[str]:
    text = (ROOT / "governance/federation_dependencies.yaml").read_text(encoding="utf-8")
    return set(re.findall(r"^  - id: ([a-z0-9-]+)$", text, flags=re.M))


def parse_registry_producers() -> set[str]:
    text = (ROOT / "registry/producers.yaml").read_text(encoding="utf-8")
    return set(re.findall(r"^  - program_id: ([a-z0-9-]+)$", text, flags=re.M))


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--all", action="store_true", help="Treat all federation repositories as impacted")
    args = ap.parse_args()

    matrix = load_json("governance/compatibility_matrix.json")
    policy = load_json("governance/contract_versions.json")

    repos = set(matrix.get("repos", {}))
    if repos != EXPECTED:
        fail(f"compatibility matrix membership mismatch: expected={sorted(EXPECTED)} actual={sorted(repos)}")

    for repo, row in matrix["repos"].items():
        state = row.get("state")
        if state not in ALLOWED_STATES:
            fail(f"{repo}: invalid compatibility state {state!r}")
        if state == "BLOCKED":
            fail(f"{repo}: compatibility state is BLOCKED")

    for name, row in policy.get("contracts", {}).items():
        version = row.get("current", "")
        if not SEMVER.fullmatch(version):
            fail(f"{name}: invalid semantic version {version!r}")

    dep_nodes = parse_dependency_nodes()
    if dep_nodes != EXPECTED:
        fail(f"dependency graph membership mismatch: expected={sorted(EXPECTED)} actual={sorted(dep_nodes)}")

    registry = parse_registry_producers()
    if registry != PRODUCERS:
        fail(f"producer registry mismatch: expected={sorted(PRODUCERS)} actual={sorted(registry)}")

    check_docs()

    files = [] if args.all else changed_files(args.base, args.head)
    impacted = EXPECTED if args.all else impact_set(files)
    missing_disposition = sorted(r for r in impacted if matrix["repos"][r]["state"] not in {"COMPATIBLE", "UPDATED"})
    if missing_disposition:
        fail("impacted repos lack COMPATIBLE/UPDATED disposition: " + ", ".join(missing_disposition))

    print("GOVERNANCE_PASS")
    print("changed_files=" + str(len(files)))
    print("impacted=" + ",".join(sorted(impacted)))
    print("repos=7 contracts=" + str(len(policy.get("contracts", {}))))


if __name__ == "__main__":
    main()
