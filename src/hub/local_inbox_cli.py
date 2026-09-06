"""CLI for fail-closed Centinelas local-envelope ingestion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .local_inbox import (
    DEFAULT_KIND,
    DEFAULT_SOURCE_REPOSITORY,
    TARGET_REPOSITORY,
    LocalInboxError,
    consume_directory,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hub-local-inbox",
        description=(
            "Validate and commit whole Centinelas envelopes into TheHub's "
            "authoritative local inbox"
        ),
    )
    parser.add_argument(
        "--exchange-root",
        default=".federation/exchange",
        help="local Federation exchange root",
    )
    parser.add_argument(
        "--source-dir",
        default=None,
        help=(
            "directory containing canonical envelope files; defaults to "
            "<exchange-root>/outbox/thehub-pr"
        ),
    )
    parser.add_argument(
        "--state-root",
        default="data/local_inbox",
        help="TheHub immutable intake/rejection record root",
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE_REPOSITORY)
    parser.add_argument("--kind", default=DEFAULT_KIND)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and classify without writing inbox, records, or receipts",
    )
    parser.add_argument("--json", action="store_true", help="emit full JSON summary")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    exchange_root = Path(args.exchange_root)
    source_dir = (
        Path(args.source_dir)
        if args.source_dir is not None
        else exchange_root / "outbox" / TARGET_REPOSITORY
    )
    try:
        summary = consume_directory(
            source_dir,
            exchange_root=exchange_root,
            state_root=args.state_root,
            expected_source=args.source,
            expected_kind=args.kind,
            dry_run=args.dry_run,
        )
    except LocalInboxError as exc:
        print(f"local inbox failed closed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        counts = summary["counts"]
        print(
            "local inbox "
            f"discovered={summary['discovered']} "
            f"processed={counts['PROCESSED']} "
            f"duplicate={counts['DUPLICATE']} "
            f"validated={counts['VALIDATED']} "
            f"rejected={counts['REJECTED']} "
            f"failed={counts['FAILED']} "
            "certification=PROVISIONAL dynamic_gates=0/8"
        )
    return 1 if (summary["counts"]["REJECTED"] or summary["counts"]["FAILED"]) else 0


if __name__ == "__main__":
    sys.exit(main())
