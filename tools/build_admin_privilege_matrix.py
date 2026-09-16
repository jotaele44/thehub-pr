#!/usr/bin/env python3
"""Build the exhaustive TheHub privilege matrix from the signed operation policy."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config" / "operations_policy.json"
OUTPUT = ROOT / "governance" / "admin_control_plane" / "privilege_matrix.json"


def authority_class(operation: dict) -> str:
    if operation["repo"] != "thehub-pr":
        return "LOCAL_REPO"
    if operation["operation_id"] in {"hub.aggregate", "hub.correlate", "hub.ingest", "hub.analytics_v2", "hub.consume_sensor_fusion"}:
        return "CROSS_REPO"
    return "FEDERATION_GLOBAL"


def build() -> dict:
    signed = json.loads(SOURCE.read_text(encoding="utf-8"))
    policy = signed["policy"]
    bindings = []
    for operation in policy["operations"]:
        bindings.append({
            "operation_id": operation["operation_id"],
            "repo": operation["repo"],
            "authority_class": authority_class(operation),
            "risk_class": operation["risk_class"],
            "enablement": operation["enablement"],
            "allowed_clients": ["thehub_workstation"],
            "token_audience": "federation-admin-workstation",
            "audit_required": True,
        })
    return {
        "schema_version": "thehub_admin_boundary_v1",
        "contract_version": "1.0.0",
        "source_policy_id": policy["policy_id"],
        "source_policy_sha256": signed["signature"]["payload_sha256"],
        "default_effect": "DENY",
        "clients": {
            "thehub_workstation": {"audience": "federation-admin-workstation", "may_execute_operations": True},
            "thehub_ios": {"audience": "federation-admin-companion", "may_execute_operations": False},
            "repo_app": {"audience": "repository-operation", "may_execute_operations": False},
        },
        "companion_capabilities": [
            "federation.status.read", "federation.search", "report.read",
            "certification.status.read", "alert.read",
        ],
        "workstation_only_capabilities": [
            "federation.membership.write", "federation.role.write", "contract.publish",
            "lockstep.override", "certification.issue", "deployment.promote",
            "schema.migrate", "secret.write", "secret.delete", "operation.execute",
        ],
        "operation_bindings": sorted(bindings, key=lambda row: row["operation_id"]),
    }


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
