#!/usr/bin/env python3
"""Validate one frozen producer runtime package against TheHub contracts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hub.federation_runtime import (  # noqa: E402
    FederationRuntimeError,
    load_federation_runtime_manifest,
)
from hub.review_quarantine import (  # noqa: E402
    ReviewQuarantineError,
    validate_review_quarantine_package,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate exact frozen federation runtime bytes using TheHub."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--certification", action="store_true")
    args = parser.parse_args(argv)

    mode = "CERTIFICATION" if args.certification else "AUDIT_ONLY"
    try:
        package = load_federation_runtime_manifest(
            args.manifest,
            package_root=args.package_root,
            certification=args.certification,
        )
        quarantine = validate_review_quarantine_package(
            args.package_root,
            certification=args.certification,
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        FederationRuntimeError,
        ReviewQuarantineError,
    ) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "mode": mode,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    promotable = bool(package.promotable and quarantine.promotable)
    print(
        json.dumps(
            {
                "ok": True,
                "mode": mode,
                "repository": package.repository,
                "producer_commit": package.producer_commit,
                "producer_tree": package.producer_tree,
                "producer_state": package.state,
                "ingestion_mode": package.ingestion_mode,
                "review_quarantine_state": quarantine.state,
                "quarantined_total": quarantine.quarantined_total,
                "canonical_primary_counts": dict(quarantine.canonical_primary_counts),
                "promotable": promotable,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
