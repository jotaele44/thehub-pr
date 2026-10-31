from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from hub.bridge import write_manifest
from hub.validate import validate_package

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "data" / "aggregate" / "moneysweep" / "full_package_current_receipt.json"
ID_FIELDS = {
    "sources": "source_id",
    "entities": "entity_id",
    "relationships": "relationship_id",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def test_exact_current_moneysweep_full_package_replay(tmp_path: Path) -> None:
    package_root_raw = os.environ.get("PRII_MONEYSWEEP_FULL_PACKAGE_ROOT")
    producer_commit = os.environ.get("PRII_MONEYSWEEP_FULL_PACKAGE_COMMIT")
    if not package_root_raw:
        pytest.skip("strict cross-repository full-package replay not enabled")

    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    package_root = Path(package_root_raw)

    assert producer_commit == receipt["producerCommit"]
    assert _sha256(package_root / "manifest.json") == receipt["producerManifestSha256"]

    producer_manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    assert producer_manifest["package_id"] == receipt["producerPackageId"]
    assert producer_manifest["producer"] == receipt["producer"]

    producer_files = {
        row["stream"]: row
        for row in producer_manifest["files"]
        if row["stream"] in ID_FIELDS
    }
    expected_streams = {row["stream"]: row for row in receipt["streams"]}
    assert set(producer_files) == set(expected_streams)

    total_records = 0
    wrapped_dir = tmp_path / "wrapped"
    wrapped_dir.mkdir()

    for stream, expected in expected_streams.items():
        source_path = package_root / expected["filename"]
        assert source_path.exists()
        assert _sha256(source_path) == expected["sha256"]

        rows = _jsonl_rows(source_path)
        total_records += len(rows)
        assert len(rows) == expected["recordCount"]

        id_field = ID_FIELDS[stream]
        ids = [row[id_field] for row in rows]
        assert len(ids) == len(set(ids))

        manifest_row = producer_files[stream]
        assert manifest_row["record_count"] == expected["recordCount"]
        assert manifest_row["sha256"] == expected["sha256"]
        assert manifest_row["schema_id"] == expected["schemaId"]

        shutil.copy2(source_path, wrapped_dir / expected["filename"])

    assert total_records == receipt["accounting"]["totalRecords"]

    wrapped = write_manifest(
        wrapped_dir,
        receipt["producer"],
        mode=receipt["mode"],
        created_at=receipt["createdAt"],
    )
    assert wrapped["package_id"] == receipt["producerPackageId"]
    assert _sha256(wrapped_dir / "manifest.json") == receipt["hubWrappedManifestSha256"]

    errors = validate_package(wrapped_dir)
    assert errors == []
