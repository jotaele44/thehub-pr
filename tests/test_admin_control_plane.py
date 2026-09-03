import json
from pathlib import Path

import pytest

from server.backend.admin_control_plane import AdminBoundary, AdminBoundaryError

ROOT = Path(__file__).resolve().parents[1]


def test_every_signed_operation_has_exactly_one_workstation_binding():
    operations = json.loads((ROOT / "config/operations_policy.json").read_text())["policy"]["operations"]
    matrix = json.loads((ROOT / "governance/admin_control_plane/privilege_matrix.json").read_text())
    ids = [row["operation_id"] for row in matrix["operation_bindings"]]
    assert len(ids) == len(set(ids)) == 68
    assert set(ids) == {row["operation_id"] for row in operations}
    assert all(row["allowed_clients"] == ["thehub_workstation"] for row in matrix["operation_bindings"])


def test_repo_and_ios_clients_cannot_execute_any_operation():
    boundary = AdminBoundary.load()
    for operation_id in boundary.operation_clients:
        for client in ("repo_app", "thehub_ios", "unknown"):
            with pytest.raises(AdminBoundaryError):
                boundary.require_operation(operation_id, client)


def test_unknown_operation_fails_closed():
    with pytest.raises(AdminBoundaryError, match="unclassified"):
        AdminBoundary.load().require_operation("hub.unclassified", "thehub_workstation")


def test_all_authority_classes_are_explicit():
    matrix = json.loads((ROOT / "governance/admin_control_plane/privilege_matrix.json").read_text())
    assert {row["authority_class"] for row in matrix["operation_bindings"]} <= {
        "LOCAL_REPO", "CROSS_REPO", "FEDERATION_GLOBAL"
    }
    assert all(row["audit_required"] is True for row in matrix["operation_bindings"])


def test_ios_sources_contain_no_workstation_only_capability_or_entitlement():
    ios = ROOT / "ios/TheHubAdminCompanion"
    source = "\n".join(path.read_text() for path in sorted((ios / "Sources").glob("*.swift")))
    forbidden = {
        "lockstep.override", "certification.issue", "deployment.promote",
        "schema.migrate", "secret.write", "secret.delete", "operation.execute",
        "federation-admin-workstation", "AdminKit",
    }
    assert forbidden.isdisjoint(source.split())
    project = (ios / "project.yml").read_text()
    assert 'CODE_SIGN_ENTITLEMENTS: ""' in project


def test_companion_capabilities_are_subset_of_server_contract():
    matrix = json.loads((ROOT / "governance/admin_control_plane/privilege_matrix.json").read_text())
    assert set(matrix["companion_capabilities"]) == {
        "federation.status.read", "federation.search", "report.read",
        "certification.status.read", "alert.read",
    }
