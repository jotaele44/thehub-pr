"""Command-line interface for the PRII federation Hub.

    hub list                         list registered producers
    hub validate-manifest <path>     validate a producer federation.json
    hub validate-package <dir>       validate an export package directory
    hub fetch [--root ws] [--run]    clone/refresh producers (optionally export)
    hub aggregate [--root .]         discover + aggregate producer packages
    hub correlate [--in d --out d]   derive cross-producer correlation relationships
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .aggregate import aggregate, discover_packages
from .bridge import write_manifest
from .correlate import correlate
from .fetch import fetch_all
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

    fp = sub.add_parser("fetch", help="clone/refresh producers into a workspace (optionally run their export)")
    fp.add_argument("--registry", default=DEFAULT_REGISTRY)
    fp.add_argument("--root", default="workspace", help="workspace dir to clone producers into")
    fp.add_argument("--run", action="store_true", help="also run each producer's export_canonical command")
    fp.add_argument("--depth", type=int, default=1, help="git clone depth")

    ap = sub.add_parser("aggregate", help="aggregate producer export packages")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--root", default=".", help="workspace root containing producer checkouts")
    ap.add_argument("--out", default="data/aggregate")
    ap.add_argument("--non-strict", action="store_true", help="aggregate even invalid packages")

    wb = sub.add_parser(
        "wrap-bridge",
        help="generate a Hub-conformant manifest.json for a directory of canonical JSONL streams",
    )
    wb.add_argument("path")
    wb.add_argument("--producer", required=True, help="producer program_id (e.g. moneysweep-pr)")
    wb.add_argument("--mode", default="test", choices=["test", "production"])
    wb.add_argument("--created-at", default="1970-01-01T00:00:00Z", help="ISO timestamp (kept out of band for deterministic package_id)")

    cp = sub.add_parser("correlate", help="derive cross-producer correlation relationships from an aggregate")
    cp.add_argument("--in", dest="in_dir", default="data/aggregate", help="aggregate dir to read (entities/funding_awards/transactions.jsonl)")
    cp.add_argument("--out", default="data/aggregate", help="dir to write correlations.jsonl")
    cp.add_argument("--window-days", type=int, default=7, help="temporal-proximity window")
    cp.add_argument("--threshold-km", type=float, default=1.0, help="spatial-proximity threshold")
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

    if args.cmd == "fetch":
        reg = load_registry(args.registry)
        results = fetch_all(reg, args.root, run_export=args.run)
        for r in results:
            print(f"{r['program_id']:16} {r['action']:8} export={'yes' if r['exported'] else 'no '}  {r['base']}")
        print(
            f"fetched {len(results)} producer(s) into {args.root!r}; "
            f"run `hub aggregate --root {args.root}` next"
        )
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

    if args.cmd == "correlate":
        summary = correlate(
            args.in_dir, args.out,
            window_days=args.window_days, threshold_km=args.threshold_km,
        )
        print(f"wrote {summary['correlations']} correlation(s) -> {args.out}/correlations.jsonl")
        print(json.dumps(summary["by_type"], indent=2, sort_keys=True))
        return 0

    if args.cmd == "wrap-bridge":
        manifest = write_manifest(
            args.path, args.producer, mode=args.mode, created_at=args.created_at
        )
        print(
            f"wrote {args.path}/manifest.json — package_id={manifest['package_id']} "
            f"({len(manifest['files'])} streams)"
        )
        errs = validate_package(args.path)
        if errs:
            print(f"WARNING: package still invalid — {len(errs)} error(s):")
            for e in errs[:20]:
                print("  -", e)
            return 1
        print("VALID package")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
