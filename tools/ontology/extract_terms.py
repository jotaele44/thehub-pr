#!/usr/bin/env python3
"""Read-only semantic term extraction for pinned PRII repositories."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from common import sha256_text
    from extract_base import Observation, RepositoryScannerBase
    from extract_python import PythonScannerMixin
    from extract_structured import StructuredScannerMixin
except ImportError:  # pragma: no cover
    from tools.ontology.common import sha256_text
    from tools.ontology.extract_base import Observation, RepositoryScannerBase
    from tools.ontology.extract_python import PythonScannerMixin
    from tools.ontology.extract_structured import StructuredScannerMixin

EXTRACTOR_VERSION = "1.0.0"

class RepositoryScanner(PythonScannerMixin, StructuredScannerMixin, RepositoryScannerBase):
    pass

def load_pins(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    repositories = data.get("repositories")
    if not isinstance(repositories, list) or len(repositories) != 7:
        raise ValueError("pins file must contain exactly seven repositories")
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in repositories:
        if not isinstance(item, dict):
            raise ValueError("repository pin must be an object")
        required = {"program_id", "repository", "directory", "commit"}
        missing = required - set(item)
        if missing:
            raise ValueError(f"repository pin missing: {sorted(missing)}")
        program_id = str(item["program_id"])
        if program_id in seen:
            raise ValueError(f"duplicate program_id: {program_id}")
        seen.add(program_id)
        result.append({str(k): str(v) for k, v in item.items()})
    return result


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    pins = load_pins(args.pins)
    args.out.mkdir(parents=True, exist_ok=True)
    all_records: list[Observation] = []
    coverage: list[dict[str, Any]] = []
    fatal_errors: list[str] = []
    for spec in pins:
        repo_root = args.workspace / spec["directory"]
        if not repo_root.is_dir():
            fatal_errors.append(f"missing repository checkout: {repo_root}")
            continue
        scanner = RepositoryScanner(spec, repo_root)
        try:
            report = scanner.scan()
        except Exception as exc:
            fatal_errors.append(f"{spec['program_id']}: {type(exc).__name__}: {exc}")
            continue
        coverage.append(report)
        all_records.extend(scanner.records)

    all_records.sort(key=lambda r: (r.program_id, r.path, r.line, r.term_kind, r.normalized_label, r.observation_id))
    ledger_path = args.out / "raw-term-ledger.jsonl"
    with ledger_path.open("w", encoding="utf-8") as handle:
        for record in all_records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) + "\n")

    program_ids = {item["program_id"] for item in coverage}
    expected_ids = {item["program_id"] for item in pins}
    all_covered = (
        not fatal_errors
        and program_ids == expected_ids
        and all(item["coverage_percent"] == 100.0 and not item["failures"] for item in coverage)
    )
    coverage_doc = {
        "schema_version": "1.0.0",
        "extractor_version": EXTRACTOR_VERSION,
        "pins_sha256": sha256_text(args.pins.read_text(encoding="utf-8")),
        "repositories_expected": 7,
        "repositories_scanned": len(coverage),
        "all_repositories_100_percent": all_covered,
        "fatal_errors": fatal_errors,
        "repositories": coverage,
        "ledger_records": len(all_records),
        "ledger_sha256": sha256_text(ledger_path.read_text(encoding="utf-8")),
    }
    write_json(args.out / "coverage.json", coverage_doc)
    print(json.dumps({"records": len(all_records), "coverage_gate": all_covered, "fatal_errors": fatal_errors}, indent=2))
    return 0 if all_covered else 2


if __name__ == "__main__":
    sys.exit(main())
