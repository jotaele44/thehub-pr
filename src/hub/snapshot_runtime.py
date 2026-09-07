"""Deterministic builder for the frozen ``snapshot_manifest.v1`` contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contract_runtime import validate_contract
from .validate import validate_package

_JSONL_STREAMS = {
    "sources",
    "entities",
    "relationships",
    "funding_awards",
    "transactions",
    "observations",
    "alerts",
    "correlations",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _iter_jsonl(path: Path):
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            yield json.loads(raw)


def build_snapshot_manifest(
    packages: Mapping[str, Path],
    aggregate_dir,
    *,
    created_at: str,
    decided_by: str,
    decided_at: str,
    decision: str = "PROMOTE",
    decision_reason: str = "validated deterministic federation snapshot",
    rollback_target: str | None = None,
    exclusion_ledger: Iterable[Mapping[str, str]] = (),
    failed_record_count: int = 0,
    operational: bool = True,
    index_version: str = "none",
    embedding_model_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate one frozen content-addressed snapshot manifest.

    Producer packages are validated before inclusion. Snapshot identity is derived
    only from producer package identities, artifact hashes, aggregate record counts,
    exclusion accounting and schema versions; timestamps and promotion actor do not
    influence the identifier. This makes equivalent rebuilds byte-addressable even
    when promotion occurs at different times.
    """
    aggregate = Path(aggregate_dir)
    errors: dict[str, list[str]] = {}
    package_versions: dict[str, str] = {}
    sha_rows: list[dict[str, str]] = []

    for producer in sorted(packages):
        pkg = Path(packages[producer])
        errs = validate_package(pkg)
        if errs:
            errors[producer] = errs
            continue
        manifest_path = pkg / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("producer") != producer:
            errors[producer] = [
                f"producer mismatch: mapping={producer!r} manifest={manifest.get('producer')!r}"
            ]
            continue
        package_versions[producer] = str(
            manifest.get("package_id") or manifest.get("export_contract_version") or ""
        )
        sha_rows.append(
            {"path": f"packages/{producer}/manifest.json", "sha256": _sha256(manifest_path)}
        )
        for entry in sorted(manifest.get("files", []), key=lambda item: str(item.get("filename"))):
            filename = str(entry["filename"])
            path = pkg / filename
            sha_rows.append(
                {"path": f"packages/{producer}/{filename}", "sha256": _sha256(path)}
            )

    if errors:
        raise ValueError("producer package validation failed: " + json.dumps(errors, sort_keys=True))

    record_counts: dict[str, int] = {}
    synthetic_count = 0
    test_only_count = 0
    aggregate_artifacts = 0
    if aggregate.exists():
        for path in sorted(p for p in aggregate.iterdir() if p.is_file()):
            sha_rows.append({"path": f"aggregate/{path.name}", "sha256": _sha256(path)})
            aggregate_artifacts += 1
            if path.suffix == ".jsonl" and path.stem in _JSONL_STREAMS:
                rows = list(_iter_jsonl(path))
                record_counts[path.stem] = len(rows)
                for row in rows:
                    if row.get("synthetic") is True:
                        synthetic_count += 1
                    if row.get("synthetic_status") == "TEST_ONLY":
                        test_only_count += 1

    exclusions = sorted(
        ({"record_ref": str(item["record_ref"]), "reason": str(item["reason"])}
         for item in exclusion_ledger),
        key=lambda item: (item["record_ref"], item["reason"]),
    )
    if failed_record_count != len(exclusions):
        raise ValueError(
            "failed_record_count must equal exclusion_ledger length so no failed record is unaccounted"
        )
    if operational and (synthetic_count or test_only_count):
        raise ValueError(
            "operational snapshot cannot contain synthetic or TEST_ONLY aggregate records"
        )

    sha_rows.sort(key=lambda item: item["path"])
    schema_versions = {
        "snapshot_manifest.v1": "1.0.0",
        "provenance.v1": "1.0.0",
        "entity_resolution.v1": "1.0.0",
    }
    identity_material = {
        "producer_package_versions": package_versions,
        "record_counts": record_counts,
        "sha256_manifest": sha_rows,
        "failed_record_count": failed_record_count,
        "exclusion_ledger": exclusions,
        "synthetic_accounting": {
            "synthetic_count": synthetic_count,
            "test_only_count": test_only_count,
        },
        "schema_versions": schema_versions,
    }
    snapshot_id = "snap_" + hashlib.sha256(_canonical_bytes(identity_material)).hexdigest()[:32]

    model_identity = dict(embedding_model_identity or {
        "model_id": "none",
        "model_revision": "none",
        "vector_dim": 1,
    })
    manifest = {
        "snapshot_id": snapshot_id,
        "created_at": created_at,
        "producer_package_versions": package_versions,
        "record_counts": record_counts,
        "artifact_counts": {
            "producer_packages": len(package_versions),
            "aggregate_artifacts": aggregate_artifacts,
            "hashed_artifacts": len(sha_rows),
        },
        "schema_versions": schema_versions,
        "sha256_manifest": sha_rows,
        "failed_record_count": failed_record_count,
        "exclusion_ledger": exclusions,
        "synthetic_accounting": {
            "synthetic_count": synthetic_count,
            "test_only_count": test_only_count,
        },
        "index_version": index_version,
        "embedding_model_identity": model_identity,
        "promotion_decision": {
            "decided_by": decided_by,
            "decided_at": decided_at,
            "decision": decision,
            "reason": decision_reason,
        },
        "rollback_target": rollback_target,
    }
    validate_contract("snapshot_manifest.v1", manifest)
    return manifest


__all__ = ["build_snapshot_manifest"]
