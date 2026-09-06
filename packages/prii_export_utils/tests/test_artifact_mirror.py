from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from prii_export_utils.artifact_mirror import (
    InvalidMirrorError,
    build_mirror_payload,
    read_canonical_envelope,
    verify_mirror_payload,
)
from prii_export_utils.artifact_transport import emit_message, sha256_bytes

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA = REPO_ROOT / "schemas" / "contracts" / "federation_artifact_mirror.v1.schema.json"


def _message(tmp_path: Path):
    return emit_message(
        tmp_path,
        source="centinelas-pr",
        target="moneysweep-pr",
        kind="centinelas-handoff",
        idempotency_key="signal-17-moneysweep-pr",
        payload={"signal": {"item_id": "17", "labels": ["FINANCIAL"]}},
    )


def test_exact_byte_mirror_round_trip(tmp_path: Path) -> None:
    emitted = _message(tmp_path)
    payload = build_mirror_payload(emitted.path)
    envelope, data = verify_mirror_payload(payload)

    assert envelope["message_id"] == emitted.message_id
    assert data == emitted.path.read_bytes()
    assert payload["envelope_size"] == len(data)
    assert payload["envelope_sha256"] == sha256_bytes(data)


def test_mirror_schema_matches_runtime_contract() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == "prii.artifact-mirror.v1"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "message_id",
        "source",
        "target",
        "kind",
        "envelope_size",
        "envelope_sha256",
        "envelope_base64",
    }


def test_noncanonical_envelope_file_is_rejected(tmp_path: Path) -> None:
    emitted = _message(tmp_path)
    value = json.loads(emitted.path.read_text(encoding="utf-8"))
    emitted.path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(InvalidMirrorError, match="not canonical"):
        read_canonical_envelope(emitted.path)


def test_symlink_envelope_is_rejected(tmp_path: Path) -> None:
    emitted = _message(tmp_path)
    linked = tmp_path / "linked.json"
    try:
        linked.symlink_to(emitted.path)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")

    with pytest.raises(InvalidMirrorError, match="regular file"):
        build_mirror_payload(linked)


def test_invalid_base64_is_rejected(tmp_path: Path) -> None:
    payload = build_mirror_payload(_message(tmp_path).path)
    payload["envelope_base64"] = "not base64!"

    with pytest.raises(InvalidMirrorError, match="canonical base64"):
        verify_mirror_payload(payload)


def test_byte_hash_tampering_is_rejected(tmp_path: Path) -> None:
    payload = build_mirror_payload(_message(tmp_path).path)
    data = base64.b64decode(payload["envelope_base64"])
    tampered = data.replace(b"FINANCIAL", b"POLITICAL")
    payload["envelope_base64"] = base64.b64encode(tampered).decode("ascii")
    payload["envelope_size"] = len(tampered)

    with pytest.raises(InvalidMirrorError, match="envelope_sha256"):
        verify_mirror_payload(payload)


def test_wrapper_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    payload = build_mirror_payload(_message(tmp_path).path)
    payload["target"] = "thehub-pr"

    with pytest.raises(InvalidMirrorError, match="target does not bind"):
        verify_mirror_payload(payload)


def test_unknown_wrapper_fields_fail_closed(tmp_path: Path) -> None:
    payload = build_mirror_payload(_message(tmp_path).path)
    payload["unexpected"] = True

    with pytest.raises(InvalidMirrorError, match="fields mismatch"):
        verify_mirror_payload(payload)


def test_duplicate_embedded_json_keys_are_rejected(tmp_path: Path) -> None:
    payload = build_mirror_payload(_message(tmp_path).path)
    data = base64.b64decode(payload["envelope_base64"])
    duplicate = data.replace(
        b'{"created_at_utc"', b'{"source":"evil","created_at_utc"'
    )
    payload["envelope_base64"] = base64.b64encode(duplicate).decode("ascii")
    payload["envelope_size"] = len(duplicate)
    payload["envelope_sha256"] = sha256_bytes(duplicate)

    with pytest.raises(InvalidMirrorError, match="duplicate JSON key: source"):
        verify_mirror_payload(payload)


def test_boolean_size_is_rejected(tmp_path: Path) -> None:
    payload = build_mirror_payload(_message(tmp_path).path)
    payload["envelope_size"] = True

    with pytest.raises(InvalidMirrorError, match="positive integer"):
        verify_mirror_payload(payload)
