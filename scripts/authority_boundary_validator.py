#!/usr/bin/env python3
"""Fail-closed B.1-B.5 federation authority-boundary validator."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

AUTHORITY = "prii-federation-spatial-identity"
TEXT_EXTS = {
    ".js",
    ".json",
    ".jsonl",
    ".jsx",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
SKIP_PARTS = {
    ".git",
    ".github",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "docs",
    "fixtures",
    "node_modules",
    "reports",
    "test",
    "tests",
    "venv",
}
ID_SIGNAL_RE = re.compile(
    r"\b(?:ID_PREFIX|id_prefix|uid_prefix|visual_id_prefix)\s*[:=]\s*[\"']([^\"']+)[\"']"
)
RELATIONSHIP_LITERAL_RES = (
    re.compile(r"[\"']relationship_type[\"']\s*:\s*[\"']([^\"']+)[\"']"),
    re.compile(r"\brelationship_type\s*=\s*[\"']([^\"']+)[\"']"),
)
YAML_RELATIONSHIP_LITERAL_RE = re.compile(
    r"^\s*relationship_type\s*:\s*[\"']?([A-Za-z0-9_.:/-]+)", re.MULTILINE
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_census_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTS:
            continue
        relative = path.relative_to(root)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        try:
            yield path, path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue


def extract_id_signals(text: str) -> set[str]:
    return {value for value in ID_SIGNAL_RE.findall(text) if 1 <= len(value) <= 96}


def extract_relationship_literals(
    text: str, include_bare_yaml: bool = True
) -> set[str]:
    values: set[str] = set()
    for pattern in RELATIONSHIP_LITERAL_RES:
        values.update(pattern.findall(text))
    if include_bare_yaml:
        values.update(YAML_RELATIONSHIP_LITERAL_RE.findall(text))
    return {value for value in values if 1 <= len(value) <= 96 and "{" not in value}


def regex_literal_prefix(pattern: str) -> str:
    if not pattern.startswith("^"):
        return ""
    literals: list[str] = []
    index = 1
    metacharacters = set(".[$(){}*+?|")
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 1
            if index >= len(pattern) or pattern[index].isalnum():
                break
            literals.append(pattern[index])
        elif char in metacharacters:
            break
        else:
            literals.append(char)
        index += 1
    return "".join(literals)


def namespace_accepts_signal(namespace: dict[str, Any], signal: str) -> bool:
    prefix = regex_literal_prefix(str(namespace.get("pattern", "")))
    if not prefix:
        return False
    return signal.rstrip("-_.:") == prefix.rstrip("-_.:")


def _git(
    root: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(detail)
    return result


def repository_paths(
    root: Path, peer_root: Path, rows: list[dict[str, Any]]
) -> dict[str, Path]:
    return {
        "thehub-pr": root,
        **{
            row["program_id"]: peer_root / row["program_id"]
            for row in rows
            if row["program_id"] != "thehub-pr"
        },
    }


def verify_repository_snapshots(
    rows: list[dict[str, Any]], paths: dict[str, Path]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    findings: dict[str, Any] = {}
    for row in rows:
        program_id = row["program_id"]
        expected = row["commit"]
        path = paths.get(program_id)
        detail = {
            "expected_commit": expected,
            "path": str(path) if path else None,
            "verification": "EXACT"
            if program_id != "thehub-pr"
            else "CANDIDATE_DESCENDANT",
        }
        if path is None or not path.exists():
            detail["state"] = "MISSING"
            findings[program_id] = detail
            blockers.append(
                {"id": "B-REPO-MISSING", "detail": {"repo": program_id, **detail}}
            )
            continue
        try:
            head = _git(path, "rev-parse", "HEAD").stdout.strip()
            dirty = _git(
                path, "status", "--porcelain", "--untracked-files=all"
            ).stdout.splitlines()
            object_check = _git(
                path, "cat-file", "-e", f"{expected}^{{commit}}", check=False
            )
        except RuntimeError as exc:
            detail.update({"state": "GIT_ERROR", "error": str(exc)})
            findings[program_id] = detail
            blockers.append(
                {"id": "B-REPO-GIT-ERROR", "detail": {"repo": program_id, **detail}}
            )
            continue
        detail.update({"actual_head": head, "dirty_paths": dirty})
        if object_check.returncode != 0:
            blockers.append(
                {
                    "id": "B-REPO-SNAPSHOT-OBJECT-MISSING",
                    "detail": {"repo": program_id, **detail},
                }
            )
            detail["state"] = "SNAPSHOT_OBJECT_MISSING"
        elif dirty:
            blockers.append(
                {"id": "B-REPO-DIRTY", "detail": {"repo": program_id, **detail}}
            )
            detail["state"] = "DIRTY"
        elif program_id == "thehub-pr":
            ancestor = _git(
                path, "merge-base", "--is-ancestor", expected, head, check=False
            )
            if ancestor.returncode != 0:
                blockers.append(
                    {
                        "id": "B-REPO-SNAPSHOT-MISMATCH",
                        "detail": {"repo": program_id, **detail},
                    }
                )
                detail["state"] = "NOT_DESCENDED_FROM_SNAPSHOT"
            else:
                detail["state"] = "PASS_CANDIDATE_DESCENDANT"
        elif head != expected:
            blockers.append(
                {
                    "id": "B-REPO-SNAPSHOT-MISMATCH",
                    "detail": {"repo": program_id, **detail},
                }
            )
            detail["state"] = "HEAD_MISMATCH"
        else:
            detail["state"] = "PASS_EXACT"
        findings[program_id] = detail
    return blockers, findings


def verify_geometry(
    admin: dict[str, Any],
    snapshots: dict[str, dict[str, Any]],
    paths: dict[str, Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    manifestation = admin.get("custodial_manifestation", {})
    repository = str(manifestation.get("repository", ""))
    program_id = repository.rsplit("/", 1)[-1]
    snapshot = snapshots.get(program_id)
    repo_root = paths.get(program_id)
    commit = manifestation.get("commit")
    canonical_crs = admin.get("canonical_crs")
    if (
        admin.get("authority_plane") != AUTHORITY
        or admin.get("source_vintage") != "2023"
        or canonical_crs != "urn:ogc:def:crs:OGC:1.3:CRS84"
        or len(admin.get("layers", [])) != 2
    ):
        blockers.append(
            {
                "id": "AB-005-ADMIN-MANIFEST",
                "detail": {
                    "authority_plane": admin.get("authority_plane"),
                    "source_vintage": admin.get("source_vintage"),
                    "canonical_crs": canonical_crs,
                    "layer_count": len(admin.get("layers", [])),
                },
            }
        )
    if snapshot is None or commit != snapshot.get("commit"):
        blockers.append(
            {
                "id": "AB-005-CUSTODIAL-SNAPSHOT-MISMATCH",
                "detail": {
                    "program_id": program_id,
                    "manifest_commit": commit,
                    "snapshot": snapshot,
                },
            }
        )
    if repo_root is None or not repo_root.exists() or not isinstance(commit, str):
        blockers.append(
            {"id": "AB-005-CUSTODIAL-CHECKOUT-MISSING", "detail": program_id}
        )
        return blockers, findings

    derivation = admin.get("source_derivation", {})
    script_path = derivation.get("producer_script")
    script_blob = derivation.get("producer_script_blob_sha")
    if isinstance(script_path, str) and isinstance(script_blob, str):
        actual_script_blob = _git(
            repo_root, "rev-parse", f"{commit}:{script_path}", check=False
        )
        actual = (
            actual_script_blob.stdout.strip()
            if actual_script_blob.returncode == 0
            else None
        )
        findings.append(
            {
                "kind": "PRODUCER_SCRIPT",
                "path": script_path,
                "declared_blob": script_blob,
                "actual_blob": actual,
            }
        )
        if actual != script_blob:
            blockers.append(
                {"id": "AB-005-PRODUCER-SCRIPT-PIN", "detail": findings[-1]}
            )

    for layer in admin.get("layers", []):
        relative = layer.get("path")
        declared_blob = layer.get("git_blob_sha")
        expected_count = layer.get("expected_feature_count")
        detail: dict[str, Any] = {
            "kind": "GEOMETRY_LAYER",
            "layer_id": layer.get("layer_id"),
            "path": relative,
            "declared_blob": declared_blob,
            "expected_feature_count": expected_count,
            "declared_crs": layer.get("crs"),
        }
        if not isinstance(relative, str) or not isinstance(declared_blob, str):
            blockers.append({"id": "AB-005-ADMIN-PIN", "detail": detail})
            findings.append(detail)
            continue
        file_path = repo_root / relative
        commit_blob_result = _git(
            repo_root, "rev-parse", f"{commit}:{relative}", check=False
        )
        worktree_blob_result = _git(repo_root, "hash-object", relative, check=False)
        commit_blob = (
            commit_blob_result.stdout.strip()
            if commit_blob_result.returncode == 0
            else None
        )
        worktree_blob = (
            worktree_blob_result.stdout.strip()
            if worktree_blob_result.returncode == 0
            else None
        )
        detail.update({"commit_blob": commit_blob, "worktree_blob": worktree_blob})
        if (
            not file_path.is_file()
            or declared_blob != commit_blob
            or commit_blob != worktree_blob
        ):
            blockers.append(
                {"id": "AB-005-ADMIN-BLOB-MISMATCH", "detail": detail.copy()}
            )
            findings.append(detail)
            continue
        try:
            geojson = load_json(file_path)
        except (OSError, json.JSONDecodeError) as exc:
            detail["parse_error"] = str(exc)
            blockers.append(
                {"id": "AB-005-ADMIN-GEOJSON-INVALID", "detail": detail.copy()}
            )
            findings.append(detail)
            continue
        features = geojson.get("features") if isinstance(geojson, dict) else None
        if not isinstance(features, list):
            detail["feature_count"] = None
            blockers.append(
                {"id": "AB-005-ADMIN-GEOJSON-INVALID", "detail": detail.copy()}
            )
            findings.append(detail)
            continue
        geometry_types = sorted(
            {
                geometry_type
                for feature in features
                if isinstance(feature, dict)
                and isinstance(feature.get("geometry"), dict)
                for geometry_type in [feature["geometry"].get("type")]
                if isinstance(geometry_type, str)
            }
        )
        invalid_geometry = sum(
            1
            for feature in features
            if not isinstance(feature, dict)
            or not isinstance(feature.get("geometry"), dict)
            or feature["geometry"].get("type") not in {"Polygon", "MultiPolygon"}
        )
        file_crs = (
            geojson.get("crs", {}).get("properties", {}).get("name")
            if isinstance(geojson, dict)
            else None
        )
        detail.update(
            {
                "feature_count": len(features),
                "geometry_types": geometry_types,
                "invalid_geometry_count": invalid_geometry,
                "file_crs": file_crs,
            }
        )
        if len(features) != expected_count:
            blockers.append(
                {"id": "AB-005-ADMIN-COUNT-MISMATCH", "detail": detail.copy()}
            )
        if invalid_geometry:
            blockers.append(
                {"id": "AB-005-ADMIN-GEOMETRY-INVALID", "detail": detail.copy()}
            )
        if layer.get("crs") != canonical_crs or file_crs != canonical_crs:
            blockers.append(
                {"id": "AB-005-ADMIN-CRS-MISMATCH", "detail": detail.copy()}
            )
        findings.append(detail)
    return blockers, findings


def validate_identifier_census(
    census: dict[str, dict[str, set[str]]], namespaces: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    resolutions: dict[str, Any] = {}
    for program_id, signals in sorted(census.items()):
        resolutions[program_id] = {}
        for signal, sources in sorted(signals.items()):
            candidates = [
                row for row in namespaces if namespace_accepts_signal(row, signal)
            ]
            summaries = [
                {
                    "namespace": row.get("namespace"),
                    "owner": row.get("owner"),
                    "repository": row.get("repository"),
                    "scope": row.get("scope"),
                }
                for row in candidates
            ]
            resolution = {"sources": sorted(sources), "candidates": summaries}
            resolutions[program_id][signal] = resolution
            if not candidates:
                blockers.append(
                    {
                        "id": "AB-003-UNKNOWN-ID-SIGNAL",
                        "detail": {"repo": program_id, "signal": signal, **resolution},
                    }
                )
            elif len(candidates) > 1:
                blockers.append(
                    {
                        "id": "AB-003-AMBIGUOUS-ID-SIGNAL",
                        "detail": {"repo": program_id, "signal": signal, **resolution},
                    }
                )
            else:
                registered_program = str(candidates[0].get("repository", "")).rsplit(
                    "/", 1
                )[-1]
                if registered_program != program_id:
                    blockers.append(
                        {
                            "id": "AB-003-ID-SIGNAL-OWNER-MISMATCH",
                            "detail": {
                                "repo": program_id,
                                "signal": signal,
                                **resolution,
                            },
                        }
                    )
    return blockers, resolutions


def relationship_registry_index(
    registry: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in registry.get("shared_relationships", []):
        index[row["id"]].append(
            {
                "owner": row.get("authority_owner"),
                "scope": row.get("scope"),
                "registry": "shared_relationships",
            }
        )
    for row in registry.get("domain_registries", []):
        for value in {*row.get("types", []), *row.get("families", [])}:
            index[value].append(
                {
                    "owner": row.get("owner"),
                    "scope": row.get("scope"),
                    "registry": "domain_registries",
                }
            )
    hub = registry.get("hub_derived", {})
    for value in {*hub.get("types", []), *hub.get("families", [])}:
        index[value].append(
            {
                "owner": hub.get("owner"),
                "scope": hub.get("scope"),
                "registry": "hub_derived",
            }
        )
    return index


def validate_relationship_census(
    census: dict[str, dict[str, set[str]]], registry: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    resolutions: dict[str, Any] = {}
    index = relationship_registry_index(registry)
    emitters_by_literal: dict[str, set[str]] = defaultdict(set)
    for program_id, literals in sorted(census.items()):
        resolutions[program_id] = {}
        for literal, sources in sorted(literals.items()):
            candidates = index.get(literal, [])
            producer_sources = {
                source
                for source in sources
                if not (
                    program_id == "thehub-pr" and source.startswith("data/aggregate/")
                )
            }
            resolution = {
                "sources": sorted(sources),
                "producer_sources": sorted(producer_sources),
                "evidence_class": (
                    "CONSUMER_PROJECTION_ONLY"
                    if not producer_sources
                    else "PRODUCER_OR_EXECUTABLE"
                ),
                "candidates": candidates,
            }
            resolutions[program_id][literal] = resolution
            if producer_sources:
                emitters_by_literal[literal].add(program_id)
            if not candidates:
                blockers.append(
                    {
                        "id": "AB-004-UNKNOWN-RELATIONSHIP-LITERAL",
                        "detail": {
                            "repo": program_id,
                            "literal": literal,
                            **resolution,
                        },
                    }
                )
                continue
            if len(candidates) != 1:
                blockers.append(
                    {
                        "id": "AB-004-AMBIGUOUS-RELATIONSHIP-LITERAL",
                        "detail": {
                            "repo": program_id,
                            "literal": literal,
                            **resolution,
                        },
                    }
                )
                continue
            candidate = candidates[0]
            shared = (
                candidate.get("owner") == AUTHORITY
                and candidate.get("scope") == "SHARED"
            )
            if producer_sources and candidate.get("owner") != program_id and not shared:
                blockers.append(
                    {
                        "id": "AB-004-RELATIONSHIP-OWNER-MISMATCH",
                        "detail": {
                            "repo": program_id,
                            "literal": literal,
                            **resolution,
                        },
                    }
                )
    for literal, emitters in sorted(emitters_by_literal.items()):
        candidates = index.get(literal, [])
        explicitly_shared = (
            len(candidates) == 1
            and candidates[0].get("owner") == AUTHORITY
            and candidates[0].get("scope") == "SHARED"
        )
        if len(emitters) > 1 and not explicitly_shared:
            blockers.append(
                {
                    "id": "AB-004-CROSS-PRODUCER-COLLISION",
                    "detail": {"literal": literal, "repositories": sorted(emitters)},
                }
            )
    return blockers, resolutions


def collect_census(paths: dict[str, Path]) -> tuple[dict[str, Any], dict[str, Any]]:
    identifier_census: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    relationship_census: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for program_id, repo_root in paths.items():
        if not repo_root.exists():
            continue
        identifier_census[program_id]
        relationship_census[program_id]
        for path, text in iter_census_files(repo_root):
            relative = str(path.relative_to(repo_root))
            for signal in extract_id_signals(text):
                identifier_census[program_id][signal].add(relative)
            for literal in extract_relationship_literals(
                text, include_bare_yaml=path.suffix.lower() in {".yaml", ".yml"}
            ):
                relationship_census[program_id][literal].add(relative)
    return identifier_census, relationship_census


def validate(root: Path, peer_root: Path) -> dict[str, Any]:
    snapshots_document = load_json(
        root / "registry/federation/repository_snapshots.json"
    )
    identifier_registry = load_json(
        root / "registry/federation/identifier_namespaces.json"
    )
    relationship_registry = load_json(
        root / "registry/federation/relationship_types.json"
    )
    quarantine = load_json(
        root / "registry/federation/legacy_identity_registry_quarantine.json"
    )
    grid = load_json(
        root / "registry/spatial/pr_grid_full_cell_index_saturated.manifest.json"
    )
    admin = load_json(root / "registry/spatial/federation_admin_geometry.manifest.json")

    blockers: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    rows = snapshots_document.get("repositories", [])
    program_ids = [row.get("program_id") for row in rows]
    expected_programs = {
        "aguayluz-pr",
        "centinelas-pr",
        "moneysweep-pr",
        "ovnis-pr",
        "skywatcher-pr",
        "spiderweb-pr",
        "thehub-pr",
    }
    if (
        snapshots_document.get("denominator") != 7
        or len(rows) != 7
        or len(set(program_ids)) != 7
        or set(program_ids) != expected_programs
    ):
        blockers.append({"id": "B-REPO-DENOMINATOR", "detail": program_ids})
    paths = repository_paths(root, peer_root, rows)
    snapshot_blockers, snapshot_findings = verify_repository_snapshots(rows, paths)
    blockers.extend(snapshot_blockers)
    findings.append(
        {"id": "REPOSITORY_SNAPSHOT_VERIFICATION", "detail": snapshot_findings}
    )

    if (
        quarantine.get("state") != "LEGACY_NONAUTHORITATIVE_TEST_FIXTURE"
        or quarantine.get("superseding_authority") != AUTHORITY
    ):
        blockers.append({"id": "AB-001-BAD-QUARANTINE", "detail": quarantine})
    production_imports = []
    for path, text in iter_census_files(root / "src"):
        if path.as_posix().endswith("src/hub/identity_registry.py"):
            continue
        if (
            "hub.identity_registry" in text
            or "from .identity_registry" in text
            or "import identity_registry" in text
        ):
            production_imports.append(str(path.relative_to(root)))
    if production_imports:
        blockers.append(
            {"id": "AB-001-ACTIVE-HUB-AUTHORITY", "detail": production_imports}
        )
    authority_leaks = []
    for program_id, repo_root in paths.items():
        if not repo_root.exists():
            continue
        for path, text in iter_census_files(repo_root):
            relative = str(path.relative_to(repo_root))
            if program_id == "thehub-pr" and relative in {
                quarantine.get("path"),
                "registry/federation/legacy_identity_registry_quarantine.json",
            }:
                continue
            if re.search(r'FEDERATION_AUTHORITY\s*=\s*["\']thehub-pr["\']', text):
                authority_leaks.append({"repo": program_id, "path": relative})
    if authority_leaks:
        blockers.append(
            {"id": "AB-001-OTHER-AUTHORITY-LEAK", "detail": authority_leaks}
        )

    if (
        grid.get("canonical_ground_geometry") is not False
        or grid.get("georeferenced") is not False
    ):
        blockers.append({"id": "AB-002-GRID", "detail": grid.get("status")})
    snapshots = {row["program_id"]: row for row in rows}
    geometry_blockers, geometry_findings = verify_geometry(admin, snapshots, paths)
    blockers.extend(geometry_blockers)
    findings.append({"id": "ADMIN_GEOMETRY_VERIFICATION", "detail": geometry_findings})

    namespaces = identifier_registry.get("namespaces", [])
    namespace_names = [row.get("namespace") for row in namespaces]
    if len(namespace_names) != len(set(namespace_names)):
        blockers.append({"id": "AB-003-DUPLICATE-NAMESPACE"})
    for namespace in namespaces:
        try:
            re.compile(namespace["pattern"])
        except (KeyError, re.error) as exc:
            blockers.append(
                {
                    "id": "AB-003-BAD-REGEX",
                    "detail": {
                        "namespace": namespace.get("namespace"),
                        "error": str(exc),
                    },
                }
            )
        if not regex_literal_prefix(str(namespace.get("pattern", ""))):
            blockers.append({"id": "AB-003-NONPREFIX-REGEX", "detail": namespace})
        if (
            namespace.get("scope") in {"SHARED_IDENTITY", "SHARED_RELATIONSHIP"}
            and namespace.get("owner") != AUTHORITY
        ):
            blockers.append({"id": "AB-003-SHARED-OWNER", "detail": namespace})

    identifier_census, relationship_census = collect_census(paths)
    identifier_blockers, identifier_resolutions = validate_identifier_census(
        identifier_census, namespaces
    )
    blockers.extend(identifier_blockers)
    findings.append(
        {
            "id": "ID_SIGNAL_CENSUS",
            "detail": {
                program_id: {
                    signal: sorted(sources)
                    for signal, sources in sorted(signals.items())
                }
                for program_id, signals in sorted(identifier_census.items())
            },
        }
    )
    findings.append({"id": "ID_SIGNAL_RESOLUTION", "detail": identifier_resolutions})
    if identifier_registry.get("census_state") != "EXHAUSTIVE_CRAWLER_RECONCILED":
        blockers.append(
            {
                "id": "AB-003-CENSUS-NOT-RECONCILED",
                "detail": identifier_registry.get("census_state"),
            }
        )

    relationship_blockers, relationship_resolutions = validate_relationship_census(
        relationship_census, relationship_registry
    )
    blockers.extend(relationship_blockers)
    findings.append(
        {
            "id": "RELATIONSHIP_LITERAL_CENSUS",
            "detail": {
                program_id: {
                    literal: sorted(sources)
                    for literal, sources in sorted(literals.items())
                }
                for program_id, literals in sorted(relationship_census.items())
            },
        }
    )
    findings.append(
        {"id": "RELATIONSHIP_LITERAL_RESOLUTION", "detail": relationship_resolutions}
    )
    if relationship_registry.get("census_state") != "EXHAUSTIVE_CRAWLER_RECONCILED":
        blockers.append(
            {
                "id": "AB-004-CENSUS-NOT-RECONCILED",
                "detail": relationship_registry.get("census_state"),
            }
        )

    return {
        "schema_version": "authority_boundary_validation_v2",
        "authority_plane": AUTHORITY,
        "repository_denominator": len(rows),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "findings": findings,
        "certification": "AUTHORITY_BOUNDARY_CERTIFIED"
        if not blockers
        else "NOT_CERTIFIED",
        "next_phase": "A_FEDERATION_IDENTITY_CONTRACT" if not blockers else "BLOCKED",
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--peer-root", default="_authority_peers")
    parser.add_argument(
        "--report", default="reports/authority_boundary_validation.json"
    )
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    peer_root = Path(args.peer_root).resolve()
    report = validate(root, peer_root)
    output = Path(args.report)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not report["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
