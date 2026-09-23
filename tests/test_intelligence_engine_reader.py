from __future__ import annotations

import json

from control_plane.active_snapshot import promote_snapshot
from hub.snapshot_runtime import build_snapshot_manifest
from intelligence_engine.query import QuerySpec
from intelligence_engine.reader import ActiveSnapshotReader

_TS = "2026-01-01T00:00:00Z"


def _entity(eid: str, *, entity_type: str = "recipient") -> dict:
    return {
        "entity_id": eid,
        "source_id": "src_" + "a" * 32,
        "name": "Example",
        "normalized_name": "EXAMPLE",
        "entity_type": entity_type,
        "jurisdiction": "PR",
        "confidence": 0.9,
        "lineage": {
            "producer_script": "test",
            "producer_phase": "TEST",
            "source_inputs": ["fixture"],
        },
        "synthetic": False,
        "created_at": _TS,
        "extracted_at": _TS,
    }


def _promoted_reader(tmp_path, rows):
    aggregate = tmp_path / "aggregate"
    aggregate.mkdir()
    (aggregate / "entities.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8"
    )
    manifest = build_snapshot_manifest(
        {}, aggregate, created_at=_TS, decided_by="test", decided_at=_TS
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    store = tmp_path / "store"
    promote_snapshot(store, manifest_path, actor="test", promoted_at=_TS)
    return ActiveSnapshotReader(store, aggregate_dir=aggregate)


def test_no_active_snapshot_abstains_snapshot_incomplete(tmp_path):
    reader = ActiveSnapshotReader(tmp_path / "store", aggregate_dir=tmp_path / "aggregate")
    result = reader.get_object("ent_" + "a" * 32)
    assert result["abstention"]["status"] == "SNAPSHOT_INCOMPLETE"
    assert result["objects"] == []


def test_exact_id_hit_returns_canonical_record(tmp_path):
    eid = "ent_" + "a" * 32
    reader = _promoted_reader(tmp_path, [_entity(eid)])

    result = reader.get_object(eid)
    assert result["abstention"]["status"] == "ANSWERED"
    assert len(result["objects"]) == 1
    obj = result["objects"][0]
    assert obj["object_type"] == "CanonicalRecord"
    assert obj["object_id"] == eid
    assert obj["fields"]["entity_id"] == eid
    assert obj["provenance"]["snapshot_id"].startswith("snap_")


def test_exact_id_miss_abstains_insufficient_evidence(tmp_path):
    reader = _promoted_reader(tmp_path, [_entity("ent_" + "a" * 32)])
    result = reader.get_object("ent_" + "f" * 32)
    assert result["abstention"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["objects"] == []


def test_structured_query_filters_by_field(tmp_path):
    reader = _promoted_reader(
        tmp_path,
        [
            _entity("ent_" + "a" * 32, entity_type="recipient"),
            _entity("ent_" + "b" * 32, entity_type="project"),
        ],
    )
    result = reader.query(QuerySpec(mode="STRUCTURED", stream="entities", filters={"entity_type": "project"}))
    assert result["abstention"]["status"] == "ANSWERED"
    assert [obj["object_id"] for obj in result["objects"]] == ["ent_" + "b" * 32]


def test_structured_query_no_match_abstains_insufficient_evidence(tmp_path):
    reader = _promoted_reader(tmp_path, [_entity("ent_" + "a" * 32, entity_type="recipient")])
    result = reader.query(QuerySpec(mode="STRUCTURED", stream="entities", filters={"entity_type": "nonexistent"}))
    assert result["abstention"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["objects"] == []


def test_corrupted_aggregate_file_abstains_retrieval_failure(tmp_path):
    eid = "ent_" + "a" * 32
    aggregate = tmp_path / "aggregate"
    aggregate.mkdir()
    (aggregate / "entities.jsonl").write_text(json.dumps(_entity(eid), sort_keys=True) + "\n", encoding="utf-8")
    manifest = build_snapshot_manifest({}, aggregate, created_at=_TS, decided_by="test", decided_at=_TS)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    store = tmp_path / "store"
    promote_snapshot(store, manifest_path, actor="test", promoted_at=_TS)

    (aggregate / "entities.jsonl").write_text("tampered content\n", encoding="utf-8")

    reader = ActiveSnapshotReader(store, aggregate_dir=aggregate)
    result = reader.get_object(eid)
    assert result["abstention"]["status"] == "RETRIEVAL_FAILURE"
    assert result["objects"] == []
