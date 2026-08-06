from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .fixture import fixture_passed, run_fixture_audit
from .inventory_graph import build_inventory_graph
from .scanner import scan_federation, write_json

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(instance: Path, schema: Path) -> None:
    Draft202012Validator(load_json(schema), format_checker=FormatChecker()).validate(load_json(instance))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="federation-audit")
    sub = parser.add_subparsers(dest="command", required=True)
    validate_parser = sub.add_parser("validate-manifest")
    validate_parser.add_argument("manifest", type=Path)
    validate_parser.add_argument("--schema", type=Path, default=PACKAGE_ROOT / "contracts/repository-audit-manifest.schema.json")
    scan = sub.add_parser("scan")
    scan.add_argument("--workspace-root", type=Path, required=True)
    scan.add_argument("--manifest", type=Path, required=True)
    scan.add_argument("--output", type=Path, required=True)
    graph = sub.add_parser("inventory-graph")
    graph.add_argument("--manifest", type=Path, required=True)
    graph.add_argument("--output", type=Path, required=True)
    fixture = sub.add_parser("fixture-audit")
    fixture.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-manifest":
        validate(args.manifest, args.schema)
        print(f"valid: {args.manifest}")
        return 0
    if args.command == "scan":
        manifest = load_json(args.manifest)
        result = scan_federation(args.workspace_root.resolve(), manifest)
        write_json(args.output, result)
        print(json.dumps(result["coverage"], sort_keys=True))
        if result["workspace_gaps"]:
            print("missing workspace repositories: " + ", ".join(result["workspace_gaps"]))
        return 0
    if args.command == "inventory-graph":
        result = build_inventory_graph(load_json(args.manifest), args.manifest.as_posix())
        write_json(args.output, result)
        print(json.dumps(result["coverage"], sort_keys=True))
        return 0
    if args.command == "fixture-audit":
        result = run_fixture_audit()
        write_json(args.output, result)
        passed = fixture_passed(result)
        print(json.dumps({"passed": passed, "cases": len(result["traces"])}, sort_keys=True))
        return 0 if passed else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
