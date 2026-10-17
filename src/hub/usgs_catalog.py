"""Read-only USGS release catalog. Catalog admission never admits payloads."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "registry/usgs/pr_releases.v1.json"


def validate_catalog(catalog):
    rows = catalog["releases"]
    ids = [row["sciencebase_id"] for row in rows]
    if len(ids) != len(set(ids)) or len(rows) != catalog["counts"]["included"]:
        raise ValueError("Release ID uniqueness or denominator failed")
    excluded = catalog["excluded"]
    excluded_ids = [row["sciencebase_id"] for row in excluded]
    if len(excluded_ids) != len(set(excluded_ids)) or set(ids) & set(excluded_ids):
        raise ValueError("Excluded IDs collide")
    if len(excluded) != catalog["counts"]["excluded"]:
        raise ValueError("Excluded denominator failed")
    if dict(Counter(row["raw"]["Category"] for row in rows)) != catalog["counts"]["categories"]:
        raise ValueError("Category arithmetic failed")
    programs = {p["program_id"]: p["repo"] for p in catalog["repositories"]}
    for row in rows:
        if row["activation_state"] != "BLOCKED" or row["payload_verified"] is not False:
            raise ValueError("This catalog contract cannot activate payloads")
        if not row["raw"]["ScienceBase URL"].endswith("/" + row["sciencebase_id"]):
            raise ValueError("Source URL/ID binding failed")
        for target in row["consumer_candidates"]:
            if programs.get(target["program_id"]) != target["repository"]:
                raise ValueError("Unknown repository binding")
            if target["state"] != "CANDIDATE_NOT_IDENTITY":
                raise ValueError("Unreviewed consumer promoted")
    return catalog


def load_catalog(path=CATALOG):
    catalog = validate_catalog(json.loads(Path(path).read_text(encoding="utf-8")))
    source = ROOT / "data/usgs/source/usgs_data_releases_puerto_rico.xlsx"
    if hashlib.sha256(source.read_bytes()).hexdigest() != catalog["source"]["sha256"]:
        raise ValueError("Frozen workbook hash mismatch")
    return catalog


def catalog_page(catalog, query="", program=None, offset=0, limit=50):
    validate_catalog(catalog)
    if offset < 0 or not 1 <= limit <= 200:
        raise ValueError("Invalid pagination")
    programs = {p["program_id"] for p in catalog["repositories"]}
    if program is not None and program not in programs:
        raise ValueError("Unknown program")
    rows = catalog["releases"]
    if program:
        rows = [r for r in rows if any(c["program_id"] == program for c in r["consumer_candidates"])]
    if query:
        term = query.casefold()
        rows = [r for r in rows if term in json.dumps(r["raw"], ensure_ascii=False).casefold()
                or term in r["sciencebase_id"]]
    selected = rows[offset:offset + limit]
    return {"contract": catalog["contract"], "records": selected, "total": len(rows),
            "next_offset": offset + len(selected) if offset + len(selected) < len(rows) else None,
            "counts": catalog["counts"], "source": catalog["source"],
            "issues": catalog["issues"], "repositories": catalog["repositories"],
            "catalog_state": "PASS", "payload_state": "BLOCKED",
            "catalog_sha256": hashlib.sha256(json.dumps(catalog, sort_keys=True, ensure_ascii=False,
                                                         separators=(",", ":")).encode()).hexdigest()}
