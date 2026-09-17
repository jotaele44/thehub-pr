#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".federation" / "statistical-routing-manifest.json"

REPOS = {
    "thehub-pr",
    "moneysweep-pr",
    "aguayluz-pr",
    "centinelas-pr",
    "skywatcher-pr",
    "ovnis-pr",
    "spiderweb-pr",
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if doc.get("routing_rules", {}).get("hub_catalog_authority") != "thehub-pr":
        fail("TheHub must remain catalog authority")

    categories = doc.get("categories") or []
    if not categories:
        fail("no categories")

    raw_names = [row.get("raw") for row in categories]
    dupes = [k for k, v in Counter(raw_names).items() if v > 1]
    if dupes:
        fail(f"duplicate category rows: {dupes}")

    for row in categories:
        if not row.get("raw"):
            fail("category missing raw label")
        primary = row.get("primary_owner")
        if primary not in REPOS:
            fail(f"unknown primary repo {primary!r} for {row['raw']!r}")
        secondaries = row.get("secondary_consumers") or []
        unknown = sorted(set(secondaries) - REPOS)
        if unknown:
            fail(f"unknown secondary repos {unknown} for {row['raw']!r}")
        if primary in secondaries:
            fail(f"primary duplicated in secondary list for {row['raw']!r}")

    for product in doc.get("sample_products") or []:
        if product.get("primary_owner") not in REPOS:
            fail(f"unknown product primary: {product.get('title_raw')!r}")
        if not product.get("title_raw") or not product.get("source_entity_raw"):
            fail("sample product missing raw title/source entity")

    required = doc.get("required_record_fields") or []
    if len(required) != len(set(required)):
        fail("required_record_fields contains duplicates")

    allowed = set(doc.get("routing_rules", {}).get("allowed_cardinalities") or [])
    expected = {"1:1", "1:N", "N:1", "N:N", "0:1", "UNRESOLVED"}
    if allowed != expected:
        fail(f"cardinality set mismatch: {sorted(allowed)}")

    print(
        "PASS:",
        f"categories={len(categories)}",
        f"sample_products={len(doc.get('sample_products') or [])}",
        f"repos={len(REPOS)}",
    )


if __name__ == "__main__":
    main()
