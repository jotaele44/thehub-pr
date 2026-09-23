"""Query spec for the read-only Intelligence Engine boundary.

Only ``EXACT_ID`` and ``STRUCTURED`` are implemented. ``LEXICAL``, ``VECTOR``,
``SPATIAL``, ``TEMPORAL``, ``GRAPH``, and ``HYBRID`` are not modelled here at
all: no snapshot manifest built by ``hub.snapshot_runtime`` has ever carried an
``index_version`` other than ``"none"``, so there is no index for those modes
to query against yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional

QueryMode = Literal["EXACT_ID", "STRUCTURED"]


@dataclass(frozen=True)
class QuerySpec:
    mode: QueryMode
    object_id: Optional[str] = None
    stream: Optional[str] = None
    filters: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if self.mode == "EXACT_ID" and not self.object_id:
            raise ValueError("EXACT_ID query requires object_id")
        if self.mode == "STRUCTURED" and not self.stream:
            raise ValueError("STRUCTURED query requires stream")


__all__ = ["QueryMode", "QuerySpec"]
