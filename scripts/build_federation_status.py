#!/usr/bin/env python3
"""Build a committable snapshot of federation readiness.

Why this exists
---------------
`hub validate-federation` is the only thing in the repo that produces real,
per-producer readiness truth: manifest validity, export-package validity, live
execution gates. Three UI collections — ValidationGates, IntegrationStatus and
FederationManifest — want exactly that data and currently render empty.

The obvious wiring, seeding straight from `validate_federation()` at server
startup the way `_seed_programs()` seeds from the registry, does not work. That
function resolves each producer as ``root / repo_name`` and can only see a
workspace holding all six producer checkouts side by side. A deployed hub has
none of them, so a live call would report ``missing_checkout`` for every producer
and the three collections would fill up with six rows of noise on every real
install.

So readiness is captured at build time, in a workspace that *does* have the
checkouts, and committed. The server seeds from the committed snapshot and never
runs the validator itself. This mirrors how ``data/aggregate`` already works: a
real pipeline result, captured once, committed, and honest about when it was
taken.

The snapshot is a point-in-time measurement, not a live feed. It carries
``generated_at`` so the UI can show when it was taken and nobody mistakes it for
current state — the same contract ``data/fixture.json`` keeps for record counts.

Usage:
    python3 scripts/build_federation_status.py --root .. --out data
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hub.federation_status import validate_federation  # noqa: E402
from hub.registry import load_registry  # noqa: E402

#: Absolute-path fields on each producer row. The validator records where it
#: looked on the build machine; committing "/home/user/moneysweep-pr" would leak
#: a local layout and churn the diff on every machine that regenerates this.
_PATH_FIELDS = ("local_path", "manifest_path", "package_path")


def _relativize(summary: dict, root: Path) -> dict:
    """Rewrite build-machine absolute paths as workspace-relative ones."""
    summary = dict(summary)
    summary["root"] = "."
    rebased = []
    for producer in summary.get("producers", []):
        producer = dict(producer)
        for field in _PATH_FIELDS:
            value = producer.get(field)
            if not value:
                continue
            try:
                producer[field] = Path(value).relative_to(root).as_posix()
            except ValueError:
                # Outside the workspace root — keep it, but it is not portable.
                producer[field] = Path(value).as_posix()
        rebased.append(producer)
    summary["producers"] = rebased
    return summary


def build(registry_path: Path, root: Path, generated_at: str) -> dict:
    registry = load_registry(str(registry_path))
    summary = _relativize(validate_federation(registry, root), root)
    summary["kind"] = "federation-readiness-snapshot"
    summary["generated_at"] = generated_at
    summary["note"] = (
        "Built by scripts/build_federation_status.py from `hub validate-federation` "
        "against a workspace holding the producer checkouts. This is a point-in-time "
        "snapshot, not live state: a deployed hub has no producer checkouts and "
        "cannot recompute it. Regenerate with `make federation-status`."
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT.parent,
                        help="workspace holding the producer checkouts")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data",
                        help="destination directory for federation_status.json")
    parser.add_argument("--registry", type=Path,
                        default=REPO_ROOT / "registry" / "producers.yaml")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    generated_at = datetime.now(timezone.utc).isoformat()
    summary = build(args.registry, root, generated_at)

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / "federation_status.json"
    destination.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"federation status written to {destination}")
    print(f"  {summary['producer_count']} producers, "
          f"{summary['ready_count']} ready, blockers: {summary['by_blocker']}")
    missing = [p["program_id"] for p in summary["producers"]
               if not p["checkout_present"]]
    if missing:
        print(f"  WARNING: no checkout found for {', '.join(missing)} — "
              f"rerun with --root pointing at the producer workspace")
    return 0


if __name__ == "__main__":
    sys.exit(main())
