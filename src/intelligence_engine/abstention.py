"""Abstention decisions for the read-only Intelligence Engine boundary.

Only the statuses this reader can actually produce are used here: ``ANSWERED``,
``INSUFFICIENT_EVIDENCE`` (a lookup or filter found nothing), ``SNAPSHOT_INCOMPLETE``
(no ACTIVE snapshot has ever been promoted), and ``RETRIEVAL_FAILURE`` (the
active manifest's recorded artifact hash no longer matches the aggregate file on
disk). ``PARTIALLY_ANSWERED``, ``CONTRADICTED``, ``OUT_OF_SCOPE``, and
``GENERATION_FAILURE`` require claim-ledger/generation machinery this reader
does not have.
"""
from __future__ import annotations

from typing import Any

from hub.contract_runtime import validate_contract


def decide_abstention(status: str, reason: str) -> dict[str, Any]:
    payload = {"status": status, "reason": reason}
    validate_contract("abstention.v1", payload)
    return payload


__all__ = ["decide_abstention"]
