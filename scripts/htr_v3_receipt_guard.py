#!/usr/bin/env python3
"""Lock a frozen HTR receipt semantically; optionally verify its actual ZIP bytes.

This is an integrity gate, not identity, connectivity, or evidence certification.
Serialization is Python JSON: sorted keys, compact separators, UTF-8, unescaped
Unicode, and no non-finite numbers. It is explicitly not an RFC 8785 claim.
No network requests, source refresh, archive extraction, or input writes occur.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

RECEIPT = Path("data/htr/runs/2026-09-02_htr_v3_frozen_road_recurrence_receipt.json")
EXPECTED_LOGICAL_SHA256 = "4baaeaccb6feff204c44b5159fff05a6fbe56c09dc02965579d59e305d3d9d99"
BUNDLE_PREFIX = "htr_v3_road_recurrence_2026-09-02/"
MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024


class ReceiptGuardError(ValueError):
    """The supplied manifestation does not satisfy the frozen integrity contract."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptGuardError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ReceiptGuardError(f"non-finite JSON constant: {value}")


def load_document(payload: bytes) -> dict[str, Any]:
    try:
        doc = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptGuardError(f"invalid UTF-8 JSON: {exc}") from exc
    if type(doc) is not dict:
        raise ReceiptGuardError("receipt must be a JSON object")
    return doc


def canonical_bytes(doc: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ReceiptGuardError(f"non-serializable receipt: {exc}") from exc


def validate_document(doc: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_bytes(doc)).hexdigest()
    if digest != EXPECTED_LOGICAL_SHA256:
        raise ReceiptGuardError(f"frozen receipt logical drift: {digest}")
    return digest


def verify_bundle(path: Path, doc: dict[str, Any]) -> dict[str, Any]:
    """Verify bytes and members against the validated receipt, without extracting."""
    validate_document(doc)
    artifact = doc["execution_artifact"]
    if path.stat().st_size != artifact["bundle_size_bytes"]:
        raise ReceiptGuardError("bundle byte-size mismatch")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != artifact["bundle_sha256"]:
        raise ReceiptGuardError("bundle SHA256 mismatch")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ReceiptGuardError("duplicate archive member path")
        if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
            raise ReceiptGuardError("archive exceeds uncompressed-size safety bound")
        for name in names:
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts or "\\" in name:
                raise ReceiptGuardError("unsafe archive path")
            if not name.startswith(BUNDLE_PREFIX):
                raise ReceiptGuardError("unexpected archive root")
        files = {i.filename[len(BUNDLE_PREFIX):] for i in infos if not i.is_dir()}
        ledger = load_document(archive.read(BUNDLE_PREFIX + "SHA256SUMS.json"))
        expected = set(artifact["output_hashes"]) | {
            "README.md", "run_htr_v3_frozen_road_recurrence.py", "terminal_receipt.json"
        }
        if set(ledger) != expected or files != expected | {"SHA256SUMS.json"}:
            raise ReceiptGuardError("archive member/ledger coverage mismatch")
        for name, digest in ledger.items():
            if hashlib.sha256(archive.read(BUNDLE_PREFIX + name)).hexdigest() != digest:
                raise ReceiptGuardError(f"archive member hash mismatch: {name}")
        for name, digest in artifact["output_hashes"].items():
            if ledger[name] != digest:
                raise ReceiptGuardError(f"external output binding mismatch: {name}")
        if ledger["run_htr_v3_frozen_road_recurrence.py"] != artifact["executor_sha256"]:
            raise ReceiptGuardError("executor binding mismatch")
    return {"state": "PASS_BYTES_AND_MEMBERS", "file_count": len(files),
            "sha256": artifact["bundle_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", type=Path, default=RECEIPT)
    parser.add_argument("--bundle", type=Path, help="Optional already-frozen local replay ZIP")
    args = parser.parse_args()
    try:
        doc = load_document(args.receipt.read_bytes())
        digest = validate_document(doc)
        bundle = verify_bundle(args.bundle, doc) if args.bundle else {"state": "NOT_RUN"}
    except (ReceiptGuardError, OSError, zipfile.BadZipFile, KeyError) as exc:
        print(json.dumps({"receipt_contract": "FAIL", "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps({
        "receipt_contract": "PASS", "logical_sha256": digest, "bundle_verification": bundle,
        "pair_binding_resolution": "OPEN", "identity_resolution": "OPEN",
        "merge_authorization_granted_by_guard": False,
        "scope": "INTEGRITY_ONLY_NOT_EVIDENCE_RESOLUTION",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
