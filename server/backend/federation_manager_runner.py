"""Run orchestration: policy to receipt, in one supervised pipeline.

Composes the pieces that already exist -- signed policy, typed parameters,
argv construction, file staging, the secrets broker, the transaction, the
process supervisor, and the receipt store -- into a single run. It deliberately
holds no policy of its own: every decision it makes is one the policy already
declared.

Kept separate from ``federation_manager_operations`` so that module stays a
pure function of its inputs (parse, verify, validate, build) and remains
testable without a filesystem, a process, or a clock.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from server.backend.federation_manager_files import (
    FileTokenBroker,
    diff_paths,
    discard_run_intake,
    observed_paths,
    stage_operation_inputs,
    unexpected_writes,
)
from server.backend.federation_manager_operations import (
    ExecutionContext,
    Operation,
    Policy,
    build_argv,
    validate_parameters,
)
from server.backend.federation_manager_process import (
    DEFAULT_ENV_ALLOWLIST,
    ProcessLimits,
    Redactor,
    build_environment,
    redact_argv,
    redact_environment_names,
    run_process,
)
from server.backend.federation_manager_receipts import (
    ReceiptInputs,
    ReceiptStore,
    new_run_id,
    utc_now_iso,
)
from server.backend.federation_manager_secrets import SecretBroker
from server.backend.federation_manager_transactions import (
    Phase,
    RollbackFailed,
    RollbackState,
    Transaction,
    TransactionError,
    require_strategy,
)

TOKEN_PARAMETER_TYPES = frozenset({"file_token", "file_set_token"})


class RunRefused(RuntimeError):
    """The run was refused before anything was executed."""


@dataclass
class RunPlan:
    """What a run *would* do. Returned by the plan endpoint, never executed."""

    operation_id: str
    app_id: str
    argv_preview: Sequence[str]
    parameters: Mapping[str, Any]
    write_scope: str
    risk_class: str
    approval_policy: str
    network_policy: str
    rollback_strategy: str
    required_secrets: Sequence[str] = field(default_factory=tuple)
    missing_secrets: Sequence[str] = field(default_factory=tuple)
    expected_outputs: Sequence[str] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "operationId": self.operation_id,
            "appId": self.app_id,
            "argvPreview": list(self.argv_preview),
            "parameters": dict(self.parameters),
            "writeScope": self.write_scope,
            "riskClass": self.risk_class,
            "approvalPolicy": self.approval_policy,
            "networkPolicy": self.network_policy,
            "rollbackStrategy": self.rollback_strategy,
            "requiredSecrets": list(self.required_secrets),
            "missingSecrets": list(self.missing_secrets),
            "expectedOutputs": list(self.expected_outputs),
            "warnings": list(self.warnings),
        }


@dataclass
class RunHandle:
    """A live run, for cancellation and log subscription."""

    run_id: str
    operation_id: str
    app_id: str
    cancel_event: threading.Event = field(default_factory=threading.Event)
    lines: List[str] = field(default_factory=list)
    finished: threading.Event = field(default_factory=threading.Event)
    status: str = "running"
    subscribers: List[Callable[[str], None]] = field(default_factory=list)

    def publish(self, line: str) -> None:
        self.lines.append(line)
        for subscriber in list(self.subscribers):
            try:
                subscriber(line)
            except Exception:  # noqa: BLE001 - a dead subscriber must not kill the run
                self.subscribers.remove(subscriber)

    def cancel(self) -> None:
        self.cancel_event.set()


class OperationRunner:
    """Executes enabled operations and records what happened."""

    def __init__(
        self,
        *,
        policy: Policy,
        context: ExecutionContext,
        receipts: ReceiptStore,
        files: FileTokenBroker,
        secrets: SecretBroker,
        limits: Optional[ProcessLimits] = None,
        env_allowlist: Sequence[str] = DEFAULT_ENV_ALLOWLIST,
    ):
        self.policy = policy
        # The file broker's intake directory is a managed root too, so path
        # containment must know about it. Filling it in here rather than asking
        # every caller to keep the two in sync removes a way to get it wrong.
        self.context = (
            context
            if context.intake_root is not None
            else replace(context, intake_root=files.intake_root)
        )
        self.receipts = receipts
        self.files = files
        self.secrets = secrets
        self.limits = limits or ProcessLimits()
        self.env_allowlist = tuple(env_allowlist)
        self._runs: Dict[str, RunHandle] = {}

    # ── plan ────────────────────────────────────────────────────────────────

    def plan(
        self,
        operation_id: str,
        parameters: Optional[Mapping[str, Any]] = None,
        *,
        session_token: str = "",
    ) -> RunPlan:
        """Validate everything and describe the run without executing it.

        The argv preview substitutes a placeholder for file tokens: at plan time
        nothing has been staged, and inventing a path would show the operator
        something that will not be what actually runs.
        """
        operation = self.policy.require(operation_id)
        resolved = validate_parameters(operation, parameters)
        warnings: List[str] = []

        token_names = {
            name
            for name, spec in operation.parameters.items()
            if spec["type"] in TOKEN_PARAMETER_TYPES
        }
        placeholder = self.context.staging_root / "<staged-at-run-time>"
        try:
            built = build_argv(
                operation,
                resolved,
                self.context,
                token_paths={name: placeholder for name in token_names},
            )
            argv_preview = list(built.argv)
        except Exception as exc:  # noqa: BLE001 - reported to the operator as a warning
            argv_preview = []
            warnings.append(f"argv could not be previewed: {exc}")

        try:
            require_strategy(operation.rollback_strategy)
        except TransactionError as exc:
            warnings.append(str(exc))

        missing: Sequence[str] = ()
        if operation.secret_refs:
            try:
                missing = self.secrets.missing(operation.app_id, operation.secret_refs)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"secret presence could not be checked: {exc}")

        return RunPlan(
            operation_id=operation.operation_id,
            app_id=operation.app_id,
            argv_preview=argv_preview,
            parameters=resolved,
            write_scope=operation.write_scope,
            risk_class=operation.risk_class,
            approval_policy=operation.approval_policy,
            network_policy=operation.network_policy,
            rollback_strategy=operation.rollback_strategy,
            required_secrets=tuple(operation.secret_refs),
            missing_secrets=tuple(missing),
            expected_outputs=tuple(operation.expected_outputs),
            warnings=tuple(warnings),
        )

    # ── prerequisites ───────────────────────────────────────────────────────

    def prerequisites(self, app_id: str) -> List[Dict[str, str]]:
        """Machine-detected readiness, with an actionable step for each gap.

        Every item is *observed* rather than declared: whether the executable
        actually resolves, whether the roots exist, whether the credential
        store answers. A list built from the policy's prose ``prerequisites``
        strings would look the same and tell an operator nothing about their
        own machine.
        """
        import shutil

        checks: List[Dict[str, str]] = []

        def add(name: str, ok: bool, detail: str, remediation: str = "") -> None:
            checks.append(
                {
                    "name": name,
                    "status": "met" if ok else "unmet",
                    "detail": detail,
                    "remediation": "" if ok else remediation,
                }
            )

        add(
            "Signed operations policy",
            True,
            f"policy {self.policy.policy_id} sequence {self.policy.sequence}, "
            f"expires {self.policy.expires_at}",
        )

        app_root = self.context.app_root
        add(
            "Application root",
            app_root.is_dir(),
            str(app_root),
            "The managed application directory is missing. Install or repair the app first.",
        )

        executables = sorted(
            {
                op.target.identifier
                for op in self.policy.operations.values()
                if op.enabled and op.app_id == app_id and op.target.kind == "console_script"
            }
        )
        for executable in executables:
            resolved = shutil.which(executable)
            add(
                f"Console script: {executable}",
                bool(resolved),
                resolved or "not found on PATH",
                f"Install the {app_id} application environment so `{executable}` is on PATH.",
            )

        data_root = self.context.data_root
        writable = data_root.is_dir() and os.access(str(data_root), os.W_OK)
        add(
            "Managed data root",
            writable,
            str(data_root),
            "The managed data directory is missing or not writable.",
        )

        receipt_root = self.receipts.root
        add(
            "Receipt store",
            receipt_root.is_dir() and os.access(str(receipt_root), os.W_OK),
            str(receipt_root),
            "Receipts cannot be written, so no run could produce gate evidence.",
        )

        from server.backend.federation_manager_secrets import provider_description

        description = provider_description(self.secrets.provider)
        required = sorted(
            {
                secret
                for op in self.policy.operations.values()
                if op.app_id == app_id
                for secret in op.secret_refs
            }
        )
        if required:
            add(
                "Credential store",
                bool(description["available"]),
                f"{description['provider']} (persistent: {description['persistent']})",
                "No OS credential provider is available, so credentials cannot be stored.",
            )

        return checks

    # ── run ─────────────────────────────────────────────────────────────────

    def handle(self, run_id: str) -> Optional[RunHandle]:
        return self._runs.get(run_id)

    def cancel(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run is None or run.finished.is_set():
            return False
        run.cancel()
        return True

    def run(
        self,
        operation_id: str,
        parameters: Optional[Mapping[str, Any]] = None,
        *,
        session_token: str,
        file_tokens: Optional[Mapping[str, str]] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute one operation end to end and return its signed receipt."""
        operation = self.policy.require(operation_id)
        strategy = require_strategy(operation.rollback_strategy)
        resolved = validate_parameters(operation, parameters)

        # Refusals that happen before anything executes are raised here rather
        # than inside the run, so they surface as a caller error and produce no
        # receipt. A receipt for a run that never started would be a misleading
        # entry in the evidence chain.
        token_specs = {
            name: spec
            for name, spec in operation.parameters.items()
            if spec["type"] in TOKEN_PARAMETER_TYPES
        }
        supplied_tokens = dict(file_tokens or {})
        absent = sorted(set(token_specs) - set(supplied_tokens))
        if absent:
            raise RunRefused(f"missing file tokens for: {absent}")
        unexpected = sorted(set(supplied_tokens) - set(token_specs))
        if unexpected:
            raise RunRefused(f"file tokens supplied for non-token parameters: {unexpected}")

        run_id = run_id or new_run_id()
        handle = RunHandle(run_id=run_id, operation_id=operation_id, app_id=operation.app_id)
        self._runs[run_id] = handle

        started_at = utc_now_iso()
        tx = Transaction(strategy, self.context.staging_root, run_id)
        tx.enter(Phase.PLAN)

        inputs: List[Dict[str, Any]] = []
        validators: List[Dict[str, Any]] = []
        env_names: List[str] = []
        argv_redacted: List[str] = []
        argv_sha256 = ""
        status = "failed"
        exit_code: Optional[int] = None
        log_sha256 = ""
        log_bytes = 0
        log_truncated = False
        log_redactions = 0

        try:
            # PREFLIGHT: stage every file token and inspect the staged copy.
            tx.enter(Phase.PREFLIGHT)
            token_paths: Dict[str, Path] = {}
            if token_specs:
                token_paths, inputs, preflights = stage_operation_inputs(
                    self.files,
                    session_token=session_token,
                    app_id=operation.app_id,
                    run_id=run_id,
                    token_parameters=supplied_tokens,
                    specs=token_specs,
                )
                for record in preflights:
                    for check in record["checks"]:
                        validators.append(
                            {
                                "name": f"preflight.{record['logical_name']}.{check['name']}",
                                "status": check["status"],
                                "detail": check.get("detail", ""),
                            }
                        )

            built = build_argv(operation, resolved, self.context, token_paths=token_paths)
            argv_redacted = redact_argv(built.argv)
            argv_sha256 = built.argv_sha256

            # Create the parent of every managed output path. The child is a
            # producer CLI that generally will not mkdir -p for us, and failing
            # for a missing directory the manager itself chose is a confusing
            # way to lose a run. Containment was already enforced by build_argv,
            # so these paths are known to be inside a managed root.
            for name, resolved_path in built.resolved_paths.items():
                kind = operation.parameters[name]["type"]
                if kind == "managed_output_directory":
                    resolved_path.mkdir(parents=True, exist_ok=True)
                elif kind in ("managed_file", "managed_sqlite_path"):
                    resolved_path.parent.mkdir(parents=True, exist_ok=True)

            # SNAPSHOT: inventory the write scope so post-run drift is detectable.
            tx.enter(Phase.SNAPSHOT)
            audit_root = self.context.data_root
            before = observed_paths(audit_root)

            # EXECUTE: environment is deny-by-default; secrets go in via the sink.
            tx.enter(Phase.EXECUTE_IN_STAGING)
            env = build_environment(
                self.env_allowlist,
                extra={"PRII_APP_ROOT": str(self.context.app_root)},
            )
            if operation.secret_refs:
                self.secrets.inject_into_env(operation.app_id, operation.secret_refs, env)
            env_names = redact_environment_names(env)

            with self.secrets.collect_redaction_values(
                operation.app_id, operation.secret_refs
            ) as redaction:
                result = run_process(
                    built.argv,
                    cwd=built.cwd,
                    env=env,
                    limits=self.limits,
                    on_line=handle.publish,
                    cancel_event=handle.cancel_event,
                    redactor=Redactor(redaction.values()),
                )

            exit_code = result.exit_code
            log_sha256 = result.log_sha256
            log_bytes = result.log_bytes
            log_truncated = result.truncated
            log_redactions = result.redactions

            # VALIDATE
            tx.enter(Phase.VALIDATE)
            validators.append(
                {
                    "name": "exit_code",
                    "status": "passed" if result.succeeded else "failed",
                    "detail": f"exit {result.exit_code}",
                }
            )

            after = observed_paths(audit_root)
            offending = unexpected_writes(
                diff_paths(before, after), _declared_write_scopes(operation, built, self.context)
            )
            if offending:
                tx.record_write_audit(offending)
                validators.append(
                    {
                        "name": "write_scope",
                        "status": "failed",
                        "detail": (
                            f"wrote outside its declared outputs "
                            f"({operation.write_scope}): {offending[:5]}"
                        ),
                    }
                )
            else:
                validators.append({"name": "write_scope", "status": "passed"})

            if result.status == "cancelled":
                status = "cancelled"
            elif result.status == "timed_out":
                status = "timed_out"
            elif not result.succeeded:
                status = "failed"
            elif offending:
                # A run that wrote outside its declared scope is quarantined even
                # though the process itself exited zero.
                status = "quarantined"
            else:
                tx.enter(Phase.COMMIT)
                tx.mark_committed()
                status = "succeeded"

            if status != "succeeded" and tx.record.rollback_state is RollbackState.NOT_REQUIRED:
                tx.record.rollback_state = RollbackState.NOT_REQUIRED

        except RollbackFailed as exc:
            status = "rolled_back"
            tx.record.rollback_state = RollbackState.FAILED
            tx.record.rollback_detail = str(exc)
        except Exception as exc:  # noqa: BLE001 - every failure still emits a receipt
            status = "failed"
            validators.append({"name": "runner", "status": "failed", "detail": str(exc)})
            if tx.record.phase_reached in (Phase.COMMIT, Phase.RECEIPT):
                try:
                    tx.rollback(str(exc))
                except RollbackFailed as rollback_exc:
                    tx.record.rollback_detail = str(rollback_exc)
        finally:
            tx.discard_staging()
            discard_run_intake(self.files.run_intake_dir(run_id).parent.parent, run_id)
            handle.status = status
            handle.finished.set()

        tx.enter(Phase.RECEIPT)
        document = self.receipts.append(
            ReceiptInputs(
                run_id=run_id,
                operation_id=operation.operation_id,
                app_id=operation.app_id,
                policy_id=self.policy.policy_id,
                policy_sequence=self.policy.sequence,
                policy_sha256=self.policy.payload_sha256,
                policy_key_id=self.policy.key_id,
                status=status,
                started_at=started_at,
                finished_at=utc_now_iso(),
                argv_redacted=argv_redacted,
                argv_sha256=argv_sha256 or "0" * 64,
                parameters_redacted=_redact_parameters(operation, resolved),
                environment_allowlist=env_names,
                transaction=tx.record.as_receipt(),
                log_sha256=log_sha256 or "0" * 64,
                log_bytes=log_bytes,
                log_truncated=log_truncated,
                log_redactions=log_redactions,
                exit_code=exit_code,
                inputs=inputs,
                outputs=[],
                validators=validators,
            )
        )
        return document


#: Parameter types whose resolved path is somewhere the operation may write.
_OUTPUT_TYPES = frozenset({"managed_output_directory", "managed_file", "managed_sqlite_path"})

#: SQLite writes these alongside the database itself.
_SQLITE_SIDECARS = ("-wal", "-shm", "-journal")


def _declared_write_scopes(operation: Operation, built, context) -> List[str]:
    """The paths this run is permitted to touch, relative to the data root.

    Derived from the run's own resolved output parameters rather than from the
    catalog's ``write_scope``, which is prose ("managed SQLite database") and
    can never match a path. Comparing paths against prose flagged every write
    as unexpected and quarantined runs that had done nothing wrong.

    A read-only operation yields an empty list, which correctly means *any*
    write is unexpected.
    """
    scopes: List[str] = []
    data_root = context.data_root.resolve()
    for name, resolved_path in built.resolved_paths.items():
        if operation.parameters[name]["type"] not in _OUTPUT_TYPES:
            continue
        try:
            relative = resolved_path.resolve().relative_to(data_root)
        except ValueError:
            continue
        scopes.append(str(relative))
        if operation.parameters[name]["type"] == "managed_sqlite_path":
            scopes.extend(f"{relative}{suffix}" for suffix in _SQLITE_SIDECARS)
    return scopes


def _redact_parameters(operation: Operation, resolved: Mapping[str, Any]) -> Dict[str, Any]:
    """Parameters as recorded in the receipt, with secret-shaped names masked."""
    from server.backend.federation_manager import redact_technical_details

    payload = {
        name: (str(value) if isinstance(value, Path) else value)
        for name, value in resolved.items()
    }
    return redact_technical_details(payload)
