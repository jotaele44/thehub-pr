#!/usr/bin/env python3
"""Maximum acceptable Federation offline package validator.

This wrapper preserves the strict validator while allowing the full source
contract vocabulary used by the Hub schema authority layer.
"""
from __future__ import annotations

import validate_offline_package_contract as contract

contract.SOURCE_ACCESS = contract.SOURCE_ACCESS | {"scrape"}
contract.SOURCE_STATUS = contract.SOURCE_STATUS | {"blocked"}

if __name__ == "__main__":
    raise SystemExit(contract.main())
