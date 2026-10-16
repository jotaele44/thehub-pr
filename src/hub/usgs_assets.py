"""Frozen ScienceBase item/file adapters. Structural checks never activate data."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import urllib.parse
import zipfile
from collections import Counter
from pathlib import PurePosixPath


def read_metadata_archive(path, expected_sha256):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("Metadata archive SHA-256 mismatch")
    items = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or sum(i.file_size for i in archive.infolist()) > 128 * 1024 * 1024:
            raise ValueError("Unsafe metadata archive inventory")
        if any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts for n in names):
            raise ValueError("Unsafe metadata archive path")
        summary = json.loads(archive.read("summary.json"))
        receipts = summary["receipts"]
        if len(receipts) != summary["attempted"]:
            raise ValueError("Metadata receipt denominator mismatch")
        for receipt in receipts:
            source_id = receipt["source_item_id"]
            if not re.fullmatch(r"[0-9a-f]{24}", source_id) or source_id in items:
                raise ValueError("Invalid/duplicate source ID")
            raw = archive.read(source_id + "/response.bin")
            if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
                raise ValueError("Source response hash/size mismatch")
            if receipt["http_status"] != 200:
                raise ValueError("Metadata response not retrieved")
            item = json.loads(raw)
            if item.get("id") != source_id:
                raise ValueError("Requested/returned ID mismatch")
            items[source_id] = item
    return summary, items


def file_inventory(items):
    rows = []
    for source_id, item in sorted(items.items()):
        descriptors = item.get("files", [])
        if not isinstance(descriptors, list):
            raise ValueError("Invalid files field")
        for ordinal, descriptor in enumerate(descriptors):
            if not isinstance(descriptor, dict):
                raise ValueError("Invalid file descriptor")
            size = descriptor.get("size")
            if size is not None and (type(size) is not int or size < 0):
                raise ValueError("Invalid declared file size")
            rows.append({"asset_id": "%s:%d" % (source_id, ordinal), "source_item_id": source_id,
                         "ordinal": ordinal, "raw_descriptor": descriptor,
                         "payload_state": "OPEN", "activation_state": "BLOCKED"})
    return rows


def verify_payload(raw, descriptor):
    expected_size = descriptor.get("size")
    if type(expected_size) is not int or len(raw) != expected_size:
        raise ValueError("Source-declared size mismatch or unavailable")
    checksum = descriptor.get("checksum") or {}
    kind = str(checksum.get("type", "")).lower().replace("-", "")
    expected = str(checksum.get("value", "")).lower()
    if kind not in ("md5", "sha1", "sha256", "sha512") or not expected:
        raise ValueError("Source checksum unavailable/unsupported")
    if hashlib.new(kind, raw).hexdigest() != expected:
        raise ValueError("Source checksum mismatch")
    return {"state": "PASS", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "source_checksum_type": kind, "source_checksum_value": expected,
            "meaning": "BYTE integrity only; semantic and activation gates remain OPEN"}


def inspect_payload(raw, name):
    """Return lossless inventory diagnostics, not a synthesized scientific table."""
    suffix = PurePosixPath(name).suffix.lower()
    if suffix == ".zip":
        return inspect_zip(raw)
    if suffix == ".csv":
        return inspect_csv(raw)
    if suffix in (".json", ".geojson"):
        value = json.loads(raw)
        if isinstance(value, dict) and value.get("type") == "FeatureCollection":
            features = value.get("features")
            if not isinstance(features, list) or any(not isinstance(f, dict) or f.get("type") != "Feature" for f in features):
                raise ValueError("Invalid GeoJSON FeatureCollection")
            return {"format": "GeoJSON", "feature_count": len(features), "crs_raw": value.get("crs"),
                    "geometry_types": dict(Counter((f.get("geometry") or {}).get("type", "NULL_EMPTY") for f in features)),
                    "state": "PROVISIONAL", "spatial_state": "UNRESOLVED",
                    "reason": "Coordinates/CRS/Z/M, topology, IDs and PR coverage still require semantic validation"}
        return {"format": "JSON", "state": "PROVISIONAL", "root_type": type(value).__name__}
    return {"format": suffix or "UNKNOWN", "state": "OPEN", "reason": "No semantic adapter certified"}


def inspect_csv(raw):
    encoding = "utf-8-sig"
    try:
        text = raw.decode(encoding, errors="strict")
    except UnicodeDecodeError:
        return {"format": "CSV", "state": "OPEN", "reason": "Encoding requires adjudication"}
    sample = text[:65536]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return {"format": "CSV", "state": "OPEN", "encoding": encoding,
                "reason": "Delimiter requires adjudication"}
    rows = list(csv.reader(io.StringIO(text, newline=""), dialect=dialect, strict=True))
    return {"format": "CSV", "state": "PROVISIONAL", "encoding": encoding,
            "delimiter_candidate": dialect.delimiter, "physical_lines": len(text.splitlines()),
            "parsed_rows": len(rows), "blank_rows": sum(not r for r in rows),
            "row_widths": dict(Counter(str(len(r)) for r in rows)), "preamble_and_header_candidates": rows[:10],
            "header_state": "UNRESOLVED", "record_denominator": None,
            "reason": "Header, units, field semantics and stable IDs require source metadata binding"}


def inspect_zip(raw):
    members = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        names = [i.filename for i in entries]
        if len(entries) > 10000 or len(names) != len(set(names)):
            raise ValueError("ZIP member count or duplicate path violation")
        if sum(i.file_size for i in entries) > 256 * 1024 * 1024:
            raise ValueError("ZIP expanded-size capacity exceeded")
        for entry in entries:
            path = PurePosixPath(entry.filename.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or entry.flag_bits & 1:
                raise ValueError("Unsafe/encrypted ZIP member")
            if entry.is_dir():
                continue
            data = archive.read(entry)  # zipfile verifies CRC; never extract or execute.
            members.append({"path": entry.filename, "uncompressed_size": len(data),
                            "sha256": hashlib.sha256(data).hexdigest()})
    return {"format": "ZIP", "state": "PROVISIONAL", "members": members,
            "member_count": len(members), "reason": "Member byte inventory only; payload semantics remain OPEN"}


def approved_download_url(source_id, descriptor):
    url = descriptor.get("downloadUri") or descriptor.get("url") or ""
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "www.sciencebase.gov" or parsed.username
            or parsed.port not in (None, 443) or parsed.fragment
            or parsed.path != "/catalog/file/get/" + source_id):
        raise ValueError("Unapproved asset URL/ID binding; requires review")
    return url
