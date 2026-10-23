"""Projects raw canonical aggregate rows into ``retrieval_object.v1`` CanonicalRecord objects.

KNOWN GAP: no producer or pipeline in this repo populates ``access_classification``
on aggregate rows today (verified against every row shape in ``data/aggregate/*.jsonl``).
Objects built here therefore stamp a conservative placeholder classification
(``INTERNAL``) with an explicit ``reason`` documenting the default. This is not a
real access decision and must not be wired into a ``PolicyDecider`` surface as if
it were authoritative until the Evidence Engine actually classifies rows.

Likewise, no row carries a real ``evidence_tier`` outside of a few streams'
``attributes.evidence_tier``; where absent, ``UNSPECIFIED`` is stamped with
``tier_source="provisional machine suggestion"`` / ``tier_review_status="PROVISIONAL"``
— i.e. explicitly marked as not yet adjudicated, never silently upgraded.
"""
from __future__ import annotations

from typing import Any, Mapping

from hub._schemas import STREAM_ID_FIELD
from hub.contract_runtime import validate_contract

_ACCESS_DEFAULT_REASON = (
    "access_classification absent from source row; defaulted conservatively "
    "pending Evidence Engine population (see intelligence_engine.objects docstring)"
)


def _artifact_sha256(manifest: Mapping[str, Any], stream: str) -> str:
    for entry in manifest["sha256_manifest"]:
        if entry["path"] == f"aggregate/{stream}.jsonl":
            return str(entry["sha256"])
    raise KeyError(f"no aggregate artifact hash recorded for stream {stream!r}")


def _provenance(row: Mapping[str, Any], *, stream: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
    attributes = row.get("attributes") or {}
    evidence_tier = str(attributes.get("evidence_tier") or "UNSPECIFIED")
    synthetic_status = row.get("synthetic_status") or ("SYNTHETIC" if row.get("synthetic") else "REAL")
    producers = row.get("_producers") or [str(row.get("source_id", "unknown"))]
    return {
        "producer_id": ",".join(sorted(str(p) for p in producers)),
        "canonical_stream": stream,
        "artifact_sha256": _artifact_sha256(manifest, stream),
        "snapshot_id": manifest["snapshot_id"],
        "schema_version": manifest["schema_versions"].get("provenance.v1", "1.0.0"),
        "evidence_tier": evidence_tier,
        "tier_authority": {
            "tier_value": evidence_tier,
            "tier_source": "provisional machine suggestion",
            "tier_review_status": "PROVISIONAL",
        },
        "synthetic_status": synthetic_status,
        "access_classification": {"level": "INTERNAL", "reason": _ACCESS_DEFAULT_REASON},
    }


def canonical_record_object(
    row: Mapping[str, Any], *, stream: str, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    """Build and validate one ``retrieval_object.v1`` CanonicalRecord for ``row``."""
    id_field = STREAM_ID_FIELD[stream]
    obj = {
        "object_type": "CanonicalRecord",
        "object_id": str(row[id_field]),
        "provenance": _provenance(row, stream=stream, manifest=manifest),
        "canonical_stream": stream,
        "fields": dict(row),
    }
    validate_contract("retrieval_object.v1", obj)
    return obj


__all__ = ["canonical_record_object"]
