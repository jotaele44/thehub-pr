"""Repository-aware facade over the existing trusted OperationRunner.

The original manager had one ``ExecutionContext`` rooted at TheHub, which is
correct for Hub operations but cannot safely execute a producer operation. This
facade keeps the existing runner implementation intact and selects a dedicated
runner whose app/data roots are bound to the repository named by the signed
policy operation.

Producer writes are still fail-closed until their signed policy rows declare
physical managed outputs: a producer runner audits the complete verified repo
root, while `_declared_write_scopes` permits only typed managed output
parameters. A command with undeclared relative writes therefore quarantines
rather than silently succeeding.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from server.backend.federation_manager_operations import OperationPolicyError, Policy
from server.backend.federation_manager_runner import OperationRunner, RunHandle


class RepositoryRunnerUnavailable(OperationPolicyError):
    """The signed operation names a repository that has no verified local runner."""


class RepositoryOperationRouter:
    """Drop-in manager runner facade that dispatches by signed ``operation.repo``."""

    def __init__(
        self,
        *,
        policy: Policy,
        runners: Mapping[str, OperationRunner],
    ) -> None:
        self.policy = policy
        self._runners = dict(runners)
        if "thehub-pr" not in self._runners:
            raise RepositoryRunnerUnavailable("thehub-pr runner is required")

        receipt_ids = {id(runner.receipts) for runner in self._runners.values()}
        if len(receipt_ids) != 1:
            raise RepositoryRunnerUnavailable(
                "all repository runners must share one receipt store for a single evidence chain"
            )
        self.receipts = next(iter(self._runners.values())).receipts

    def _operation(self, operation_id: str):
        try:
            return self.policy.operations[operation_id]
        except KeyError as exc:
            raise OperationPolicyError(f"unknown operation: {operation_id!r}") from exc

    def _runner_for_operation(self, operation_id: str) -> OperationRunner:
        operation = self._operation(operation_id)
        try:
            return self._runners[operation.repo]
        except KeyError as exc:
            raise RepositoryRunnerUnavailable(
                f"operation {operation_id!r} is bound to {operation.repo!r}, "
                "but that repository is not verified in this workspace"
            ) from exc

    def _runner_for_app(self, app_id: str) -> OperationRunner:
        repo_keys = {
            operation.repo
            for operation in self.policy.operations.values()
            if operation.app_id == app_id
        }
        if not repo_keys:
            raise OperationPolicyError(f"unknown application: {app_id!r}")
        if len(repo_keys) != 1:
            raise RepositoryRunnerUnavailable(
                f"application {app_id!r} maps to multiple repositories: {sorted(repo_keys)}"
            )
        repo_key = next(iter(repo_keys))
        try:
            return self._runners[repo_key]
        except KeyError as exc:
            raise RepositoryRunnerUnavailable(
                f"application {app_id!r} repository {repo_key!r} is not verified in this workspace"
            ) from exc

    def plan(
        self,
        operation_id: str,
        parameters: Optional[Mapping[str, Any]] = None,
        *,
        session_token: str = "",
    ):
        return self._runner_for_operation(operation_id).plan(
            operation_id, parameters, session_token=session_token
        )

    def prerequisites(self, app_id: str):
        return self._runner_for_app(app_id).prerequisites(app_id)

    def run(
        self,
        operation_id: str,
        parameters: Optional[Mapping[str, Any]] = None,
        *,
        session_token: str,
        file_tokens: Optional[Mapping[str, str]] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._runner_for_operation(operation_id).run(
            operation_id,
            parameters,
            session_token=session_token,
            file_tokens=file_tokens,
            run_id=run_id,
        )

    def handle(self, run_id: str) -> Optional[RunHandle]:
        matches = [handle for runner in self._runners.values() if (handle := runner.handle(run_id))]
        if len(matches) > 1:
            raise RepositoryRunnerUnavailable(f"run id collision across repositories: {run_id}")
        return matches[0] if matches else None

    def cancel(self, run_id: str) -> bool:
        matches = [runner for runner in self._runners.values() if runner.handle(run_id) is not None]
        if len(matches) > 1:
            raise RepositoryRunnerUnavailable(f"run id collision across repositories: {run_id}")
        return matches[0].cancel(run_id) if matches else False

    @property
    def repository_keys(self):
        return tuple(sorted(self._runners))
