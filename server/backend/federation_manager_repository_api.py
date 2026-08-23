"""Repository/data-health routes for the native Federation Manager.

Installed by ``run_manager_host.py`` before the FastAPI application includes the
manager router. The route reuses the manager's loopback/origin/session gates and
reports only identities, states, receipts and artifact hashes; it exposes no
secret value and accepts no command text.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Optional

from fastapi import Header, Request

from server.backend.federation_manager_artifacts import ArtifactRegistrationError
from server.backend.federation_manager_repository_registry import RepositoryBindingError

_INSTALLED = False


def _last_receipt(active, app_id: str) -> Optional[Dict[str, Any]]:
    matches = []
    for document in active.runner.receipts.all_documents():
        receipt = document.get("receipt", {})
        if receipt.get("app_id") == app_id:
            matches.append(receipt)
    if not matches:
        return None
    matches.sort(key=lambda row: str(row.get("finished_at") or ""))
    last = matches[-1]
    return {
        "runId": last.get("run_id"),
        "operationId": last.get("operation_id"),
        "status": last.get("status"),
        "finishedAt": last.get("finished_at"),
    }


def _quick_actions(operations) -> Dict[str, Optional[str]]:
    actions: Dict[str, Optional[str]] = {
        "fetch": None,
        "export": None,
        "audit": None,
        "repair": None,
    }
    for operation in operations:
        op_id = operation.operation_id.lower()
        category = operation.category.lower()
        if actions["fetch"] is None and (category == "acquire" or ".fetch" in op_id):
            actions["fetch"] = operation.operation_id
        if actions["export"] is None and category == "export":
            actions["export"] = operation.operation_id
        if actions["audit"] is None and (category == "maintenance" or ".maintenance" in op_id):
            actions["audit"] = operation.operation_id
        if actions["repair"] is None and (category == "repair" or ".repair" in op_id):
            actions["repair"] = operation.operation_id
    return actions


def install_repository_routes(api_module) -> None:
    """Install once on the existing authenticated manager router."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    @api_module.router.get("/repositories")
    def repository_health(
        request: Request,
        authorization: Optional[str] = Header(None),
    ):
        api_module._authorize(request, authorization)
        active = api_module._require_runtime()

        operations_by_repo = defaultdict(list)
        for operation in active.runner.policy.operations.values():
            operations_by_repo[operation.repo].append(operation)

        rows = []
        for repo_key in sorted(operations_by_repo):
            operations = operations_by_repo[repo_key]
            app_ids = sorted({operation.app_id for operation in operations})
            app_id = app_ids[0] if len(app_ids) == 1 else None
            enabled = sum(1 for operation in operations if operation.enabled)
            binding = None
            binding_error = getattr(active, "repository_binding_failures", {}).get(repo_key)

            if not binding_error:
                try:
                    binding = active.repositories.resolve(repo_key)
                except RepositoryBindingError as exc:
                    binding_error = str(exc)

            active_artifact = None
            artifact_error = None
            if app_id and binding is not None:
                try:
                    active_artifact = active.artifacts.current(app_id)
                except ArtifactRegistrationError as exc:
                    artifact_error = str(exc)

            if binding_error:
                state = "UNAVAILABLE"
            elif artifact_error:
                state = "ARTIFACT_ERROR"
            elif active_artifact:
                state = "ACTIVE_ARTIFACT"
            else:
                state = "CONNECTED_NO_ACTIVE_ARTIFACT"

            rows.append(
                {
                    "repo": repo_key,
                    "appId": app_id,
                    "appIds": app_ids,
                    "repositoryFullName": (
                        binding.repository_full_name if binding is not None else None
                    ),
                    "state": state,
                    "bindingError": binding_error,
                    "artifactError": artifact_error,
                    "declaredOperations": len(operations),
                    "enabledOperations": enabled,
                    "activeArtifact": active_artifact,
                    "lastReceipt": _last_receipt(active, app_id) if app_id else None,
                    "quickActions": _quick_actions(operations),
                }
            )
        return rows
