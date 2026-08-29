#!/usr/bin/env python3
"""Freeze a bounded authoritative Puerto Rico river/quebrada name denominator.

Source: Puerto Rico Planning Board SIGE Rios/MapServer/0 (Rios Quebradas).
Every source segment is preserved with its OBJECTID. Exact raw-name families are
also emitted solely as discovery indexes; grouping equal strings is NOT a
canonical feature-identity assertion and does not merge river segments.
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
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from hub.htr import normalize_name  # noqa: E402

LAYER = "https://sige.pr.gov/server/rest/services/Rios/MapServer/0"
USER_AGENT = "thehub-pr-htr/1.0 (+https://github.com/jotaele44/thehub-pr)"
BATCH = 500


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def post_json(url: str, params: dict[str, Any], path: Path, manifest: list[dict[str, Any]]) -> dict[str, Any]:
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
    )
    last: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                payload = response.read()
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            if attempt == 3:
                raise RuntimeError(f"request failed: {url}: {last}") from exc
            time.sleep(2**attempt)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    parsed = json.loads(payload)
    if parsed.get("error"):
        raise RuntimeError(f"ArcGIS error: {parsed['error']}")
    manifest.append(
        {
            "endpoint": url,
            "params": params,
            "retrieval_utc": utc_now(),
            "path": str(path),
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }
    )
    return parsed


def chunks(values: list[int], size: int) -> Iterable[list[int]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/htr_river_denominator")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw_manifest: list[dict[str, Any]] = []
    started = utc_now()

    meta = post_json(LAYER, {"f": "pjson"}, out / "raw" / "metadata.json", raw_manifest)
    fields = {row.get("name") for row in meta.get("fields", [])}
    required = {"OBJECTID", "NAME", "SHAPE_Length"}
    if not required.issubset(fields):
        raise RuntimeError(f"river source schema drift: missing {sorted(required - fields)}")

    ids_doc = post_json(
        f"{LAYER}/query",
        {"where": "1=1", "returnIdsOnly": "true", "f": "pjson"},
        out / "raw" / "ids.json",
        raw_manifest,
    )
    ids = sorted(int(value) for value in (ids_doc.get("objectIds") or []))
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate river OBJECTID in denominator")

    features: list[dict[str, Any]] = []
    for page_no, batch in enumerate(chunks(ids, BATCH)):
        page = post_json(
            f"{LAYER}/query",
            {
                "objectIds": ",".join(str(value) for value in batch),
                "outFields": "OBJECTID,NAME,SHAPE_Length",
                "returnGeometry": "false",
                "f": "pjson",
            },
            out / "raw" / "pages" / f"page_{page_no:04d}.json",
            raw_manifest,
        )
        if page.get("exceededTransferLimit"):
            raise RuntimeError("unexpected transfer-limit truncation in river page")
        features.extend(page.get("features") or [])

    returned = [int((feature.get("attributes") or {})["OBJECTID"]) for feature in features]
    if len(returned) != len(set(returned)) or set(returned) != set(ids):
        raise RuntimeError("river denominator row conservation failed")

    source_rows: list[dict[str, Any]] = []
    named_rows: list[dict[str, Any]] = []
    families: dict[str, list[int]] = defaultdict(list)
    for feature in features:
        attrs = feature.get("attributes") or {}
        oid = int(attrs["OBJECTID"])
        raw = attrs.get("NAME")
        source_rows.append(
            {
                "source_id": "sige:rios-quebradas:0",
                "source_feature_id": oid,
                "raw_name": raw,
                "shape_length": attrs.get("SHAPE_Length"),
                "source_manifestation_identity": f"sige-river-segment:{oid}",
                "canonical_entity_id": None,
                "canonical_identity_state": "UNRESOLVED",
            }
        )
        if not isinstance(raw, str) or not raw.strip():
            continue
        form = normalize_name(raw)
        named_rows.append(
            {
                "source_id": "sige:rios-quebradas:0",
                "source_feature_id": oid,
                "raw_name": raw,
                "normalized_name": form["normalized"],
                "name_core": form["core"],
                "feature_type": "RIVER_OR_QUEBRADA_SEGMENT",
                "source_manifestation_identity": f"sige-river-segment:{oid}",
                "canonical_entity_id": None,
                "canonical_identity_state": "UNRESOLVED",
                "identity_from_equal_name_prohibited": True,
            }
        )
        families[raw].append(oid)

    family_rows = []
    for raw, member_ids in sorted(families.items(), key=lambda item: item[0]):
        form = normalize_name(raw)
        family_rows.append(
            {
                "name_family_id": "river-raw-name:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24],
                "raw_name": raw,
                "normalized_name": form["normalized"],
                "name_core": form["core"],
                "member_source_feature_ids": sorted(member_ids),
                "member_count": len(member_ids),
                "family_semantics": "EXACT_RAW_NAME_BUCKET_NOT_FEATURE_IDENTITY",
                "canonical_entity_id": None,
                "canonical_identity_state": "UNRESOLVED",
            }
        )

    write_jsonl(out / "river_source_rows.jsonl", source_rows)
    write_jsonl(out / "river_named_manifestations.jsonl", named_rows)
    write_jsonl(out / "river_raw_name_families.jsonl", family_rows)
    write_json(out / "raw_manifest.json", raw_manifest)

    summary = {
        "schema_version": "htr-river-denominator-1.0",
        "source_url": LAYER,
        "service_item_id": meta.get("serviceItemId"),
        "retrieval_started_utc": started,
        "retrieval_completed_utc": utc_now(),
        "source_segment_count": len(source_rows),
        "named_segment_manifestation_count": len(named_rows),
        "exact_raw_name_family_count": len(family_rows),
        "row_conservation": "PASS",
        "source_id_uniqueness": "PASS",
        "equal_name_implies_identity": False,
        "canonical_identity_certified": False,
        "scope": "SIGE Rios Quebradas layer only",
        "universal_hydro_name_claim": False,
    }
    write_json(out / "summary.json", summary)

    hashes = []
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        hashes.append(
            {
                "path": str(path.relative_to(out)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    write_json(out / "SHA256SUMS.json", hashes)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
