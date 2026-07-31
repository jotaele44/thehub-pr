"""Shared offline helpers for ADR 0006 H08 dual-run readiness."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set

from jsonschema import Draft202012Validator


class DualRunReadinessError(ValueError):
    """Raised when dual-run evidence is incomplete, inconsistent, or mutable."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def as_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DualRunReadinessError(f"{name} must be an object")
    return value


def as_list(value: Any, name: str) -> List[Any]:
    if not isinstance(value, list):
        raise DualRunReadinessError(f"{name} must be an array")
    return value


def unique_index(records: Iterable[Mapping[str, Any]], key: str, name: str) -> Dict[str, Mapping[str, Any]]:
    result: Dict[str, Mapping[str, Any]] = {}
    for record in records:
        value = str(record.get(key) or "")
        if not value:
            raise DualRunReadinessError(f"{name} entry missing {key}")
        if value in result:
            raise DualRunReadinessError(f"duplicate {name} {key}: {value}")
        result[value] = record
    return result


def ensure_sha256(value: Any, name: str) -> str:
    text = str(value or "")
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise DualRunReadinessError(f"{name} must be lowercase sha256")
    return text


def ensure_revision(value: Any, name: str) -> str:
    text = str(value or "")
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise DualRunReadinessError(f"{name} must be lowercase 40-character revision")
    return text


def schema_directory(default_file: Path, explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return Path(explicit)
    return default_file.resolve().parents[2] / "schemas" / "contracts" / "skywatcher_ai"


def validate_schema_record(record: Mapping[str, Any], filename: str, schema_dir: Path) -> None:
    schema_path = schema_dir / filename
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DualRunReadinessError(f"cannot load schema {filename}") from exc
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(dict(record)),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        location = ".".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise DualRunReadinessError(
            f"{filename} validation failed at {location}: {errors[0].message}"
        )


def write_json_once(path: Path, value: Mapping[str, Any]) -> None:
    data = (canonical_json(dict(value)) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise DualRunReadinessError(f"immutable record conflict: {path.name}")
        return
    path.write_bytes(data)


def receipt_path(storage_root: Path, campaign_id: str) -> Path:
    return storage_root / "registry" / "dual_run_readiness" / f"{sha256_bytes(campaign_id.encode('utf-8'))}.json"


def replay_receipt(path: Path, input_digests: Mapping[str, str]) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DualRunReadinessError("existing readiness receipt is unreadable") from exc
    stored = current.get("input_digests")
    if stored != dict(input_digests):
        raise DualRunReadinessError(
            "changed campaign, lane, policy, comparison, or rollback evidence"
        )
    return current


def numeric(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DualRunReadinessError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise DualRunReadinessError(f"{name} must be finite")
    return result


def exact_key_set(records: Sequence[Mapping[str, Any]], key: str, name: str) -> Set[str]:
    return set(unique_index(records, key, name))
