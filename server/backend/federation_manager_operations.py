"""Signed operations policy: verification, typed parameters, and argv construction.

This is the executable half of the manager's trust model. The release catalog
(``federation_manager.py``) stays declarative and recursively rejects
command-bearing fields; executable intent lives here instead, in a separately
signed artifact.

The central property is that **no string is ever parsed into a command**. An
operation declares a target (an executable *identity*, not a path supplied by a
browser or a producer manifest) and an ordered ``argv`` list whose elements are
either fixed literals or references to schema-validated parameters. Argv is
assembled element by element; there is no shell, no interpolation, no splitting,
and no metacharacter to escape, because nothing is ever concatenated into a
command line.

Contrast with ``src/hub/fetch.py``: that module *does* parse producer command
strings, so it must defend with an executable allow-list, a metacharacter
denylist, and a model of Python's option parsing that rejects ``-m`` alongside
``-c``/``-e``. This module never parses, so ``python_module`` is safe here: the
module name is a fixed value in a signed policy, never operator input. The two
guards are deliberately different because they defend different pipelines.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Optional, Sequence

from jsonschema import Draft202012Validator

from server.backend.federation_manager import RELEASE_FORMAT_CHECKER

POLICY_SCHEMA_VERSION = "prii_operations_policy_v1"

#: Make targets the manager will drive. ``make`` is a temporary compatibility
#: adapter for producers that have not yet exposed a Python entry point; the
#: target name is matched against this set, never taken from a request.
ALLOWED_MAKE_TARGETS = frozenset({"validate-schemas"})

#: Parameter types whose value must resolve inside a managed root.
_PATH_TYPES = frozenset(
    {
        "directory",
        "managed_output_directory",
        "managed_file",
        "managed_sqlite_path",
        "file_token",
        "file_set_token",
    }
)

#: Token types are resolved by the file broker before they reach argv; the raw
#: token is an opaque handle, never a filesystem path from the browser.
_TOKEN_TYPES = frozenset({"file_token", "file_set_token"})

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-/]*$")
_MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


class OperationPolicyError(ValueError):
    """Base error for anything that makes a policy or operation untrustworthy."""


class PolicySignatureError(OperationPolicyError):
    """Signature, key, hash, expiry, or anti-rollback verification failed."""


class ParameterValidationError(OperationPolicyError):
    """A supplied parameter is absent, mistyped, or outside its declared bounds."""


class OperationDisabledError(OperationPolicyError):
    """The operation exists in the policy but is not enabled for execution."""


class PathContainmentError(OperationPolicyError):
    """A resolved path escaped its managed root."""


def canonical_json(value: Any) -> bytes:
    """Deterministic JSON encoding used for hashing and signing.

    Sorted keys and compact separators, so an identical document always produces
    an identical digest regardless of how it was serialised upstream.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


# ── Path containment ────────────────────────────────────────────────────────


def resolve_within(root: Path, candidate: str) -> Path:
    """Resolve ``candidate`` and require that it stays under ``root``.

    Rejects absolute paths, parent traversal, and symlinks whose target leaves
    the root. Every component is resolved, so a symlink partway along the path
    cannot smuggle the result outside the managed tree.
    """
    if candidate is None or candidate == "":
        raise PathContainmentError("empty path is not permitted")
    pure = PurePosixPath(candidate)
    if pure.is_absolute() or candidate.startswith("\\") or re.match(r"^[A-Za-z]:", candidate):
        raise PathContainmentError(f"absolute paths are not permitted: {candidate!r}")
    if any(part == ".." for part in pure.parts):
        raise PathContainmentError(f"parent traversal is not permitted: {candidate!r}")
    if "\x00" in candidate:
        raise PathContainmentError("null byte in path")

    root_resolved = root.resolve()
    target = (root_resolved / candidate).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise PathContainmentError(
            f"path escapes its managed root: {candidate!r} resolved outside {root_resolved}"
        ) from exc
    return target


# ── Policy model ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Target:
    kind: str
    identifier: str
    subcommand: Optional[str] = None


@dataclass(frozen=True)
class Operation:
    operation_id: str
    app_id: str
    repo: str
    category: str
    enablement: str
    target: Target
    parameters: Mapping[str, Mapping[str, Any]]
    argv: Sequence[Mapping[str, str]]
    risk_class: str
    approval_policy: str
    network_policy: str
    write_scope: str
    rollback_strategy: str
    promotion_state: str
    provenance: Mapping[str, Any]
    enablement_reason: str = ""
    secret_refs: Sequence[str] = field(default_factory=tuple)
    expected_outputs: Sequence[str] = field(default_factory=tuple)
    local_input_refs: Sequence[str] = field(default_factory=tuple)
    prerequisites: Sequence[str] = field(default_factory=tuple)

    @property
    def enabled(self) -> bool:
        return self.enablement == "ENABLED"


@dataclass(frozen=True)
class Policy:
    policy_id: str
    sequence: int
    minimum_accepted_sequence: int
    issued_at: str
    expires_at: str
    key_id: str
    payload_sha256: str
    security_invariants: Sequence[str]
    operations: Mapping[str, Operation]

    def require(self, operation_id: str) -> Operation:
        try:
            operation = self.operations[operation_id]
        except KeyError as exc:
            raise OperationPolicyError(f"unknown operation: {operation_id!r}") from exc
        if not operation.enabled:
            raise OperationDisabledError(
                f"operation {operation_id!r} is declared but not enabled: "
                f"{operation.enablement_reason or 'no reason recorded'}"
            )
        return operation


def _operation_from_mapping(raw: Mapping[str, Any]) -> Operation:
    target = raw["target"]
    return Operation(
        operation_id=raw["operation_id"],
        app_id=raw["app_id"],
        repo=raw["repo"],
        category=raw["category"],
        enablement=raw["enablement"],
        enablement_reason=raw.get("enablement_reason", ""),
        target=Target(
            kind=target["kind"],
            identifier=target["identifier"],
            subcommand=target.get("subcommand"),
        ),
        parameters=dict(raw["parameters"]),
        argv=tuple(dict(element) for element in raw["argv"]),
        risk_class=raw["risk_class"],
        approval_policy=raw["approval_policy"],
        network_policy=raw["network_policy"],
        write_scope=raw["write_scope"],
        rollback_strategy=raw["rollback_strategy"],
        promotion_state=raw["promotion_state"],
        provenance=dict(raw["provenance"]),
        secret_refs=tuple(raw.get("secret_refs", ())),
        expected_outputs=tuple(raw.get("expected_outputs", ())),
        local_input_refs=tuple(raw.get("local_input_refs", ())),
        prerequisites=tuple(raw.get("prerequisites", ())),
    )


# ── Verification ────────────────────────────────────────────────────────────


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise PolicySignatureError(f"policy timestamps must be timezone-aware: {value!r}")
    return parsed


def verify_policy(
    document: Mapping[str, Any],
    *,
    schema: Mapping[str, Any],
    public_key_pem: bytes,
    pinned_key_id: str,
    minimum_sequence: int = 1,
    now: Optional[datetime] = None,
) -> Policy:
    """Verify a signed policy document and return the usable policy.

    Checks, in order: schema; pinned key identity; Ed25519 signature over the
    canonical encoding of ``policy``; the recorded payload digest; expiry; and
    the anti-rollback sequence. Every one of these is fatal — there is no
    "warn and continue" path, because a policy the manager cannot fully trust is
    a policy that must not select an executable.
    """
    Draft202012Validator(schema, format_checker=RELEASE_FORMAT_CHECKER).validate(document)

    body = document["policy"]
    signature = document["signature"]

    if body["schema_version"] != POLICY_SCHEMA_VERSION:
        raise PolicySignatureError(f"unsupported policy schema version: {body['schema_version']!r}")

    if signature["key_id"] != pinned_key_id or body["key_id"] != pinned_key_id:
        raise PolicySignatureError(
            f"policy key {signature['key_id']!r} does not match the pinned key {pinned_key_id!r}"
        )

    payload = canonical_json(body)
    digest = sha256_hex(payload)
    if not _constant_time_equals(digest, signature["payload_sha256"]):
        raise PolicySignatureError("policy payload digest does not match the signed digest")

    _verify_ed25519(public_key_pem, payload, signature["value"])

    now = now or datetime.now(timezone.utc)
    if now >= _parse_timestamp(body["expires_at"]):
        raise PolicySignatureError(f"policy expired at {body['expires_at']}")
    if now < _parse_timestamp(body["issued_at"]):
        raise PolicySignatureError(f"policy is not yet valid; issued at {body['issued_at']}")

    floor = max(int(minimum_sequence), int(body["minimum_accepted_sequence"]))
    if int(body["sequence"]) < floor:
        raise PolicySignatureError(
            f"policy sequence {body['sequence']} is below the accepted floor {floor} (rollback rejected)"
        )

    operations: dict[str, Operation] = {}
    for raw in body["operations"]:
        operation = _operation_from_mapping(raw)
        if operation.operation_id in operations:
            raise OperationPolicyError(f"duplicate operation id: {operation.operation_id!r}")
        _validate_operation_shape(operation)
        operations[operation.operation_id] = operation

    return Policy(
        policy_id=body["policy_id"],
        sequence=int(body["sequence"]),
        minimum_accepted_sequence=int(body["minimum_accepted_sequence"]),
        issued_at=body["issued_at"],
        expires_at=body["expires_at"],
        key_id=body["key_id"],
        payload_sha256=digest,
        security_invariants=tuple(body["security_invariants"]),
        operations=operations,
    )


def _constant_time_equals(left: str, right: str) -> bool:
    import hmac as _hmac

    return _hmac.compare_digest(left, right)


def _verify_ed25519(public_key_pem: bytes, payload: bytes, signature_b64: str) -> None:
    import base64

    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    key = load_pem_public_key(public_key_pem)
    if not isinstance(key, Ed25519PublicKey):
        raise PolicySignatureError("pinned key is not an Ed25519 public key")
    try:
        key.verify(base64.b64decode(signature_b64, validate=True), payload)
    except (InvalidSignature, ValueError) as exc:
        raise PolicySignatureError("policy signature verification failed") from exc


def _validate_operation_shape(operation: Operation) -> None:
    """Structural checks the JSON Schema cannot express."""
    target = operation.target
    if not _IDENTIFIER_RE.match(target.identifier):
        raise OperationPolicyError(f"invalid target identifier: {target.identifier!r}")

    if target.kind == "console_script":
        if "/" in target.identifier or "\\" in target.identifier:
            # A bare name is resolved on PATH. Accepting a path here would let a
            # policy point at an arbitrary binary.
            raise OperationPolicyError(
                f"console_script target must be a bare name, got {target.identifier!r}"
            )
    elif target.kind == "python_module":
        if not _MODULE_RE.match(target.identifier):
            raise OperationPolicyError(f"invalid python module name: {target.identifier!r}")
    elif target.kind == "python_script":
        if PurePosixPath(target.identifier).is_absolute() or ".." in PurePosixPath(target.identifier).parts:
            raise OperationPolicyError(
                f"python_script target must be relative to the app root: {target.identifier!r}"
            )
    elif target.kind == "make_target":
        if target.identifier not in ALLOWED_MAKE_TARGETS:
            raise OperationPolicyError(f"make target is not allow-listed: {target.identifier!r}")

    for element in operation.argv:
        if "param" in element and element["param"] not in operation.parameters:
            raise OperationPolicyError(
                f"{operation.operation_id}: argv references undeclared parameter {element['param']!r}"
            )


# ── Typed parameter validation ──────────────────────────────────────────────
#
# Parameters are validated by _coerce below rather than by jsonschema. The
# checks a parameter needs -- null bytes, length ceilings, enum membership,
# absolute-path and parent-traversal refusal -- are argv-safety checks with no
# jsonschema `format` equivalent, so there is no FormatChecker here on purpose.
# Release manifests still go through jsonschema with RELEASE_FORMAT_CHECKER.


def validate_parameters(
    operation: Operation, supplied: Optional[Mapping[str, Any]] = None
) -> dict[str, Any]:
    """Validate operator-supplied values against the operation's declared types.

    Returns a dict of coerced values. Unknown keys are a hard error rather than
    being ignored: a caller sending a parameter this operation does not declare
    has misunderstood the contract, and silently dropping it would hide that.
    """
    supplied = dict(supplied or {})
    unknown = sorted(set(supplied) - set(operation.parameters))
    if unknown:
        raise ParameterValidationError(f"unknown parameters for {operation.operation_id}: {unknown}")

    resolved: dict[str, Any] = {}
    for name, spec in operation.parameters.items():
        kind = spec["type"]
        if kind == "fixed":
            if name in supplied and supplied[name] != spec.get("value"):
                raise ParameterValidationError(
                    f"{operation.operation_id}.{name} is fixed and cannot be overridden"
                )
            resolved[name] = spec.get("value")
            continue

        if name in supplied and supplied[name] is not None:
            value = supplied[name]
        elif "default" in spec:
            value = spec["default"]
        elif kind in _TOKEN_TYPES:
            # A file-token parameter takes its value from the token channel,
            # not from `parameters`. Requiring it here would demand the caller
            # send the same thing twice. Token presence is enforced by the
            # runner before execution and again by build_argv, which refuses to
            # emit argv without a staged path.
            resolved[name] = None
            continue
        elif spec.get("required"):
            raise ParameterValidationError(f"{operation.operation_id}.{name} is required")
        else:
            resolved[name] = None
            continue

        resolved[name] = _coerce(operation.operation_id, name, spec, value)

    return resolved


def _coerce(operation_id: str, name: str, spec: Mapping[str, Any], value: Any) -> Any:
    kind = spec["type"]
    label = f"{operation_id}.{name}"

    if kind == "boolean":
        if not isinstance(value, bool):
            raise ParameterValidationError(f"{label} must be a boolean")
        return value

    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ParameterValidationError(f"{label} must be an integer")
        return _check_bounds(label, spec, value)

    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ParameterValidationError(f"{label} must be a number")
        return _check_bounds(label, spec, float(value))

    if not isinstance(value, str):
        raise ParameterValidationError(f"{label} must be a string")
    if "\x00" in value:
        raise ParameterValidationError(f"{label} contains a null byte")
    max_length = int(spec.get("max_length", 4096))
    if len(value) > max_length:
        raise ParameterValidationError(f"{label} exceeds {max_length} characters")

    if kind == "enum":
        permitted = spec.get("values", ())
        if value not in permitted:
            raise ParameterValidationError(f"{label} must be one of {sorted(permitted)}")
        return value

    if kind == "datetime":
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ParameterValidationError(f"{label} must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None:
            raise ParameterValidationError(f"{label} must include a timezone offset")
        return value

    if kind == "string":
        pattern = spec.get("pattern")
        if pattern and not re.match(pattern, value):
            raise ParameterValidationError(f"{label} does not match {pattern!r}")
        return value

    if kind in _PATH_TYPES:
        extensions = spec.get("extensions")
        if extensions and not any(value.endswith(ext) for ext in extensions):
            raise ParameterValidationError(f"{label} must end with one of {sorted(extensions)}")
        # Containment is enforced at argv-build time against the run's managed
        # roots; here we only reject shapes that can never be contained.
        if value.startswith("/") or value.startswith("\\") or re.match(r"^[A-Za-z]:", value):
            raise ParameterValidationError(f"{label} must be relative to a managed root")
        if ".." in PurePosixPath(value).parts:
            raise ParameterValidationError(f"{label} must not contain parent traversal")
        return value

    raise ParameterValidationError(f"{label} has an unsupported parameter type {kind!r}")


def _check_bounds(label: str, spec: Mapping[str, Any], value: Any) -> Any:
    if "minimum" in spec and value < spec["minimum"]:
        raise ParameterValidationError(f"{label} must be >= {spec['minimum']}")
    if "maximum" in spec and value > spec["maximum"]:
        raise ParameterValidationError(f"{label} must be <= {spec['maximum']}")
    return value


# ── Argv construction ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExecutionContext:
    """Everything argv construction is allowed to know about the filesystem."""

    app_root: Path
    data_root: Path
    staging_root: Path
    #: Where the file broker stages operator-selected inputs. Separate from
    #: staging_root because intake holds copies of the operator's own files,
    #: which have a different lifetime and a different audit story from the
    #: manager's own scratch space.
    intake_root: Optional[Path] = None
    python_executable: str = "python3"
    make_executable: str = "make"

    def managed_roots(self) -> tuple[Path, ...]:
        roots = [self.staging_root, self.data_root, self.app_root]
        if self.intake_root is not None:
            roots.append(self.intake_root)
        return tuple(roots)


@dataclass(frozen=True)
class BuiltCommand:
    argv: tuple[str, ...]
    cwd: Path
    resolved_paths: Mapping[str, Path]

    @property
    def argv_sha256(self) -> str:
        return sha256_hex(canonical_json(list(self.argv)))


def build_argv(
    operation: Operation,
    parameters: Mapping[str, Any],
    context: ExecutionContext,
    *,
    token_paths: Optional[Mapping[str, Path]] = None,
) -> BuiltCommand:
    """Assemble the argv list for an enabled operation.

    Every element is either a policy literal or a validated parameter. Nothing is
    concatenated, so there is no command line for a shell to reinterpret — the
    list goes straight to ``Popen`` with ``shell=False``.
    """
    if not operation.enabled:
        raise OperationDisabledError(
            f"operation {operation.operation_id!r} is not enabled: "
            f"{operation.enablement_reason or 'no reason recorded'}"
        )

    token_paths = dict(token_paths or {})
    argv = list(_target_prefix(operation, context))
    resolved: dict[str, Path] = {}

    for element in operation.argv:
        if "literal" in element:
            argv.append(element["literal"])
            continue

        name = element["param"]
        spec = operation.parameters[name]
        value = parameters.get(name)
        kind = spec["type"]

        if kind == "boolean" or (kind == "fixed" and isinstance(value, bool)):
            # A boolean drives the *preceding* literal flag: when false, drop the
            # flag that was just appended rather than emitting "--flag false".
            if not value and spec.get("omit_when_false", True):
                if argv and argv[-1].startswith("-"):
                    argv.pop()
            continue

        if kind in _TOKEN_TYPES:
            # Checked before the None branch below: a token parameter's value
            # always arrives through token_paths, never through `parameters`,
            # so a resolved value of None is normal rather than "omitted".
            staged = token_paths.get(name)
            if staged is None:
                raise ParameterValidationError(
                    f"{operation.operation_id}.{name} is a file token but no staged path was provided"
                )
            contained = _require_contained(staged, context)
            resolved[name] = contained
            argv.append(str(contained))
            continue

        if value is None:
            # An optional parameter with no value drops its own flag too.
            if argv and argv[-1].startswith("-"):
                argv.pop()
            continue

        if kind in _PATH_TYPES:
            base = context.staging_root if kind == "managed_output_directory" else context.data_root
            contained = resolve_within(base, str(value))
            resolved[name] = contained
            argv.append(str(contained))
            continue

        if isinstance(value, (list, tuple)):
            argv.extend(str(item) for item in value)
            continue

        argv.append(str(value))

    return BuiltCommand(argv=tuple(argv), cwd=context.app_root, resolved_paths=resolved)


def _require_contained(candidate: Path, context: ExecutionContext) -> Path:
    resolved = candidate.resolve()
    for root in context.managed_roots():
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return resolved
    raise PathContainmentError(f"staged path is outside every managed root: {resolved}")


def _target_prefix(operation: Operation, context: ExecutionContext) -> list[str]:
    target = operation.target
    if target.kind == "console_script":
        prefix = [target.identifier]
    elif target.kind == "python_module":
        prefix = [context.python_executable, "-m", target.identifier]
    elif target.kind == "python_script":
        script = resolve_within(context.app_root, target.identifier)
        if not script.is_file():
            raise OperationPolicyError(f"python_script target does not exist: {target.identifier}")
        prefix = [context.python_executable, str(script)]
    elif target.kind == "make_target":
        if target.identifier not in ALLOWED_MAKE_TARGETS:
            raise OperationPolicyError(f"make target is not allow-listed: {target.identifier!r}")
        prefix = [context.make_executable, target.identifier]
    elif target.kind == "internal_builtin":
        raise OperationPolicyError(
            f"{operation.operation_id} is an internal builtin and has no argv; "
            "it must be dispatched to a manager handler instead"
        )
    elif target.kind == "composite_unresolved":
        raise OperationPolicyError(
            f"{operation.operation_id} is still a shell composite and has not been decomposed; "
            "it is non-executable by construction"
        )
    else:  # pragma: no cover - schema-constrained
        raise OperationPolicyError(f"unsupported target kind: {target.kind!r}")

    if target.subcommand:
        prefix.append(target.subcommand)
    return prefix


# ── Loading ─────────────────────────────────────────────────────────────────


def load_policy_document(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def accounting_summary(document: Mapping[str, Any]) -> dict[str, Any]:
    """Count declared, enabled, and deferred operations.

    Gate G04 asks for accounting, not universal enablement: every declared
    operation must appear with an explicit classification and zero rows may be
    left unclassified.
    """
    operations: Iterable[Mapping[str, Any]] = document["policy"]["operations"]
    by_app: dict[str, int] = {}
    enabled = 0
    deferred = 0
    unclassified: list[str] = []
    for raw in operations:
        by_app[raw["app_id"]] = by_app.get(raw["app_id"], 0) + 1
        if raw.get("enablement") == "ENABLED":
            enabled += 1
        elif raw.get("enablement") == "DECLARED_NOT_ENABLED":
            deferred += 1
            if not raw.get("enablement_reason"):
                unclassified.append(raw["operation_id"])
        else:
            unclassified.append(raw["operation_id"])
    return {
        "total": enabled + deferred + len(unclassified),
        "enabled": enabled,
        "declared_not_enabled": deferred,
        "unclassified": sorted(unclassified),
        "by_app": dict(sorted(by_app.items())),
    }
