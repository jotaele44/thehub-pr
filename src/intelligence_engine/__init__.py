"""Read-only Intelligence Engine query boundary over the certified ACTIVE snapshot.

See ``reader`` for the ``ActiveSnapshotReader`` interface and its documented
scope limits (no vector/spatial/graph index, no citation resolution, no real
access-classification enforcement yet).
"""
from .abstention import decide_abstention
from .objects import canonical_record_object
from .query import QueryMode, QuerySpec
from .reader import ActiveSnapshotReader

__all__ = [
    "ActiveSnapshotReader",
    "QueryMode",
    "QuerySpec",
    "canonical_record_object",
    "decide_abstention",
]
