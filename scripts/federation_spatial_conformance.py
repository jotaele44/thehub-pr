#!/usr/bin/env python3
"""Validate the federation spatial capability matrix without collapsing role asymmetry.

This validator checks the control-plane specification itself. It intentionally does
not certify producer domain truth. Producer fixture runners and compatibility
receipts remain separate evidence and must close before federation certification.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "registry/spatial/federation_spatial_capability_matrix_v1.json"

EXPECTED_REPOS = {
    "spiderweb-pr",
    "aguayluz-pr",
    "skywatcher-pr",
    "moneysweep-pr",
    "centinelas-pr",
    "ovnis-pr",
    "thehub-pr",
}

ALLOWED_CLASSES = {"DOMAIN_AUTHORITY", "FEDERATION_AUTHORITY", "CONSUMER", "N/A"}
REQUIRED_INVARIANTS = {
    "Cell_ID is a spatial address and never identity proof",
    "spatial proximity defaults to CANDIDATE_NOT_IDENTITY",
    "N/A is not LOW and is not FAIL",
    "domain producers own domain truth while TheHub owns cross-producer correlation",
    "Spiderweb owns generic geometry semantics but not producer domain truth",
}


def load_matrix(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(matrix: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if matrix.get("schema_version") != "prii_federation_spatial_capability_matrix_v1":
        errors.append("wrong schema_version")
    if matrix.get("certification_model") != "asymmetric_role_conformance":
        errors.append("certification_model must preserve asymmetric roles")
    if matrix.get("identity_default") != "CANDIDATE_NOT_IDENTITY":
        errors.append("identity_default must fail closed")
    if matrix.get("geometry_authority") != "spiderweb-pr":
        errors.append("geometry_authority must remain spiderweb-pr")
    if matrix.get("correlation_authority") != "thehub-pr":
        errors.append("correlation_authority must remain thehub-pr")

    roles = matrix.get("roles")
    if not isinstance(roles, dict):
        return errors + ["roles must be an object"]

    found = set(roles)
    if found != EXPECTED_REPOS:
        errors.append(
            "repository denominator mismatch: "
            f"missing={sorted(EXPECTED_REPOS - found)} extra={sorted(found - EXPECTED_REPOS)}"
        )

    fixtures = matrix.get("fixture_denominator")
    if not isinstance(fixtures, dict):
        errors.append("fixture_denominator must be an object")
        fixtures = {}
    elif set(fixtures) != EXPECTED_REPOS:
        errors.append("fixture denominator must contain exactly the seven federation repositories")

    for repo in sorted(EXPECTED_REPOS & found):
        role = roles[repo]
        if not isinstance(role, dict):
            errors.append(f"{repo}: role entry must be an object")
            continue

        classes = role.get("authority_classes")
        if not isinstance(classes, list) or not classes:
            errors.append(f"{repo}: authority_classes must be non-empty")
        elif any(c not in ALLOWED_CLASSES for c in classes):
            errors.append(f"{repo}: invalid authority class")

        required = role.get("required_capabilities")
        not_required = role.get("not_required")
        if not isinstance(required, list) or not required:
            errors.append(f"{repo}: required_capabilities must be non-empty")
        if not isinstance(not_required, list):
            errors.append(f"{repo}: not_required must be a list")
        if isinstance(required, list) and isinstance(not_required, list):
            overlap = set(required) & set(not_required)
            if overlap:
                errors.append(f"{repo}: capability both required and not_required: {sorted(overlap)}")

        repo_fixtures = fixtures.get(repo)
        if not isinstance(repo_fixtures, list) or len(repo_fixtures) < 5:
            errors.append(f"{repo}: fixture denominator must contain at least five cases")
        elif len(repo_fixtures) != len(set(repo_fixtures)):
            errors.append(f"{repo}: duplicate fixture ids")

    invariants = matrix.get("shared_invariants")
    if not isinstance(invariants, list):
        errors.append("shared_invariants must be a list")
    else:
        missing = REQUIRED_INVARIANTS - set(invariants)
        if missing:
            errors.append(f"missing shared invariants: {sorted(missing)}")

    states = matrix.get("certification_states")
    if not isinstance(states, list) or "UNRESOLVED" not in states or "PASS" not in states:
        errors.append("certification_states must include PASS and UNRESOLVED")

    pass_rule = matrix.get("federation_pass_rule")
    if not isinstance(pass_rule, str) or "no unresolved residue" not in pass_rule.lower():
        errors.append("federation_pass_rule must fail closed on unresolved residue")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        matrix = load_matrix(args.matrix)
        errors = validate(matrix)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors = [f"cannot load matrix: {exc}"]

    state = "PASS" if not errors else "FAIL"
    result = {
        "state": state,
        "matrix": str(args.matrix),
        "repository_count": len(EXPECTED_REPOS),
        "errors": errors,
        "claim_scope": "specification conformance only; producer domain fixtures are not certified by this validator",
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"FEDERATION_SPATIAL_CONFORMANCE_SPEC={state}")
        for error in errors:
            print(f"FAIL: {error}")
        if not errors:
            print("PASS: seven-repository asymmetric role matrix is internally consistent")
            print("OPEN: producer fixture execution and cross-repository receipts remain required")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
