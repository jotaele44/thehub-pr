#!/usr/bin/env python3
"""Canonical CLI entry point for authority-boundary validation.

This v4 wrapper composes the original B.1-B.5 validator with the structured B.3
crawler and the PLAN MAX pre-activation artifacts. It remains fail-closed: draft
A/D material is checked for bounded non-authoritative state, but Phase A is not
activated by this script. A zero-blocker hosted receipt is the only condition
that may emit AUTHORITY_BOUNDARY_CERTIFIED.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from authority_boundary_validator import (
    load_json,
    repository_paths,
    validate as validate_base,
)
from identifier_namespace_census import validate as validate_identifier_v2

AUTHORITY = "prii-federation-spatial-identity"


def _finding(report: dict[str, Any], finding_id: str) -> Any:
    for row in report.get("findings", []):
        if row.get("id") == finding_id:
            return row.get("detail")
    return None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _append(blockers: list[dict[str, Any]], blocker_id: str, detail: Any) -> None:
    blockers.append({"id": blocker_id, "detail": detail})


def _validate_max_artifacts(root: Path, blockers: list[dict[str, Any]]) -> dict[str, Any]:
    receipt_schema = load_json(root / "registry/federation/authority_boundary_receipt.schema.json")
    matrix = load_json(root / "registry/federation/authority_matrix.json")
    sources = load_json(root / "registry/federation/source_ownership.json")
    drift = load_json(root / "registry/federation/drift_policy.json")
    arithmetic = load_json(root / "registry/federation/arithmetic_closure.json")
    certificate = load_json(root / "registry/federation/certifications/authority_boundary_certification.json")
    draft_a = load_json(root / "registry/federation/draft/federation_spatial_entity_contract_1_0.json")
    d_corpus = load_json(root / "tests/fixtures/federation_identity_adversarial/corpus.json")
    authority_census = load_json(root / "registry/federation/authority_boundary_census.json")

    if receipt_schema.get("properties", {}).get("schema_version", {}).get("const") != "authority_boundary_validation_v4":
        _append(blockers, "B-H1-RECEIPT-CONTRACT", "receipt schema does not pin authority_boundary_validation_v4")

    objects = matrix.get("objects", [])
    object_ids = [row.get("authority_object_id") for row in objects]
    if matrix.get("state") != "FROZEN_CANDIDATE" or len(object_ids) != len(set(object_ids)):
        _append(blockers, "B-H4-AUTHORITY-MATRIX", {"state": matrix.get("state"), "duplicate_ids": len(object_ids) - len(set(object_ids))})
    for row in objects:
        writers = row.get("write_authority")
        if not isinstance(writers, list):
            _append(blockers, "B-H4-WRITE-AUTHORITY-MISSING", row.get("authority_object_id"))
            continue
        if row.get("shared_or_domain") == "SHARED" and len(writers) != 1:
            _append(blockers, "B-H4-SHARED-MULTIWRITER", {"id": row.get("authority_object_id"), "writers": writers})
        if len(writers) > 1 and row.get("shared_or_domain") != "CROSS_DOMAIN":
            _append(blockers, "B-H4-AMBIGUOUS-WRITER", {"id": row.get("authority_object_id"), "writers": writers})
    if matrix.get("invariants", {}).get("unclassified_authority_objects") != 0:
        _append(blockers, "B-H4-UNCLASSIFIED", matrix.get("invariants"))

    source_closure = sources.get("closure", {})
    allowed = set(sources.get("allowed_classifications", []))
    bad_source_classes = [
        row.get("source_family_id")
        for row in sources.get("families", [])
        if row.get("classification") not in allowed
    ]
    if (
        sources.get("state") != "FROZEN_CANDIDATE"
        or source_closure.get("unclassified_families") != 0
        or source_closure.get("ambiguous_authority_families") != 0
        or bad_source_classes
    ):
        _append(blockers, "B-H5-SOURCE-OWNERSHIP", {"closure": source_closure, "bad_classes": bad_source_classes})

    if drift.get("state") != "ACTIVE_CANDIDATE_POLICY" or not drift.get("critical_inputs"):
        _append(blockers, "B-H6-DRIFT-POLICY", drift.get("state"))

    requirements = arithmetic.get("certification_requirements", {})
    if arithmetic.get("state") != "FROZEN_CANDIDATE" or requirements.get("blocked") != 0 or requirements.get("unclassified") != 0:
        _append(blockers, "B-H7-ARITHMETIC-CONTRACT", {"state": arithmetic.get("state"), "requirements": requirements})

    if (
        certificate.get("state") != "READY_FOR_ZERO_BLOCKER_RECEIPT"
        or certificate.get("issued_at") is not None
        or certificate.get("receipt_sha256") is not None
        or certificate.get("successor_phase", {}).get("state") != "LOCKED"
        or certificate.get("manual_override_permitted") is not False
    ):
        _append(blockers, "B-H8-DORMANT-CERTIFICATE", certificate)

    if (
        draft_a.get("status") != "DRAFT_NONAUTHORITATIVE"
        or draft_a.get("activation_requires") != "AUTHORITY_BOUNDARY_CERTIFIED"
        or draft_a.get("activation_state") != "LOCKED_PENDING_B_CERTIFICATION"
        or len(draft_a.get("A9_invariants", [])) < 30
    ):
        _append(blockers, "A-DRAFT-BOUNDARY", {"status": draft_a.get("status"), "activation": draft_a.get("activation_state"), "invariants": len(draft_a.get("A9_invariants", []))})

    fixtures = d_corpus.get("fixtures", [])
    fixture_ids = [row.get("fixture_id") for row in fixtures]
    if (
        d_corpus.get("status") != "FROZEN_DRAFT_FIXTURES"
        or len(fixtures) != 10
        or len(fixture_ids) != len(set(fixture_ids))
        or d_corpus.get("closure", {}).get("difference") != 0
        or d_corpus.get("closure", {}).get("material_unclassified_fixtures") != 0
    ):
        _append(blockers, "D-FIXTURE-CLOSURE", d_corpus.get("closure"))

    static_arithmetic = authority_census.get("arithmetic", {})
    if (
        static_arithmetic.get("repository_difference") != 0
        or static_arithmetic.get("producer_difference") != 0
        or static_arithmetic.get("unclassified_authority_planes") != 0
    ):
        _append(blockers, "B-H7-STATIC-ARITHMETIC", static_arithmetic)

    required_negative_tests = [
        "tests/test_authority_boundary_validator.py",
        "tests/test_authority_boundary_quarantine.py",
        "tests/test_identifier_namespace_census_adversarial.py",
        "tests/test_relationship_authority_adversarial.py",
    ]
    missing_tests = [path for path in required_negative_tests if not (root / path).is_file()]
    if missing_tests:
        _append(blockers, "B-H2-H3-NEGATIVE-SUITE-MISSING", missing_tests)
    negative_tests_passed = os.environ.get("AUTHORITY_NEGATIVE_TESTS_PASSED") == "1"
    if not negative_tests_passed:
        _append(blockers, "B-H2-H3-NEGATIVE-SUITE-NOT-EXECUTED", "Set AUTHORITY_NEGATIVE_TESTS_PASSED=1 only after the required pytest suites pass in the same hosted job.")

    critical_paths = [
        "registry/federation/repository_snapshots.json",
        "registry/federation/identifier_namespaces.json",
        "registry/federation/relationship_types.json",
        "registry/federation/authority_matrix.json",
        "registry/federation/source_ownership.json",
        "registry/federation/drift_policy.json",
        "registry/federation/arithmetic_closure.json",
        "registry/federation/authority_boundary_receipt.schema.json",
        "registry/spatial/federation_admin_geometry.manifest.json",
        "registry/spatial/pr_grid_full_cell_index_saturated.manifest.json",
        "scripts/authority_boundary_validator.py",
        "scripts/identifier_namespace_census.py",
        "scripts/validate_authority_boundary.py",
        "tests/test_identifier_namespace_census_adversarial.py",
        "tests/test_relationship_authority_adversarial.py",
        "registry/federation/draft/federation_spatial_entity_contract_1_0.json",
        "tests/fixtures/federation_identity_adversarial/corpus.json",
    ]
    manifest_hashes = {
        path: _sha256(root / path)
        for path in critical_paths
        if (root / path).is_file()
    }

    return {
        "receipt_contract": {"state": "FROZEN", "path": "registry/federation/authority_boundary_receipt.schema.json"},
        "authority_matrix": {"state": matrix.get("state"), "object_count": len(objects), "unclassified": matrix.get("invariants", {}).get("unclassified_authority_objects")},
        "source_ownership": {"state": sources.get("state"), "family_count": len(sources.get("families", [])), "closure": source_closure},
        "drift_policy": {"state": drift.get("state"), "critical_input_count": len(drift.get("critical_inputs", []))},
        "arithmetic_contract": {"state": arithmetic.get("state"), "equation_count": len(arithmetic.get("equations", []))},
        "dormant_certificate": {"state": certificate.get("state"), "successor_phase": certificate.get("successor_phase")},
        "draft_A": {"status": draft_a.get("status"), "activation_state": draft_a.get("activation_state"), "invariant_count": len(draft_a.get("A9_invariants", []))},
        "D_fixture_corpus": {"status": d_corpus.get("status"), "fixture_count": len(fixtures), "closure": d_corpus.get("closure")},
        "negative_tests": {"required": required_negative_tests, "missing": missing_tests, "hosted_job_pass_flag": negative_tests_passed},
        "critical_manifest_sha256": manifest_hashes,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--peer-root", default="_authority_peers")
    parser.add_argument("--report", default="reports/authority_boundary_validation.json")
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    peer_root = Path(args.peer_root).resolve()

    report = validate_base(root, peer_root)

    snapshots = load_json(root / "registry/federation/repository_snapshots.json")
    rows = snapshots.get("repositories", [])
    paths = repository_paths(root, peer_root, rows)
    identifier_registry = load_json(root / "registry/federation/identifier_namespaces.json")
    id_blockers, id_detail = validate_identifier_v2(paths, identifier_registry)
    report["blockers"].extend(id_blockers)
    report["findings"].append({"id": "STRUCTURED_IDENTIFIER_CENSUS_V2", "detail": id_detail})

    max_detail = _validate_max_artifacts(root, report["blockers"])
    report["findings"].append({"id": "PLAN_MAX_PREACTIVATION", "detail": max_detail})

    authority_census = load_json(root / "registry/federation/authority_boundary_census.json")
    report["schema_version"] = "authority_boundary_validation_v4"
    report["authority_plane"] = AUTHORITY
    report["receipt_metadata"] = {
        "validator": "scripts/validate_authority_boundary.py",
        "repository_denominator": 7,
        "producer_denominator": 6,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "receipt_sha256": None,
        "receipt_hash_basis": "canonical JSON with receipt_metadata.receipt_sha256=null",
        "critical_manifest_sha256": max_detail["critical_manifest_sha256"],
    }
    report["repository_snapshot_receipts"] = _finding(report, "REPOSITORY_SNAPSHOT_VERIFICATION") or {}
    report["identifier_namespace_census"] = id_detail
    report["relationship_namespace_census"] = {
        "census": _finding(report, "RELATIONSHIP_LITERAL_CENSUS") or {},
        "resolution": _finding(report, "RELATIONSHIP_LITERAL_RESOLUTION") or {},
        "source_verification": _finding(report, "RELATIONSHIP_REGISTRY_SOURCE_VERIFICATION") or [],
        "python_parse_errors": _finding(report, "RELATIONSHIP_PYTHON_PARSE_ERRORS") or [],
    }
    report["geometry_authority_receipts"] = {"admin": _finding(report, "ADMIN_GEOMETRY_VERIFICATION") or []}
    report["source_ownership_receipts"] = max_detail["source_ownership"]
    report["producer_consumer_receipts"] = {
        "producers": authority_census.get("producers", []),
        "edges": authority_census.get("producer_consumer_edges", []),
    }
    report["authority_leakage_receipts"] = {
        "active_identity_authority_blockers": [row for row in report["blockers"] if str(row.get("id", "")).startswith("AB-001")]
    }
    report["negative_test_receipts"] = max_detail["negative_tests"]

    report["blocker_count"] = len(report["blockers"])
    report["arithmetic_closure"] = {
        "equations": load_json(root / "registry/federation/arithmetic_closure.json").get("equations", []),
        "unclassified": max_detail["authority_matrix"].get("unclassified", 0) or 0,
        "blocked": report["blocker_count"],
        "static_repository_arithmetic": authority_census.get("arithmetic", {}),
    }
    report["certification"] = "AUTHORITY_BOUNDARY_CERTIFIED" if not report["blockers"] else "NOT_CERTIFIED"
    report["next_phase"] = "A_FEDERATION_IDENTITY_CONTRACT" if not report["blockers"] else "BLOCKED"

    hash_basis = json.loads(json.dumps(report))
    hash_basis["receipt_metadata"]["receipt_sha256"] = None
    encoded = json.dumps(hash_basis, sort_keys=True, separators=(",", ":")).encode("utf-8")
    report["receipt_metadata"]["receipt_sha256"] = hashlib.sha256(encoded).hexdigest()

    output = Path(args.report)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not report["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
