"""Control Plane primitives that do not promote ACTIVE snapshots."""

from .snapshot_gate import (
    SnapshotCertificationError,
    certify_validation_report,
    compute_snapshot_gate,
    snapshot_operation_decision,
)

__all__ = [
    "SnapshotCertificationError",
    "certify_validation_report",
    "compute_snapshot_gate",
    "snapshot_operation_decision",
]
