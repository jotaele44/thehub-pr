"""Shared immutable H05 receipt utilities with no network or credential access."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

_FORBIDDEN_SECRET_KEYS = {
    "api_key",
    "secret",
    "secret_value",
    "token",
    "access_token",
    "password",
    "credential_value",
    "authorization_header",
}


class EgressPolicyError(RuntimeError):
    """Raised when an immutable H05 receipt cannot be handled safely."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _artifact_id(digest: str) -> str:
    return "artifact-sha256-" + digest


def _safe_write_once(path: Path, data: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise EgressPolicyError("immutable path content conflict: " + str(path))
        return False
    fd, temporary_name = tempfile.mkstemp(prefix=".h05-", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(str(temporary), str(path))
            return True
        except FileExistsError:
            if path.read_bytes() != data:
                raise EgressPolicyError(
                    "immutable path content conflict: " + str(path)
                )
            return False
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_once(path: Path, value: Mapping[str, Any]) -> bool:
    return _safe_write_once(path, _canonical_bytes(dict(value)) + b"\n")


def _load_json(path: Path, label: str) -> Dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise EgressPolicyError(label + " must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EgressPolicyError(label + " is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise EgressPolicyError(label + " must contain a JSON object")
    return value


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any) -> Optional[List[str]]:
    if not isinstance(value, list):
        return None
    result = [str(item) for item in value]
    if any(not item for item in result) or len(result) != len(set(result)):
        return None
    return result


def _contains_secret_material(value: Any) -> bool:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key).lower()
            if (
                key in _FORBIDDEN_SECRET_KEYS
                or key.endswith("_secret")
                or key.endswith("_token")
                or key.endswith("_password")
                or key.endswith("_api_key")
            ):
                return True
            if _contains_secret_material(child):
                return True
    elif isinstance(value, list):
        return any(_contains_secret_material(child) for child in value)
    return False
