#!/usr/bin/env python3
"""Compatibility entry point for the PLAN MAX authority-boundary validator.

The canonical implementation lives in scripts/validate_authority_boundary.py.
This module exists so drift manifests and operators have a stable semantic name
for the expanded B-H1..B-H8 + A/D pre-activation gate.
"""

from validate_authority_boundary import main


if __name__ == "__main__":
    raise SystemExit(main())
