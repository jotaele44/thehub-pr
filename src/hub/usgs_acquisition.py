"""Bounded ScienceBase metadata snapshot adapter. No network at import time.

HTTP errors are frozen transport evidence, never absence. Successful item
metadata admits file descriptors only. Payloads remain blocked until format,
geometry, coverage, lineage and consumer gates are independently satisfied.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES = 8 * 1024 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # A redirect requires explicit lineage/host review.


def fetch_manifest(url, opener=None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "www.sciencebase.gov" or parsed.username:
        raise ValueError("Unapproved metadata origin")
    request = urllib.request.Request(url, headers={"User-Agent": "PRII-USGS-catalog/1.0", "Accept": "application/json"})
    open_url = opener or urllib.request.build_opener(_NoRedirect()).open
    started = datetime.now(timezone.utc).isoformat()
    raw, status, content_type, error = b"", None, None, None
    try:
        with open_url(request, timeout=12) as response:
            status = response.status
            content_type = response.headers.get("Content-Type")
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get("Content-Type")
        raw = exc.read(MAX_BYTES + 1)
        error = "HTTP_%s" % status
    except (OSError, TimeoutError) as exc:
        error = type(exc).__name__
    truncated = len(raw) > MAX_BYTES
    if truncated:
        raw = raw[:MAX_BYTES]
        error = "SIZE_CAP_TRUNCATED"
    evidence = {"url": url, "retrieval_utc": started, "http_status": status,
                "content_type": content_type, "error": error, "truncated": truncated,
                "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "state": "PASS" if status == 200 and not error else "BLOCKED"}
    return raw, evidence


def enumerate_item(item, expected_id):
    if not isinstance(item, dict) or item.get("id") != expected_id:
        raise ValueError("Returned item ID does not bind to requested source")
    files = item.get("files", [])
    if not isinstance(files, list):
        raise ValueError("Unexpected files schema")
    assets = []
    for ordinal, file in enumerate(files):
        if not isinstance(file, dict):
            raise ValueError("Unexpected file descriptor schema")
        assets.append({"source_item_id": expected_id, "ordinal": ordinal, "raw_descriptor": file,
                       "payload_state": "OPEN", "adapter_state": "UNRESOLVED"})
    return {"assets": assets, "web_links_raw": item.get("webLinks", []),
            "facets_raw": item.get("facets", []), "has_children_raw": item.get("hasChildren"),
            "child_enumeration_state": "OPEN" if item.get("hasChildren") is not False else "PASS",
            "enumeration_state": "PROVISIONAL" if item.get("hasChildren") is not False else "PASS",
            "payload_state": "BLOCKED"}


def snapshot_item(source_id, destination, opener=None):
    if not re.fullmatch(r"[0-9a-f]{24}", source_id):
        raise ValueError("Invalid item ID")
    destination = Path(destination) / source_id
    destination.mkdir(parents=True, exist_ok=True)
    receipt_path = destination / "receipt.json"
    # Immutable run directory: reuse frozen observations, including failed ones.
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        raw = (destination / "response.bin").read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("Frozen source hash mismatch")
        return receipt
    url = "https://www.sciencebase.gov/catalog/item/%s?format=json" % source_id
    raw, receipt = fetch_manifest(url, opener)
    receipt.update({"source_item_id": source_id, "payload_state": "BLOCKED", "enumeration_state": "BLOCKED"})
    (destination / "response.bin").write_bytes(raw)
    if receipt["state"] == "PASS":
        try:
            manifest = enumerate_item(json.loads(raw), source_id)
            (destination / "assets.json").write_text(json.dumps(manifest, indent=2) + "\n")
            receipt["enumeration_state"] = manifest["enumeration_state"]
            receipt["asset_descriptor_count"] = len(manifest["assets"])
        except (ValueError, TypeError) as exc:
            receipt.update(state="FAIL", error=str(exc))
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
