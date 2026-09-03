"""Frozen entity-resolution ledger projection for Hub correlation output.

This module is intentionally separate from correlation discovery. Correlation rows
remain canonical federation relationships; this layer exposes the corresponding
immutable ``entity_resolution.v1`` candidate ledger without upgrading any match to
identity.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contract_runtime import correlation_candidate_record


def candidate_ledger_rows(
    relationships: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Project candidate correlation relationships into frozen ledger rows.

    Every input must already carry the explicit correlation-not-identity runtime
    state. Output order is deterministic by decision id.
    """
    rows = [correlation_candidate_record(row) for row in relationships]
    rows.sort(key=lambda row: row["decision_id"])
    return rows


def write_candidate_ledger(correlations_path, ledger_path) -> dict[str, Any]:
    """Write a deterministic frozen candidate ledger from ``correlations.jsonl``."""
    source = Path(correlations_path)
    target = Path(ledger_path)
    relationships: list[dict[str, Any]] = []
    if source.exists():
        for raw in source.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                relationships.append(json.loads(raw))

    rows = candidate_ledger_rows(relationships)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return {
        "source": str(source),
        "ledger": str(target),
        "candidate_count": len(rows),
    }


__all__ = ["candidate_ledger_rows", "write_candidate_ledger"]
