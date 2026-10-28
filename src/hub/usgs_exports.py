"""Independent validation of frozen documentary producer exports; no activation."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path

from .usgs_assets import root_membership, verify_payload
from .validate import validate_package


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def assess_usgs_export(package_dir, input_manifest, source_root):
    """Validate bytes, schema, stable-key membership and whole native features."""
    pkg, root = Path(package_dir), Path(source_root).resolve()
    spec_raw = Path(input_manifest).read_bytes()
    spec = json.loads(spec_raw)
    if (
        spec.get("contract") != "prii.usgs-native-producer-input/v1"
        or spec.get("producer") != "spiderweb-pr"
        or spec.get("mode") != "test"
        or spec.get("activation_state") != "BLOCKED"
        or not spec.get("open_gates")
    ):
        raise ValueError("Expected blocked source-native test input")
    receipt = json.loads(
        (root / "registry/usgs/continuation_evidence.v1.json").read_text()
    )
    frozen = (root / "data/usgs/continuation_inventory.v1.json.gz").read_bytes()
    if _sha(frozen) != receipt["compressed_inventory_sha256"]:
        raise ValueError("Frozen inventory container mismatch")
    inventory_raw = gzip.decompress(frozen)
    if (
        _sha(inventory_raw) != receipt["inventory_sha256"]
        or _sha(inventory_raw) != spec["source_inventory_sha256"]
    ):
        raise ValueError("Frozen inventory/source binding mismatch")
    inventory = json.loads(inventory_raw)
    inventory_assets = {a["asset_id"]: a for a in inventory["assets"]}
    catalog = json.loads((root / "registry/usgs/pr_releases.v1.json").read_text())
    memberships = root_membership(
        [r["sciencebase_id"] for r in catalog["releases"]], inventory["child_edges"]
    )
    manifest_raw = (pkg / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest.get("producer") != "spiderweb-pr" or manifest.get("mode") != "test":
        raise ValueError("Producer identity/mode mismatch")
    if manifest.get("federation") != {
        "producer_repo": "spiderweb-pr",
        "hub_parent": "thehub-pr",
    }:
        raise ValueError("Producer handshake mismatch")
    files = manifest.get("files", [])
    if (
        len(files) != 2
        or {f.get("filename") for f in files} != {"sources.jsonl", "observations.jsonl"}
        or {f.get("stream") for f in files} != {"sources", "observations"}
        or any(f["filename"] != f["stream"] + ".jsonl" for f in files)
    ):
        raise ValueError("Unexpected export stream membership")
    package_digest = _sha(
        ("|".join(f"{f['filename']}:{f['sha256']}" for f in files) + "|test").encode()
    )[:32]
    if manifest.get("package_id") != "pkg_" + package_digest:
        raise ValueError("Deterministic producer package ID mismatch")
    errors = validate_package(pkg)
    if errors:
        raise ValueError(
            "Canonical package validation failed: " + "; ".join(errors[:4])
        )
    audit = json.loads((pkg / "usgs_export_audit.json").read_text())
    if (
        audit.get("manifest_sha256") != _sha(manifest_raw)
        or audit.get("input_manifest_sha256") != _sha(spec_raw)
        or audit.get("activation_state") != "BLOCKED"
        or audit.get("production_export_state") != "BLOCKED"
        or audit.get("activated") != 0
    ):
        raise ValueError("Export audit source/manifest binding mismatch")
    expected, observed = {}, {}
    assets = {}
    for asset in spec["assets"]:
        aid = asset["asset_id"]
        if aid in assets:
            raise ValueError("Duplicate input asset")
        original = inventory_assets[aid]
        if (
            original["payload_state"] != "PASS"
            or original["raw_descriptor"] != asset["source_descriptor_raw"]
            or original["verification"]["sha256"] != asset["raw_sha256"]
            or original["transport"]["retrieval_utc"] != asset["retrieval_utc"]
            or original["source_item_id"] != asset["source_item_id"]
            or memberships[original["source_item_id"]] != asset["root_release_ids"]
        ):
            raise ValueError("Input manifest differs from frozen source evidence")
        assets[aid] = asset
        path = (root / asset["raw_file"]).resolve()
        path.relative_to(root)
        packed = path.read_bytes()
        if _sha(packed) != asset["packed_sha256"]:
            raise ValueError("Packed input hash mismatch")
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as source:
            raw = source.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise ValueError("Source capacity exceeded")
        verify_payload(raw, asset["source_descriptor_raw"])
        if _sha(raw) != asset["raw_sha256"]:
            raise ValueError("Raw input hash mismatch")
        native = json.loads(raw)
        if len(native["features"]) != asset["expected_features"]:
            raise ValueError("Native feature count mismatch")
        for feature in native["features"]:
            key = feature["properties"][asset["source_key"]]
            identity = _canonical([aid, type(key).__name__, key])
            if identity in expected:
                raise ValueError("Duplicate native primary key")
            expected[identity] = _canonical(
                [feature, {k: v for k, v in native.items() if k != "features"}]
            )
    sources = [
        json.loads(line) for line in (pkg / "sources.jsonl").read_text().splitlines()
    ]
    by_source = {s["source_id"]: s for s in sources}
    if len(by_source) != len(sources) or len(sources) != len(assets):
        raise ValueError("Source identity/count mismatch")
    ids = set()
    used_sources = set()
    for line in (pkg / "observations.jsonl").read_text().splitlines():
        row = json.loads(line)
        attrs = row["attributes"]
        aid, key = attrs["asset_id"], attrs["source_key_raw"]
        asset = assets[aid]
        identity = _canonical([aid, type(key).__name__, key])
        if identity in observed or row["observation_id"] in ids:
            raise ValueError("Duplicate export identity")
        ids.add(row["observation_id"])
        observed[identity] = _canonical(
            [attrs["native_feature"], attrs["native_collection_metadata"]]
        )
        if (
            row.get("observation_type") != "usgs_feature_source_snapshot"
            or any(
                row.get(k) != asset["retrieval_utc"]
                for k in ("observed_at", "created_at", "extracted_at")
            )
            or attrs.get("timestamp_semantics")
            != "SOURCE_RETRIEVAL_ONLY_NOT_GEOLOGICAL_EVENT"
            or attrs.get("confidence_semantics")
            != "UNASSESSED_DOMAIN_CONFIDENCE_NOT_BYTE_VERIFICATION"
            or row.get("synthetic") is not False
            or row.get("confidence") != 0.0
            or "location" in row
            or "geometry" in row
            or "geo" in row
            or "evidence_state" in row
            or row["source_id"] not in by_source
            or attrs.get("activation_state") != "BLOCKED"
            or attrs.get("semantic_state") != "OPEN"
            or attrs.get("spatial_state") != "UNRESOLVED"
            or attrs.get("production_export_state") != "BLOCKED"
            or attrs.get("source_key_field") != asset["source_key"]
            or attrs.get("root_release_ids") != asset["root_release_ids"]
        ):
            raise ValueError(
                "Unreviewed semantic/spatial promotion or lineage mismatch"
            )
        expected_source = (
            "src_"
            + _sha(
                json.dumps(
                    ["spiderweb-pr", aid, asset["raw_sha256"]],
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
            )[:32]
        )
        expected_id = (
            "obs_"
            + _sha(
                json.dumps(
                    ["spiderweb-pr", aid, asset["raw_sha256"], type(key).__name__, key],
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
            )[:32]
        )
        if row["source_id"] != expected_source or row["observation_id"] != expected_id:
            raise ValueError("Content-scoped producer ID mismatch")
        used_sources.add(row["source_id"])
        source = by_source[row["source_id"]]
        if (
            source.get("source_ref") != asset["source_descriptor_raw"]["downloadUri"]
            or source.get("source_type") != "usgs_source_snapshot"
            or source.get("synthetic") is not False
            or source.get("confidence") != 0.0
            or any(
                source.get(k) != asset["retrieval_utc"]
                for k in ("created_at", "extracted_at")
            )
            or "sha256:" + asset["raw_sha256"] not in source["lineage"]["source_inputs"]
            or "sha256:" + asset["raw_sha256"] not in row["lineage"]["source_inputs"]
        ):
            raise ValueError("Source/observation content-addressed lineage mismatch")
    if used_sources != set(by_source):
        raise ValueError("Orphaned export source")
    a, b = set(expected), set(observed)
    membership = {
        "intersection": len(a & b),
        "a_only": len(a - b),
        "b_only": len(b - a),
        "union": len(a | b),
        "symmetric_difference": len(a ^ b),
    }
    if a != b or any(expected[k] != observed[k] for k in a & b):
        raise ValueError("Native feature membership or whole-row conservation mismatch")
    if (
        audit.get("feature_count") != len(expected)
        or audit.get("source_count") != len(sources)
        or audit.get("asset_count") != len(assets)
    ):
        raise ValueError("Export audit denominator mismatch")
    return {
        "contract": "prii.usgs-export-validation/v1",
        "state": "PASS",
        "scope": "Frozen TEST-MODE producer export bytes/schema/identities/native feature conservation",
        "producer": "spiderweb-pr",
        "manifest_sha256": _sha(manifest_raw),
        "input_manifest_sha256": _sha(spec_raw),
        "asset_count": len(assets),
        "inventory_file_count": inventory["file_count"],
        "sources": len(sources),
        "features": len(expected),
        "membership": membership,
        "canonical_locations_emitted": 0,
        "activation_state": "BLOCKED",
        "production_export_state": "BLOCKED",
        "activated": 0,
        "open_gates": spec["open_gates"],
        "reason": "Test package validity does not close domain or production gates",
    }
