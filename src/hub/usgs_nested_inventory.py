"""Enumerate nested frozen file references without conflating mirrors with assets."""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

from .usgs_assets import root_membership


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _walk(value, path="", anomalies=None):
    if anomalies is None:
        anomalies = []
    if isinstance(value, dict):
        for key, child in value.items():
            pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key == "files" and path:
                if not isinstance(child, list):
                    anomalies.append(
                        {
                            "json_pointer": pointer,
                            "raw_value": child,
                            "state": "UNRESOLVED",
                        }
                    )
                for ordinal, descriptor in enumerate(
                    child if isinstance(child, list) else []
                ):
                    if not isinstance(descriptor, dict):
                        raise ValueError("Nested file descriptor must be an object")
                    yield pointer + "/" + str(ordinal), descriptor
            yield from _walk(child, pointer, anomalies)
    elif isinstance(value, list):
        for ordinal, child in enumerate(value):
            yield from _walk(child, path + "/" + str(ordinal), anomalies)


def inventory_nested_files(metadata_archive, expected_sha256, baseline, roots):
    """Close all recursive JSON `files` references; leave unique payload binding open."""
    path = Path(metadata_archive)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("Frozen all-item metadata archive mismatch")
    expected = set(roots)
    for edge in baseline["child_edges"]:
        expected.update([edge["parent"], edge["child"]])
    expected.update(a["source_item_id"] for a in baseline["assets"])
    memberships = root_membership(roots, baseline["child_edges"])
    direct = {}
    for a in baseline["assets"]:
        direct.setdefault(
            (a["source_item_id"], _canonical(a["raw_descriptor"])), []
        ).append(a["asset_id"])
    observations, metadata_receipts, anomalies = [], [], []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != {
            sid + ".json" for sid in expected
        }:
            raise ValueError("All-item metadata stable-ID denominator mismatch")
        if sum(i.file_size for i in archive.infolist()) > 64 * 1024 * 1024:
            raise ValueError("Metadata archive capacity exceeded")
        for sid in sorted(expected):
            info = archive.getinfo(sid + ".json")
            if info.file_size > 8 * 1024 * 1024:
                raise ValueError("Metadata item size exceeded")
            raw = archive.read(info)
            item = json.loads(raw)
            if item.get("id") != sid:
                raise ValueError("Metadata requested/returned identity mismatch")
            top = item.get("files", [])
            if not isinstance(top, list):
                raise ValueError("Top-level files field malformed")
            frozen = [
                a["raw_descriptor"]
                for a in baseline["assets"]
                if a["source_item_id"] == sid
            ]
            if _canonical(top) != _canonical(frozen):
                raise ValueError("Top-level descriptor baseline mismatch")
            metadata_receipts.append(
                {
                    "source_item_id": sid,
                    "raw_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
            item_anomalies = []
            discovered = list(_walk(item, anomalies=item_anomalies))
            anomalies.extend({**a, "source_item_id": sid} for a in item_anomalies)
            for pointer, descriptor in discovered:
                matches = direct.get((sid, _canonical(descriptor)), [])
                observations.append(
                    {
                        "reference_id": sid + "#" + pointer,
                        "source_item_id": sid,
                        "json_pointer": pointer,
                        "root_release_ids": memberships.get(sid, []),
                        "raw_descriptor": descriptor,
                        "exact_top_level_descriptor_matches": matches,
                        "binding_scope": "Exact logical descriptor only; not independent payload identity",
                        "payload_state": "UNVERIFIED",
                        "activation_state": "BLOCKED",
                    }
                )
    if len({r["reference_id"] for r in observations}) != len(observations):
        raise ValueError("Nested reference identity collision")
    return {
        "contract": "prii.usgs-nested-file-inventory/v1",
        "metadata_enumeration_state": "OPEN" if anomalies else "PASS",
        "array_reference_enumeration_state": "PASS",
        "non_array_files_fields": anomalies,
        "non_array_files_field_count": len(anomalies),
        "scope": "Recursive files arrays in all 463 frozen item JSONs; not arbitrary URLs or services",
        "metadata_archive_sha256": expected_sha256,
        "metadata_item_count": len(expected),
        "top_level_baseline_references": baseline["file_count"],
        "nested_reference_observations": len(observations),
        "combined_reference_observations": baseline["file_count"] + len(observations),
        "reference_locations": dict(
            Counter(r["json_pointer"].split("/")[1] for r in observations)
        ),
        "exact_top_level_descriptor_match_observations": sum(
            bool(r["exact_top_level_descriptor_matches"]) for r in observations
        ),
        "unique_asset_binding_state": "UNRESOLVED",
        "full_payload_closure": "OPEN",
        "warning": "Reference observations include potential mirrors; do not sum them as unique assets",
        "metadata_receipts": metadata_receipts,
        "references": observations,
        "activated": 0,
        "activation_state": "BLOCKED",
    }
