"""Fail-closed client and operation boundary for TheHub administration."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "governance" / "admin_control_plane" / "privilege_matrix.json"


class AdminBoundaryError(PermissionError):
    pass


@dataclass(frozen=True)
class AdminBoundary:
    operation_clients: dict[str, frozenset[str]]

    @classmethod
    def load(cls, path: Path = MATRIX_PATH) -> "AdminBoundary":
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("default_effect") != "DENY":
            raise AdminBoundaryError("admin boundary must default to DENY")
        bindings: dict[str, frozenset[str]] = {}
        for row in document.get("operation_bindings", []):
            operation_id = row.get("operation_id")
            if not operation_id or operation_id in bindings:
                raise AdminBoundaryError("missing or duplicate operation binding")
            bindings[operation_id] = frozenset(row.get("allowed_clients", []))
        return cls(bindings)

    def require_operation(self, operation_id: str, client_class: str) -> None:
        allowed = self.operation_clients.get(operation_id)
        if allowed is None:
            raise AdminBoundaryError(f"unclassified operation: {operation_id}")
        if client_class not in allowed:
            raise AdminBoundaryError(
                f"client {client_class!r} cannot execute operation {operation_id!r}"
            )


BOUNDARY = AdminBoundary.load()


def declared_client(request) -> str:
    """Manager sessions are native-workstation sessions; reject client confusion."""
    value = request.headers.get("x-prii-client-class", "thehub_workstation")
    if value != "thehub_workstation":
        raise AdminBoundaryError("manager API is workstation-only")
    return value
