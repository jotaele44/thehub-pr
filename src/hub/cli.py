"""Command-line interface for the PRII federation Hub.

    hub list                         list registered producers
    hub validate-manifest <path>     validate a producer federation.json
    hub validate-package <dir>       validate an export package directory
    hub aggregate [--root .]         discover + aggregate producer packages
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .aggregate import aggregate, discover_packages
from .manifest import load_and_validate_manifest
from .registry import load_registry
from .validate import validate_package

DEFAULT_REGISTRY = "registry/producers.yaml"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hub", description="PRII federation Hub")
    sub = p.add_subparsers(dest="cmd", required=True)

    lp = sub.add_parser("list", help="list registered producers")
    lp.add_argument("--registry", default=DEFAULT_REGISTRY)

    mp = sub.add_parser("validate-manifest", help="validate a producer federation.json")
    mp.add_argument("path")

    vp = sub.add_parser("validate-package", help="validate an export package dir")
    vp.add_argument("path")

    ap = sub.add_parser("aggregate", help="aggregate producer export packages")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--root", default=".", help="workspace root containing producer checkouts")
    ap.add_argument("--out", default="data/aggregate")
    ap.add_argument("--non-strict", action="store_true", help="aggregate even invalid packages")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "list":
        reg = load_registry(args.registry)
        print(f"# {reg.hub} ({reg.schema_version}) — {len(reg.producers)} producers")
        for pr in reg.producers:
            print(f"{pr.program_id:16} {pr.status:20} {pr.role:34} {pr.repo}")
        return 0

    if args.cmd == "validate-manifest":
        data, errs = load_and_validate_manifest(args.path)
        if errs:
            print(f"INVALID — {len(errs)} error(s):")
            for e in errs:
                print("  -", e)
            return 1
        print(f"VALID — {data.get('program_id')} (hub_parent={data.get('hub_parent')})")
        return 0

    if args.cmd == "validate-package":
        errs = validate_package(args.path)
        if errs:
            print(f"INVALID — {len(errs)} error(s):")
            for e in errs[:50]:
                print("  -", e)
            if len(errs) > 50:
                print(f"  … and {len(errs) - 50} more")
            return 1
        print("VALID package")
        return 0

    if args.cmd == "aggregate":
        reg = load_registry(args.registry)
        packages = discover_packages(reg, args.root)
        if not packages:
            print(f"no producer export packages found under {args.root!r}")
            return 1
        summary = aggregate(packages, args.out, strict=not args.non_strict)
        print(f"aggregated {len(summary['producers'])} producer(s) -> {args.out}")
        print(json.dumps(summary["streams"], indent=2, sort_keys=True))
        bad = {k: v for k, v in summary["errors"].items() if v}
        if bad:
            print("producers with validation errors:", ", ".join(bad))
            return 1
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
