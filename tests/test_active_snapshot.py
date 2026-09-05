from __future__ import annotations

import json

import pytest

from control_plane.active_snapshot import ActiveSnapshotError, promote_snapshot, rollback_snapshot


def _manifest(snapshot_id: str, *, decision: str = "PROMOTE", failed: int = 0) -> dict:
    return {
        "snapshot_id": snapshot_id,
        "created_at": "2026-01-01T00:00:00Z",
        "producer_package_versions": {"p": "pkg_x"},
        "record_counts": {"entities": 1},
        "artifact_counts": {"producer_packages": 1},
        "schema_versions": {"snapshot_manifest.v1": "1.0.0"},
        "sha256_manifest": [{"path": "aggregate/entities.jsonl", "sha256": "a" * 64}],
        "failed_record_count": failed,
        "exclusion_ledger": [] if failed == 0 else [{"record_ref": "r", "reason": "bad"}],
        "synthetic_accounting": {"synthetic_count": 0, "test_only_count": 0},
        "index_version": "none",
        "embedding_model_identity": {"model_id": "none", "model_revision": "none", "vector_dim": 1},
        "promotion_decision": {
            "decided_by": "test",
            "decided_at": "2026-01-01T00:00:00Z",
            "decision": decision,
            "reason": "test",
        },
        "rollback_target": None,
    }


def _write_manifest(tmp_path, payload):
    path = tmp_path / (payload["snapshot_id"] + ".json")
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_promote_then_rollback_only_changes_pointer(tmp_path):
    first = _manifest("snap_" + "1" * 32)
    second = _manifest("snap_" + "2" * 32)
    first_path = _write_manifest(tmp_path, first)
    second_path = _write_manifest(tmp_path, second)

    p1 = promote_snapshot(tmp_path / "store", first_path, actor="a", promoted_at="2026-01-01T00:00:01Z")
    p2 = promote_snapshot(tmp_path / "store", second_path, actor="a", promoted_at="2026-01-01T00:00:02Z")
    assert p1["snapshot_id"] == first["snapshot_id"]
    assert p2["previous_snapshot_id"] == first["snapshot_id"]

    restored = rollback_snapshot(
        tmp_path / "store", first["snapshot_id"], actor="a", rolled_back_at="2026-01-01T00:00:03Z"
    )
    assert restored["snapshot_id"] == first["snapshot_id"]
    assert restored["previous_snapshot_id"] == second["snapshot_id"]
    assert restored["transition"] == "ROLLBACK"


def test_failed_promotion_does_not_mutate_existing_active_pointer(tmp_path):
    good = _manifest("snap_" + "1" * 32)
    bad = _manifest("snap_" + "2" * 32, failed=1)
    good_path = _write_manifest(tmp_path, good)
    bad_path = _write_manifest(tmp_path, bad)
    store = tmp_path / "store"
    promote_snapshot(store, good_path, actor="a", promoted_at="2026-01-01T00:00:01Z")
    before = (store / "registry" / "active_snapshot.json").read_bytes()

    with pytest.raises(ActiveSnapshotError, match="failed records"):
        promote_snapshot(store, bad_path, actor="a", promoted_at="2026-01-01T00:00:02Z")

    assert (store / "registry" / "active_snapshot.json").read_bytes() == before


def test_non_promote_decision_cannot_be_activated(tmp_path):
    rejected = _manifest("snap_" + "3" * 32, decision="REJECT")
    path = _write_manifest(tmp_path, rejected)
    with pytest.raises(ActiveSnapshotError, match="not PROMOTE"):
        promote_snapshot(tmp_path / "store", path, actor="a", promoted_at="2026-01-01T00:00:00Z")


def test_existing_immutable_snapshot_symlink_is_rejected(tmp_path):
    manifest = _manifest("snap_" + "4" * 32)
    manifest_path = _write_manifest(tmp_path, manifest)
    store = tmp_path / "store"
    snapshots = store / "registry" / "snapshots"
    snapshots.mkdir(parents=True)
    target = tmp_path / "outside.json"
    target.write_text(json.dumps(manifest), encoding="utf-8")
    (snapshots / f"{manifest['snapshot_id']}.json").symlink_to(target)

    with pytest.raises(ActiveSnapshotError, match="regular file"):
        promote_snapshot(store, manifest_path, actor="a", promoted_at="2026-01-01T00:00:00Z")
