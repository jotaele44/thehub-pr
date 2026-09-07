#!/usr/bin/env python3
"""Validate a bounded seven-app release evidence bundle; never issue certification.

All receipt paths are relative to the bundle, and all hashes refer to raw bytes.
This checks evidence integrity/accounting, not the truth of operator assertions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORIES = tuple(f"{name}-pr" for name in (
    "thehub", "aguayluz", "ovnis", "moneysweep", "centinelas", "spiderweb", "skywatcher"
))
AXES = (
    "engineering", "main_branch_availability", "ci_enforcement", "data_materialization",
    "product_ui", "operator_platform_readiness", "federation_readiness",
)
PLATFORMS = ("macos", "windows", "linux")
JOURNEY = ("install", "launch", "setup", "domain_workflow", "export", "restart_recovery", "upgrade", "rollback")
CLAIM_TYPES = {"FACT", "COMPUTED", "BINDING", "INFERENCE", "ASSUMPTION", "HYPOTHESIS", "UNKNOWN"}
STATES = {"PASS", "FAIL", "OPEN", "BLOCKED", "PROVISIONAL", "UNRESOLVED", "SUPERSEDED"}
SCHEMA = "federation_release_evidence.v1"
GENERATION = "seven-local-apps.v1"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"duplicate JSON key: {key}")
            obj[key] = value
        return obj
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def verify_blob(root: Path, ref: Any) -> Path:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        raise ValueError("missing artifact reference")
    relative = Path(ref["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("artifact path must remain inside bundle")
    target = (root / relative).resolve(strict=True)
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("artifact escapes bundle or is not a file")
    if not re.fullmatch(r"[0-9a-f]{64}", str(ref.get("sha256", ""))):
        raise ValueError("invalid SHA256")
    if digest(target) != ref["sha256"]:
        raise ValueError("artifact hash mismatch")
    return target


def assess(bundle: dict[str, Any], root: Path) -> dict[str, Any]:
    errors: list[str] = []
    pending: list[str] = []
    if bundle.get("schema_version") != SCHEMA:
        errors.append("unsupported schema_version")
    if bundle.get("generation") != GENERATION:
        errors.append("unexpected contract generation")
    heads = bundle.get("heads", {})
    if not isinstance(heads, dict) or set(heads) != set(REPOSITORIES):
        errors.append("head denominator must be exactly seven repositories")
        heads = heads if isinstance(heads, dict) else {}
    for repo, sha in heads.items():
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            errors.append(f"{repo}: invalid head SHA")
    counts: dict[str, dict[str, int]] = {}
    for section, dimensions in (("axes", AXES), ("platforms", PLATFORMS)):
        expected = {(repo, dimension) for repo in REPOSITORIES for dimension in dimensions}
        rows = bundle.get(section, [])
        if not isinstance(rows, list):
            errors.append(f"{section}: expected list")
            rows = []
        seen = set()
        statuses: Counter[str] = Counter()
        for row in rows:
            if not isinstance(row, dict):
                errors.append(f"{section}: invalid row")
                continue
            key = (row.get("repository"), row.get("dimension"))
            label = f"{section}:{key}"
            # Reject malformed keys before set lookup (including lists/dicts).
            if not all(isinstance(value, str) for value in key):
                errors.append(f"{section}: invalid key")
                continue
            if key not in expected or key in seen:
                errors.append(f"{label}: unexpected or duplicate cell")
            seen.add(key)
            state = row.get("state")
            if not isinstance(state, str) or state not in STATES:
                errors.append(f"{label}: invalid state")
                continue
            statuses[state] += 1
            claim_type = row.get("claim_type")
            if not isinstance(claim_type, str) or claim_type not in CLAIM_TYPES:
                errors.append(f"{label}: invalid claim type")
            if state != "PASS":
                pending.append(label)
                if not row.get("reason"):
                    errors.append(f"{label}: non-PASS cell requires reason")
                continue
            if claim_type not in {"FACT", "COMPUTED"}:
                errors.append(f"{label}: unsupported claim type for PASS")
            if row.get("residue") != []:
                errors.append(f"{label}: PASS requires explicit zero residue")
            refs = row.get("receipts")
            if not isinstance(refs, list) or not refs:
                errors.append(f"{label}: PASS requires receipts")
                continue
            for ref in refs:
                try:
                    receipt = read_json(verify_blob(root, ref))
                    if not isinstance(receipt, dict):
                        raise ValueError("receipt must be an object")
                    bindings = {
                        "repository": key[0], "dimension": key[1], "section": section,
                        "head_sha": heads.get(key[0]), "generation": GENERATION,
                        "state": "PASS", "residue": [],
                    }
                    for field, value in bindings.items():
                        if field not in receipt or receipt[field] != value:
                            raise ValueError(f"receipt {field} mismatch")
                    for field in ("command", "environment", "started_utc", "completed_utc", "scope"):
                        if not receipt.get(field):
                            raise ValueError(f"receipt missing {field}")
                    times = [datetime.fromisoformat(receipt[field].replace("Z", "+00:00"))
                             for field in ("started_utc", "completed_utc")]
                    if any(value.tzinfo is None for value in times):
                        raise ValueError("receipt timestamps require timezone")
                    if times[0] > times[1] or times[1] > datetime.now(timezone.utc):
                        raise ValueError("receipt time order is invalid or future-dated")
                    if not isinstance(receipt["environment"], dict):
                        raise ValueError("receipt environment must be an object")
                    if receipt.get("evidence_kind") != "executed":
                        raise ValueError("receipt is not execution evidence")
                    if receipt.get("exit_code") != 0 or isinstance(receipt.get("exit_code"), bool):
                        raise ValueError("receipt command did not pass")
                    for field in ("inputs", "outputs"):
                        values = receipt.get(field)
                        if not isinstance(values, list) or not values:
                            raise ValueError(f"receipt needs nonempty {field}")
                        for blob in values:
                            verify_blob(root, blob)
                    verify_blob(root, receipt.get("log"))
                    if section == "platforms":
                        journey = receipt.get("journey", {})
                        if not isinstance(journey, dict) or set(journey) != set(JOURNEY):
                            raise ValueError("incomplete platform journey")
                        if any(value != "PASS" for value in journey.values()):
                            raise ValueError("platform journey did not pass")
                        if receipt.get("environment", {}).get("platform") != key[1]:
                            raise ValueError("platform evidence environment mismatch")
                except (OSError, ValueError, TypeError, AttributeError) as exc:
                    errors.append(f"{label}: {exc}")
        for key in sorted(expected - seen):
            errors.append(f"{section}:{key}: missing cell")
        counts[section] = {"expected": len(expected), "observed": len(rows), **dict(statuses)}
    for field in ("scope_residue", "pr_disposition_residue", "source_residue"):
        if bundle.get(field) != []:
            pending.append(field)
    # Evidence validation is deliberately not an identity/source/product certificate.
    return {
        "schema_version": SCHEMA, "generation": bundle.get("generation"),
        "state": "FAIL" if errors else "BLOCKED" if pending else "PASS",
        "certification": "AUDIT_ONLY", "counts": counts,
        "errors": errors, "pending": pending,
    }


def pending_bundle(heads: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "generation": GENERATION, "heads": heads,
        **{section: [
            {"repository": repo, "dimension": dimension, "state": "OPEN",
             "claim_type": "UNKNOWN", "reason": "Execution evidence not yet supplied",
             "receipts": [], "residue": ["verification_required"]}
            for repo in REPOSITORIES for dimension in dimensions
        ] for section, dimensions in (("axes", AXES), ("platforms", PLATFORMS))},
        "scope_residue": ["full_release_verification_required"],
        "pr_disposition_residue": ["current_PR_content_adjudication_required"],
        "source_residue": ["required_source_accounting_required"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        payload = read_json(args.bundle)
        if not isinstance(payload, dict):
            raise ValueError("bundle must be an object")
        result = assess(payload, args.bundle.parent)
    except (OSError, ValueError, TypeError) as exc:
        result = {"state": "FAIL", "certification": "AUDIT_ONLY", "errors": [str(exc)]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
