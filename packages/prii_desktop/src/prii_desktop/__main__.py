"""Command-line tools of the shared desktop runtime.

    python -m prii_desktop launchpad --check [--repo-root PATH] [--no-status]
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["launchpad"]:
        from .launchpad import main as launchpad_main

        return launchpad_main(args[1:])
    print(__doc__.strip())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
