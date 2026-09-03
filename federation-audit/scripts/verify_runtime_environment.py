#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
from pathlib import Path

EXCLUDED_DISTRIBUTIONS = {"pip", "setuptools"}


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_lock(path: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, version = line.partition("==")
        if not separator or not name or not version:
            raise SystemExit(f"non-exact requirement at {path}:{line_number}")
        normalized = normalize_name(name)
        if normalized in expected:
            raise SystemExit(f"duplicate requirement: {normalized}")
        expected[normalized] = version
    return expected


def installed_distributions() -> dict[str, str]:
    return {
        normalize_name(distribution.metadata["Name"]): distribution.version
        for distribution in importlib.metadata.distributions()
        if normalize_name(distribution.metadata["Name"]) not in EXCLUDED_DISTRIBUTIONS
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    expected = load_lock(args.lock)
    actual = installed_distributions()
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        wrong = sorted(name for name in set(actual) & set(expected) if actual[name] != expected[name])
        raise SystemExit(
            f"runtime environment mismatch: missing={missing} unexpected={unexpected} wrong={wrong}"
        )

    packages = [{"name": name, "version": actual[name]} for name in sorted(actual)]
    snapshot = "".join(f"{item['name']}=={item['version']}\n" for item in packages)
    args.snapshot.write_text(snapshot, encoding="utf-8")
    manifest = {
        "schema_version": "1.0.0",
        "verified": True,
        "lock": {"file": args.lock.name, "sha256": sha256_file(args.lock)},
        "snapshot": {"file": args.snapshot.name, "sha256": sha256_file(args.snapshot)},
        "package_count": len(packages),
        "packages": packages,
    }
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
