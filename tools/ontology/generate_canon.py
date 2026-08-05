#!/usr/bin/env python3
"""Generate or verify the deterministic manifest for normative ontology files."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Sequence

MANIFEST_REL = Path("federation/ontology/CANON_MANIFEST.json")
EXCLUDED_PARTS = {"generated", "__pycache__"}


def digest(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def build(root: Path) -> dict[str, object]:
    ontology = root / "federation/ontology"
    files: dict[str, str] = {}
    for path in sorted(ontology.rglob("*")):
        if not path.is_file() or path == root / MANIFEST_REL:
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        files[rel.as_posix()] = digest(path)
    shared = root / "schemas/common/lineage.schema.json"
    if shared.exists():
        files[shared.relative_to(root).as_posix()] = digest(shared)
    return {"schema_version": "1.0.0", "hash_algorithm": "git_blob_sha1", "files": files}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    expected = build(args.root)
    manifest_path = args.root / MANIFEST_REL
    if args.check:
        if not manifest_path.exists():
            print(f"missing {MANIFEST_REL}", file=sys.stderr)
            return 2
        actual = json.loads(manifest_path.read_text(encoding="utf-8"))
        if actual != expected:
            print("ontology manifest drift detected", file=sys.stderr)
            return 2
        print("ontology manifest verified")
        return 0
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
