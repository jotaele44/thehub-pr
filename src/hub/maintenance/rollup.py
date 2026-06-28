"""Load producer maintenance reports from a workspace and aggregate them.

Filesystem-local, like ``federation_status``: it does not clone, fetch, or run
producer commands. Each producer is expected to have written
``reports/maintenance/latest.json`` (audit mode) which the Hub validates against
``maintenance_report.schema.json`` and rolls up.
"""
from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import jsonschema

from .._schemas import load_schema
from ..federation_status import _producer_base
from ..registry import Registry
from .gate import compute_gate

MAINTENANCE_VERSION = "0.1.0"
REPORT_RELPATH = "reports/maintenance/latest.json"


def _report_validator() -> "jsonschema.Draft7Validator":
    """Draft-07 validator for maintenance_report with the finding $ref resolvable."""
    report_schema = load_schema("maintenance_report.schema.json")
    finding_schema = load_schema("maintenance_finding.schema.json")
    store = {
        report_schema["$id"]: report_schema,
        finding_schema["$id"]: finding_schema,
    }
    # RefResolver is deprecated in jsonschema>=4.18 but is the only cross-file
    # resolver available across the declared floor (jsonschema>=4.0). Suppress
    # the deprecation locally; behaviour is unchanged.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        resolver = jsonschema.RefResolver.from_schema(report_schema, store=store)
    return jsonschema.Draft7Validator(report_schema, resolver=resolver)


def validate_report(data: Any) -> List[str]:
    """Return a list of schema-validation error strings (empty if valid)."""
    validator = _report_validator()
    errors: List[str] = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path)
        errors.append(f"{loc}: {err.message}" if loc else err.message)
    return errors


def build_rollup(
    registry: Registry,
    root: str | Path = "..",
    *,
    maintenance_version: str = MAINTENANCE_VERSION,
) -> Dict[str, Any]:
    """Aggregate every registered producer's maintenance report into a rollup dict."""
    root_path = Path(root)
    repo_status: Dict[str, Any] = {}
    reports_missing = 0
    reports_invalid = 0
    findings_total = 0
    critical_total = 0

    for producer in registry.producers:
        base = _producer_base(root_path, producer)
        report_path = base / REPORT_RELPATH
        status: Dict[str, Any] = {
            "report_present": False,
            "report_valid": False,
            "findings_count": 0,
            "critical_count": 0,
            "promotion_blocked": False,
            "errors": [],
        }

        if not report_path.exists():
            reports_missing += 1
            status["errors"].append("maintenance report missing")
            repo_status[producer.program_id] = status
            continue

        status["report_present"] = True
        try:
            data = json.loads(report_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            reports_invalid += 1
            status["errors"].append(f"unreadable report: {exc}")
            repo_status[producer.program_id] = status
            continue

        schema_errors = validate_report(data)
        if schema_errors:
            reports_invalid += 1
            status["report_valid"] = False
            status["errors"].extend(schema_errors[:10])
        else:
            status["report_valid"] = True

        status["findings_count"] = int(data.get("findings_count", 0))
        status["critical_count"] = int(data.get("critical_count", 0))
        status["promotion_blocked"] = bool(data.get("promotion_blocked", False))
        findings_total += status["findings_count"]
        critical_total += status["critical_count"]
        repo_status[producer.program_id] = status

    rollup: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "maintenance_version": maintenance_version,
        "producer_count": len(registry.producers),
        "reports_missing": reports_missing,
        "reports_invalid": reports_invalid,
        "findings_count": findings_total,
        "critical_count": critical_total,
        "repo_status": repo_status,
    }
    rollup.update(compute_gate(rollup))
    return rollup
