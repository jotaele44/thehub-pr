#!/usr/bin/env python3
"""Strict offline package contract validator for the Federation Hub.

This validator is dependency-free and complements JSON Schema with cross-file
checks that JSON Schema cannot cover cleanly: required package files, dashboard
self-containment, CSV evidence columns, package checksum presence, and ZIP
contents.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

EXPECTED_REPOS = {
    "thehub-pr",
    "skywatcher-pr",
    "moneysweep-pr",
    "aguayluz-pr",
    "centinelas-pr",
    "ovnis-pr",
    "spiderweb-pr",
}

REQUIRED_FILES = [
    "manifest.json",
    "readiness.json",
    "blockers.json",
    "sources.json",
    "evidence_ledger.csv",
    "operator_report.md",
    "dashboard.html",
    "package.sha256",
]

EVIDENCE_COLUMNS = [
    "evidence_id",
    "repo",
    "evidence_tier",
    "claim",
    "artifact_path",
    "artifact_type",
    "generated_by",
    "validation_status",
    "sha256",
    "notes",
]

STATUS = {"green", "yellow", "red", "critical", "unknown"}
EVIDENCE_TIERS = {"T1", "T2", "T3", "T4"}
DATA_MODES = {"diagnostic_seed", "live", "mixed", "unknown"}
PRODUCTION_STATUS = {"diagnostic", "staging", "production_blocked", "production_candidate", "production"}
NODE_TYPES = {"hub", "producer"}
BLOCKER_SEVERITY = {"critical", "high", "medium", "low"}
BLOCKER_STATUS = {"open", "resolved", "accepted_risk"}
SOURCE_ACCESS = {"manual", "rss", "api", "upload", "derived", "unknown"}
SOURCE_SCOPE = {"puerto_rico", "caribbean", "us_federal", "global", "mixed", "unknown"}
SOURCE_AUTHORITY = {"official", "institutional", "media", "community", "derived", "unknown"}
SOURCE_CADENCE = {"daily", "weekly", "monthly", "event_driven", "unknown"}
SOURCE_STATUS = {"active", "candidate", "deprecated", "unavailable"}
GATE_STATUS = {"pass", "fail", "unknown", "not_applicable"}


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path}: invalid json: {exc}")
        return {}


def check(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(root: Path, errors: list[str]) -> str:
    manifest = load_json(root / "manifest.json", errors)
    repo = str(manifest.get("repo", ""))
    check(manifest.get("schema_version") == "federation.offline_package.v1", errors, "manifest.schema_version mismatch")
    check(repo in EXPECTED_REPOS, errors, f"manifest.repo unexpected: {repo}")
    check(manifest.get("node_type") in NODE_TYPES, errors, "manifest.node_type invalid")
    check(manifest.get("data_mode") in DATA_MODES, errors, "manifest.data_mode invalid")
    check(manifest.get("production_status") in PRODUCTION_STATUS, errors, "manifest.production_status invalid")
    check(manifest.get("offline_ready") is True, errors, "manifest.offline_ready must be true")
    check(manifest.get("localhost_required") is False, errors, "manifest.localhost_required must be false")

    summary = manifest.get("summary", {})
    for key in ["records", "sources", "blockers_open", "critical_blockers_open", "evidence_items"]:
        check(isinstance(summary.get(key), (int, float)) and summary.get(key) >= 0, errors, f"manifest.summary.{key} invalid")

    gates = manifest.get("gates", {})
    for key in ["tests", "schema_validation", "export_generated", "offline_dashboard_generated", "hub_ingest_compatible"]:
        check(gates.get(key) in GATE_STATUS, errors, f"manifest.gates.{key} invalid")

    for entry in manifest.get("files", []):
        path = entry.get("path")
        digest = entry.get("sha256")
        check(isinstance(path, str) and bool(path), errors, "manifest.files path missing")
        check(isinstance(digest, str) and len(digest) == 64, errors, f"manifest.files sha invalid for {path}")
    return repo


def validate_readiness(root: Path, repo: str, errors: list[str]) -> None:
    data = load_json(root / "readiness.json", errors)
    check(data.get("schema_version") == "federation.readiness.v1", errors, "readiness.schema_version mismatch")
    check(data.get("repo") == repo, errors, "readiness.repo does not match manifest")
    check(data.get("overall_status") in STATUS, errors, "readiness.overall_status invalid")
    pct = data.get("overall_completion_pct")
    check(isinstance(pct, (int, float)) and 0 <= pct <= 100, errors, "readiness.overall_completion_pct invalid")
    dims = data.get("dimensions", [])
    check(isinstance(dims, list) and len(dims) > 0, errors, "readiness.dimensions empty")
    for dim in dims:
        check(dim.get("status") in STATUS, errors, f"readiness dimension status invalid: {dim.get('id')}")
        dpct = dim.get("completion_pct")
        check(isinstance(dpct, (int, float)) and 0 <= dpct <= 100, errors, f"readiness dimension pct invalid: {dim.get('id')}")
        check(isinstance(dim.get("blockers"), list), errors, f"readiness dimension blockers not list: {dim.get('id')}")
        check(isinstance(dim.get("evidence_refs"), list), errors, f"readiness dimension evidence_refs not list: {dim.get('id')}")


def validate_blockers(root: Path, repo: str, errors: list[str]) -> None:
    data = load_json(root / "blockers.json", errors)
    check(data.get("schema_version") == "federation.blockers.v1", errors, "blockers.schema_version mismatch")
    check(data.get("repo") == repo, errors, "blockers.repo does not match manifest")
    for item in data.get("blockers", []):
        check(item.get("severity") in BLOCKER_SEVERITY, errors, f"blocker severity invalid: {item.get('id')}")
        check(item.get("status") in BLOCKER_STATUS, errors, f"blocker status invalid: {item.get('id')}")
        for key in ["id", "scope", "title", "impact", "resolution"]:
            check(isinstance(item.get(key), str) and bool(item.get(key)), errors, f"blocker.{key} missing")
        check(isinstance(item.get("evidence_refs"), list), errors, f"blocker evidence_refs not list: {item.get('id')}")


def validate_sources(root: Path, repo: str, errors: list[str]) -> None:
    data = load_json(root / "sources.json", errors)
    check(data.get("schema_version") == "federation.sources.v1", errors, "sources.schema_version mismatch")
    check(data.get("repo") == repo, errors, "sources.repo does not match manifest")
    for source in data.get("sources", []):
        check(source.get("access_method") in SOURCE_ACCESS, errors, f"source access invalid: {source.get('source_id')}")
        check(source.get("scope") in SOURCE_SCOPE, errors, f"source scope invalid: {source.get('source_id')}")
        check(source.get("authority_level") in SOURCE_AUTHORITY, errors, f"source authority invalid: {source.get('source_id')}")
        check(source.get("cadence") in SOURCE_CADENCE, errors, f"source cadence invalid: {source.get('source_id')}")
        check(source.get("status") in SOURCE_STATUS, errors, f"source status invalid: {source.get('source_id')}")
        for key in ["source_id", "name", "category", "notes"]:
            check(isinstance(source.get(key), str), errors, f"source.{key} invalid")


def validate_evidence(root: Path, repo: str, errors: list[str]) -> None:
    path = root / "evidence_ledger.csv"
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            check(reader.fieldnames == EVIDENCE_COLUMNS, errors, "evidence_ledger.csv columns mismatch")
            for row in reader:
                check(row.get("repo") == repo, errors, f"evidence repo mismatch: {row.get('evidence_id')}")
                check(row.get("evidence_tier") in EVIDENCE_TIERS, errors, f"evidence tier invalid: {row.get('evidence_id')}")
    except Exception as exc:
        errors.append(f"evidence_ledger.csv unreadable: {exc}")


def validate_dashboard(root: Path, errors: list[str]) -> None:
    text = (root / "dashboard.html").read_text(encoding="utf-8", errors="replace").lower()
    external_tokens = ["http" + "://", "https" + "://", "//cdn.", "cdnjs", "unpkg", "jsdelivr"]
    for token in external_tokens:
        check(token not in text, errors, f"dashboard external dependency detected: {token}")
    check("<script" in text, errors, "dashboard.html missing embedded script/data surface")


def validate_package(root: Path, repo: str, errors: list[str]) -> None:
    checksum_path = root / "package.sha256"
    try:
        checksum_text = checksum_path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        errors.append(f"package.sha256 unreadable: {exc}")
        return
    zips = sorted(root.glob("*_federation_package.zip"))
    check(len(zips) == 1, errors, "expected exactly one federation package zip")
    if not zips:
        return
    zip_path = zips[0]
    check(zip_path.name in checksum_text, errors, "package.sha256 does not name package zip")
    check(sha256(zip_path) in checksum_text, errors, "package.sha256 digest mismatch")
    expected_inside = {f"federation/{name}" for name in REQUIRED_FILES if name != "package.sha256"}
    expected_inside.add(f"federation/{repo}_federation_package.zip")
    try:
        with zipfile.ZipFile(zip_path) as bundle:
            names = set(bundle.namelist())
        for required in expected_inside:
            if required.endswith("_federation_package.zip"):
                continue
            check(required in names, errors, f"package missing {required}")
    except Exception as exc:
        errors.append(f"package zip unreadable: {exc}")


def validate_package_dir(root: Path) -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_FILES:
        check((root / name).exists(), errors, f"missing {name}")
    if errors:
        return errors
    repo = validate_manifest(root, errors)
    validate_readiness(root, repo, errors)
    validate_blockers(root, repo, errors)
    validate_sources(root, repo, errors)
    validate_evidence(root, repo, errors)
    validate_dashboard(root, errors)
    validate_package(root, repo, errors)
    return errors


def discover(root: Path) -> list[Path]:
    if (root / "manifest.json").exists():
        return [root]
    return sorted(root.glob("*/exports/federation"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="exports/federation", help="single package dir or workspace root")
    args = parser.parse_args()
    roots = discover(Path(args.root))
    if not roots:
        print("FAIL: no offline package directories found", file=sys.stderr)
        return 1
    failed = False
    for package_root in roots:
        errors = validate_package_dir(package_root)
        label = str(package_root)
        if errors:
            failed = True
            print(f"[FAIL] {label}", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"[PASS] {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
