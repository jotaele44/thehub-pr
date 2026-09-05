from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.authority_boundary_validator import (
    AUTHORITY,
    extract_id_signals,
    extract_relationship_literals,
    validate_identifier_census,
    validate_relationship_census,
    verify_geometry,
    verify_repository_snapshots,
)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit_file(root: Path, relative: str, content: str) -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(root, "add", relative)
    git(root, "commit", "-m", f"add {relative}")
    return git(root, "rev-parse", "HEAD")


def init_repository(root: Path) -> None:
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "authority-validator@example.invalid")
    git(root, "config", "user.name", "Authority Validator Test")


def blocker_ids(blockers: list[dict[str, Any]]) -> set[str]:
    return {blocker["id"] for blocker in blockers}


def test_extractors_ignore_generic_yaml_ids_and_prefixes() -> None:
    text = """
- id: ruff
prefix = "NOT_AN_ID_NAMESPACE"
ID_PREFIX = "GOV_"
relationship_type: parent_of
"""
    assert extract_id_signals(text) == {"GOV_"}
    assert extract_relationship_literals(text) == {"parent_of"}
    assert (
        extract_relationship_literals("relationship_type: str", include_bare_yaml=False)
        == set()
    )


def test_identifier_signal_must_resolve_to_exactly_one_repository_namespace() -> None:
    namespaces = [
        {
            "namespace": "MONEYSWEEP_GOVERNMENT_ENTITY",
            "owner": "moneysweep-pr",
            "repository": "jotaele44/moneysweep-pr",
            "pattern": "^GOV_[A-Z0-9]{4,}$",
            "scope": "DOMAIN_ONLY",
        }
    ]
    census = {
        "moneysweep-pr": {
            "GOV_": {"src/known.py"},
            "TOTALLY_NEW_": {"src/unknown.py"},
        }
    }

    blockers, resolutions = validate_identifier_census(census, namespaces)

    assert blocker_ids(blockers) == {"AB-003-UNKNOWN-ID-SIGNAL"}
    assert len(resolutions["moneysweep-pr"]["GOV_"]["candidates"]) == 1
    assert resolutions["moneysweep-pr"]["TOTALLY_NEW_"]["candidates"] == []


def test_relationship_literal_must_be_declared_for_its_emitter() -> None:
    registry = {
        "shared_relationships": [],
        "domain_registries": [
            {
                "owner": "moneysweep-pr",
                "scope": "DOMAIN_ONLY",
                "types": ["parent_of"],
            }
        ],
        "hub_derived": {"owner": "thehub-pr", "scope": "SHARED_DERIVED_CANDIDATE"},
    }
    census = {
        "moneysweep-pr": {
            "parent_of": {"src/known.py"},
            "totally_new": {"src/unknown.py"},
        }
    }

    blockers, resolutions = validate_relationship_census(census, registry)

    assert blocker_ids(blockers) == {"AB-004-UNKNOWN-RELATIONSHIP-LITERAL"}
    assert len(resolutions["moneysweep-pr"]["parent_of"]["candidates"]) == 1
    assert resolutions["moneysweep-pr"]["totally_new"]["candidates"] == []


def test_hub_aggregate_is_observed_but_not_a_second_authority_emitter() -> None:
    registry = {
        "shared_relationships": [],
        "domain_registries": [
            {
                "owner": "moneysweep-pr",
                "scope": "DOMAIN_ONLY",
                "types": ["parent_of"],
            }
        ],
        "hub_derived": {"owner": "thehub-pr", "scope": "SHARED_DERIVED_CANDIDATE"},
    }
    census = {
        "moneysweep-pr": {"parent_of": {"src/producer.py"}},
        "thehub-pr": {"parent_of": {"data/aggregate/relationships.jsonl"}},
    }

    blockers, resolutions = validate_relationship_census(census, registry)

    assert blockers == []
    assert (
        resolutions["thehub-pr"]["parent_of"]["evidence_class"]
        == "CONSUMER_PROJECTION_ONLY"
    )


def test_snapshot_verification_distinguishes_exact_peers_and_candidate_descendants(
    tmp_path: Path,
) -> None:
    peer = tmp_path / "peer"
    candidate = tmp_path / "candidate"
    init_repository(peer)
    init_repository(candidate)
    peer_frozen = commit_file(peer, "peer.txt", "frozen\n")
    candidate_frozen = commit_file(candidate, "candidate.txt", "frozen\n")
    commit_file(candidate, "candidate.txt", "descendant\n")
    rows = [
        {"program_id": "peer-pr", "commit": peer_frozen},
        {"program_id": "thehub-pr", "commit": candidate_frozen},
    ]

    blockers, findings = verify_repository_snapshots(
        rows, {"peer-pr": peer, "thehub-pr": candidate}
    )

    assert blockers == []
    assert findings["peer-pr"]["state"] == "PASS_EXACT"
    assert findings["thehub-pr"]["state"] == "PASS_CANDIDATE_DESCENDANT"

    commit_file(peer, "peer.txt", "advanced\n")
    blockers, _ = verify_repository_snapshots(
        rows, {"peer-pr": peer, "thehub-pr": candidate}
    )
    assert "B-REPO-SNAPSHOT-MISMATCH" in blocker_ids(blockers)

    (candidate / "untracked.txt").write_text("residue\n", encoding="utf-8")
    blockers, _ = verify_repository_snapshots(
        rows, {"peer-pr": peer, "thehub-pr": candidate}
    )
    assert "B-REPO-DIRTY" in blocker_ids(blockers)


def test_geometry_verification_checks_blob_count_type_and_crs(tmp_path: Path) -> None:
    repo = tmp_path / "aguayluz-pr"
    init_repository(repo)
    script = repo / "scripts/build_pr_geo_boundaries.py"
    script.parent.mkdir(parents=True)
    script.write_text("# frozen producer\n", encoding="utf-8")
    geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "one"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                },
            }
        ],
    }
    geometry_path = repo / "data/geo/layer.geojson"
    geometry_path.parent.mkdir(parents=True)
    geometry_path.write_text(json.dumps(geojson), encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "freeze geometry")
    commit = git(repo, "rev-parse", "HEAD")
    script_blob = git(repo, "rev-parse", f"{commit}:scripts/build_pr_geo_boundaries.py")
    geometry_blob = git(repo, "rev-parse", f"{commit}:data/geo/layer.geojson")
    crs = "urn:ogc:def:crs:OGC:1.3:CRS84"
    admin = {
        "authority_plane": AUTHORITY,
        "source_vintage": "2023",
        "canonical_crs": crs,
        "custodial_manifestation": {
            "repository": "jotaele44/aguayluz-pr",
            "commit": commit,
        },
        "source_derivation": {
            "producer_script": "scripts/build_pr_geo_boundaries.py",
            "producer_script_blob_sha": script_blob,
        },
        "layers": [
            {
                "layer_id": "ONE",
                "path": "data/geo/layer.geojson",
                "git_blob_sha": geometry_blob,
                "expected_feature_count": 1,
                "crs": crs,
            },
            {
                "layer_id": "TWO",
                "path": "data/geo/layer.geojson",
                "git_blob_sha": geometry_blob,
                "expected_feature_count": 1,
                "crs": crs,
            },
        ],
    }
    snapshots = {"aguayluz-pr": {"commit": commit}}
    paths = {"aguayluz-pr": repo}

    blockers, findings = verify_geometry(admin, snapshots, paths)

    assert blockers == []
    assert {
        finding["feature_count"] for finding in findings if "feature_count" in finding
    } == {1}
    assert {
        tuple(finding["geometry_types"])
        for finding in findings
        if "geometry_types" in finding
    } == {("Polygon",)}

    bad = copy.deepcopy(admin)
    bad["layers"][0]["git_blob_sha"] = "0" * 40
    bad["layers"][1]["expected_feature_count"] = 2
    bad["layers"][1]["crs"] = "EPSG:4326"
    blockers, _ = verify_geometry(bad, snapshots, paths)
    assert {
        "AB-005-ADMIN-BLOB-MISMATCH",
        "AB-005-ADMIN-COUNT-MISMATCH",
        "AB-005-ADMIN-CRS-MISMATCH",
    }.issubset(blocker_ids(blockers))
