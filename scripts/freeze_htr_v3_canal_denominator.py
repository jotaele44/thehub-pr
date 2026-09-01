#!/usr/bin/env python3
"""Freeze the bounded SIGE Canal de Riego denominator for HTR v3.

This replaces no prior artifact. The original Puerto Rico GIS / AEE Isabela
SHAPE-ZIP acquisition attempt is retained as BLOCKED_NETWORK_TIMEOUT in its
workflow receipt. This source is a separately authoritative Puerto Rico
Planning Board SIGE manifestation with island-wide Canal de Riego rows.

Rows with the same `canal` value remain separate source segments. Exact RAW name
families are discovery buckets only; equal names never establish feature or
cross-source identity, and the layer cannot establish hydraulic connectivity by
name/proximity alone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

LAYER = "https://sige.pr.gov/server/rest/services/MIPR/AgricolaPUT_v10_N/FeatureServer/1"
SERVICE_ITEM_ID = "8f28013ad1db40b08a2f75de44ad1412"
USER_AGENT = "thehub-pr-htr-v3-canal/1.0 (+https://github.com/jotaele44/thehub-pr)"
FIELDS = ["OBJECTID", "canal", "Shape__Length"]
BATCH = 500


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def post(url: str, params: dict[str, Any], *, attempts: int = 4) -> bytes:
    encoded = urllib.parse.urlencode(params, doseq=True).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
    )
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt == attempts:
                break
            time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"request failed after {attempts} attempts: {url}: {last}")


def freeze_json(url: str, params: dict[str, Any], path: Path, raw: list[dict[str, Any]]) -> dict[str, Any]:
    payload = post(url, params)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    try:
        doc = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"non-JSON response from {url}; preserved at {path}") from exc
    if not isinstance(doc, dict):
        raise RuntimeError(f"non-object JSON response from {url}")
    if doc.get("error"):
        raise RuntimeError(f"ArcGIS source error: {doc['error']}")
    raw.append({
        "url": url,
        "params": params,
        "retrieval_utc": utc_now(),
        "path": str(path),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    })
    return doc


def chunks(values: list[int], size: int = BATCH) -> Iterable[list[int]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/htr_v3_canal")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw: list[dict[str, Any]] = []
    started = utc_now()

    metadata = freeze_json(LAYER, {"f": "pjson"}, out / "raw" / "metadata.json", raw)
    if metadata.get("serviceItemId") != SERVICE_ITEM_ID:
        raise RuntimeError(f"service item drift: {metadata.get('serviceItemId')!r}")
    field_names = {row.get("name") for row in metadata.get("fields", [])}
    missing = sorted(set(FIELDS) - field_names)
    if missing:
        raise RuntimeError(f"schema drift; missing fields: {missing}")
    if metadata.get("geometryType") != "esriGeometryPolyline":
        raise RuntimeError(f"unexpected geometry type: {metadata.get('geometryType')!r}")

    query = f"{LAYER}/query"
    count_doc = freeze_json(query, {"where": "1=1", "returnCountOnly": "true", "f": "json"}, out / "raw" / "count.json", raw)
    expected_count = int(count_doc.get("count", -1))
    ids_doc = freeze_json(query, {"where": "1=1", "returnIdsOnly": "true", "f": "json"}, out / "raw" / "ids.json", raw)
    object_ids = sorted(int(value) for value in (ids_doc.get("objectIds") or []))
    if expected_count != len(object_ids) or len(object_ids) != len(set(object_ids)):
        raise RuntimeError(f"count/ID conservation failed: count={expected_count} ids={len(object_ids)} unique={len(set(object_ids))}")

    features: list[dict[str, Any]] = []
    for page_no, batch in enumerate(chunks(object_ids)):
        page = freeze_json(
            query,
            {
                "objectIds": ",".join(map(str, batch)),
                "outFields": ",".join(FIELDS),
                "returnGeometry": "true",
                "outSR": "6566",
                "f": "json",
            },
            out / "raw" / "pages" / f"page_{page_no:04d}.json",
            raw,
        )
        if page.get("exceededTransferLimit"):
            raise RuntimeError("unexpected exceededTransferLimit on exact object-ID page")
        features.extend(page.get("features") or [])

    returned_ids: list[int] = []
    rows: list[dict[str, Any]] = []
    families: dict[str, list[int]] = {}
    for feature in features:
        attrs = feature.get("attributes") or {}
        oid = int(attrs["OBJECTID"])
        returned_ids.append(oid)
        raw_name = attrs.get("canal")
        if not isinstance(raw_name, str) or not raw_name:
            raise RuntimeError(f"source OBJECTID {oid} has blank/non-string canal despite non-null schema")
        families.setdefault(raw_name, []).append(oid)
        rows.append({
            "source_observation_id": f"sigecanal:{oid}",
            "source_id": "sige:mipr-agricola-put:canal-de-riego:1",
            "source_feature_id": oid,
            "raw_name": raw_name,
            "normalized_name": raw_name.casefold(),
            "canonical_entity_id": None,
            "cross_source_identity_state": "UNRESOLVED",
            "discovery_key_status": "SUPPORTED",
            "identity_claim": False,
            "connectivity_claim": False,
            "shape_length": attrs.get("Shape__Length"),
            "geometry": feature.get("geometry"),
        })
    if len(returned_ids) != len(set(returned_ids)) or set(returned_ids) != set(object_ids):
        raise RuntimeError("returned source-row identity conservation failed")

    family_rows = [
        {
            "raw_name": name,
            "segment_count": len(ids),
            "source_feature_ids": sorted(ids),
            "canonical_entity_id": None,
            "identity_state": "UNRESOLVED",
            "equal_name_implies_feature_identity": False,
            "discovery_key_status": "SUPPORTED",
        }
        for name, ids in sorted(families.items())
    ]
    write_jsonl(out / "canal_source_rows.jsonl", rows)
    write_jsonl(out / "canal_raw_name_families.jsonl", family_rows)
    write_json(out / "raw_manifest.json", raw)
    summary = {
        "schema_version": "htr-v3-sige-canal-denominator-1.0",
        "started_utc": started,
        "completed_utc": utc_now(),
        "source_url": LAYER,
        "service_item_id": SERVICE_ITEM_ID,
        "source_row_count": len(rows),
        "raw_name_family_count": len(family_rows),
        "row_conservation": "PASS",
        "source_id_uniqueness": "PASS",
        "canonical_identity_certified": False,
        "connectivity_certified": False,
        "equal_name_implies_feature_identity": False,
        "universal_irrigation_asset_exhaustion_claimed": False,
        "certification": "PASS",
    }
    write_json(out / "summary.json", summary)
    hashes = {
        str(path.relative_to(out)): sha256_file(path)
        for path in sorted(out.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS.json"
    }
    write_json(out / "SHA256SUMS.json", hashes)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
