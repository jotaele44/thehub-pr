"""Internal continuation from frozen roots: recursive metadata and bounded bytes."""
import argparse
import csv
import hashlib
import json
import sys
import urllib.parse
import zipfile
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hub.usgs_acquisition import fetch_manifest, snapshot_item  # noqa: E402
from hub.usgs_assets import (approved_download_url, file_inventory, inspect_payload,
                            read_metadata_archive, verify_payload)  # noqa: E402
from hub.usgs_catalog import load_catalog  # noqa: E402


def continue_snapshot(archive, expected_hash, out, byte_budget=256 * 1024 * 1024, file_cap=5 * 1024 * 1024):
    summary, items = read_metadata_archive(archive, expected_hash)
    roots = {r["sciencebase_id"] for r in load_catalog()["releases"]}
    if set(items) != roots:
        raise ValueError("Root item set differs from catalog")
    out.mkdir(parents=True, exist_ok=True)
    query_dir = out / "queries"
    query_dir.mkdir(exist_ok=True)
    queue, visited, edges, problems = deque(sorted(items)), set(), [], []
    while queue:
        source_id = queue.popleft()
        if source_id in visited:
            continue
        visited.add(source_id)
        item = items[source_id]
        if item.get("hasChildren") is False:
            continue
        if item.get("hasChildren") is not True:
            problems.append({"item": source_id, "state": "OPEN", "reason": "hasChildren unavailable"})
            continue
        seen, offset, expected_count = set(), 0, None
        while True:
            url = "https://www.sciencebase.gov/catalog/items?" + urllib.parse.urlencode({
                "parentId": source_id, "format": "json", "max": 1000, "offset": offset})
            key = hashlib.sha256(url.encode()).hexdigest()
            raw_path, receipt_path = query_dir / (key + ".bin"), query_dir / (key + ".json")
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text())
                raw = raw_path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
                    raise ValueError("Cached query hash mismatch")
            else:
                raw, receipt = fetch_manifest(url)
                raw_path.write_bytes(raw)
                receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
            if receipt["state"] != "PASS":
                problems.append({"item": source_id, "state": "BLOCKED", "reason": "Child query transport", "receipt": receipt_path.name})
                break
            page = json.loads(raw)
            total, children = page.get("total"), page.get("items")
            if type(total) is not int or total < 0 or not isinstance(children, list):
                raise ValueError("Unexpected child page schema")
            if expected_count is not None and expected_count != total:
                raise ValueError("Child count changed during snapshot")
            expected_count = total
            if len(items) + len(children) > 10000 or offset > 100000:
                problems.append({"item": source_id, "state": "BLOCKED", "reason": "Metadata capacity exceeded"})
                break
            for child in children:
                child_id = child["id"]
                if child_id in seen or child_id == source_id:
                    raise ValueError("Duplicate/cyclic child membership")
                seen.add(child_id)
                edges.append({"parent": source_id, "child": child_id, "query_receipt": receipt_path.name})
                if child_id not in items:
                    child_receipt = snapshot_item(child_id, out / "items")
                    if child_receipt["state"] != "PASS":
                        problems.append({"item": child_id, "state": "BLOCKED", "reason": "Child metadata transport"})
                        continue
                    items[child_id] = json.loads((out / "items" / child_id / "response.bin").read_bytes())
                    queue.append(child_id)
            offset += len(children)
            if offset == total:
                break
            if not children or offset > total:
                raise ValueError("Child pagination does not close")
    inventory = file_inventory(items)
    remaining = byte_budget
    payload_dir = out / "payloads"
    payload_dir.mkdir(exist_ok=True)
    for row in inventory:
        descriptor = row["raw_descriptor"]
        size = descriptor.get("size")
        row["semantic_state"] = "OPEN"
        if size is None or size > file_cap or size > remaining or remaining <= 0:
            row.update(payload_state="BLOCKED", reason="DECLARED_SIZE_OR_CAPACITY_GATE")
            continue
        if not (descriptor.get("checksum") or {}).get("value"):
            row.update(payload_state="BLOCKED", reason="SOURCE_CHECKSUM_UNAVAILABLE")
            continue
        key = row["asset_id"].replace(':', '_')
        raw_path, receipt_path = payload_dir / (key + ".bin"), payload_dir / (key + ".json")
        try:
            url = approved_download_url(row["source_item_id"], descriptor)
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text())
                raw = raw_path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
                    raise ValueError("Cached payload hash mismatch")
            else:
                raw, receipt = fetch_manifest(url, max_bytes=min(file_cap, max(1, size), remaining))
                raw_path.write_bytes(raw)
                receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
            remaining -= len(raw)
            row["transport"] = receipt
            if receipt["state"] != "PASS":
                row.update(payload_state="BLOCKED", reason="PAYLOAD_TRANSPORT")
                continue
            row["verification"] = verify_payload(raw, descriptor)
            row["payload_state"] = "PASS"
            row["inspection"] = inspect_payload(raw, descriptor.get("name", ""))
            row["semantic_state"] = row["inspection"]["state"]
        except (ValueError, KeyError, OSError, csv.Error, zipfile.BadZipFile, RuntimeError) as error:
            row.update(payload_state="FAIL", reason=str(error))
    result = {"contract": "prii.usgs-asset-inventory/v1", "root_archive_sha256": expected_hash,
              "source_workbook_sha256": summary["source_workbook_sha256"], "root_count": len(roots),
              "item_count": len(items), "child_edges": edges, "enumeration_problems": problems,
              "enumeration_state": "PASS" if not problems else "OPEN", "file_count": len(inventory),
              "declared_bytes": sum(r["raw_descriptor"].get("size") or 0 for r in inventory),
              "byte_budget": byte_budget, "byte_budget_remaining": remaining,
              "payload_states": dict(Counter(r["payload_state"] for r in inventory)),
              "activated": 0, "activation_state": "BLOCKED", "assets": inventory}
    (out / "inventory.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = continue_snapshot(args.archive, args.sha256, args.out)
    print(json.dumps({k: v for k, v in result.items() if k not in ("assets", "child_edges", "enumeration_problems")}))
    return 2 if result["activation_state"] == "BLOCKED" else 0


if __name__ == "__main__":
    sys.exit(main())
