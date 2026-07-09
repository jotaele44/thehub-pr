#!/usr/bin/env python3
"""Validate TheHub's external MCP candidate scoring matrix."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_PATH = REPO_ROOT / "mcp" / "registry" / "external_mcp_candidates.csv"

REQUIRED_COLUMNS = [
    "candidate_id",
    "name",
    "category",
    "primary_use",
    "authority_score",
    "coverage_score",
    "puerto_rico_fit",
    "auth_requirements",
    "cost",
    "write_risk",
    "provenance_support",
    "adoption_status",
    "notes",
]

SCORE_COLUMNS = ["authority_score", "coverage_score", "puerto_rico_fit"]

VALID_ADOPTION_STATUS = {"pilot", "conditional", "hold", "reject", "active"}
VALID_WRITE_RISK = {"low", "medium", "high"}
VALID_AUTH_REQUIREMENTS = {
    "none",
    "none_or_low",
    "none_or_api_key",
    "api_key_possible",
    "api_key_likely",
    "secret_required",
}
VALID_COST = {"free", "free_or_low", "free_or_paid", "paid"}
VALID_PROVENANCE_SUPPORT = {"low", "medium", "high"}

FORBIDDEN_PHRASES = [
    "confirmed anomaly",
    "confirmed uap",
    "confirmed uso",
]

# Looks for an actual assigned credential value, not the bare vocabulary
# words (e.g. "secret_required" is a legitimate auth_requirements value).
SECRET_PATTERNS = [
    re.compile(r"api[_-]?key\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"token\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"password\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"secret\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
]


def scan_row_text(row: dict, row_num: int) -> list[str]:
    errors: list[str] = []
    joined = " ".join(str(v) for v in row.values() if v is not None)
    lowered = joined.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            errors.append(f"row {row_num}: forbidden phrase found: {phrase!r}")
    for pattern in SECRET_PATTERNS:
        if pattern.search(joined):
            errors.append(f"row {row_num}: possible secret string found")
    return errors


def validate() -> list[str]:
    errors: list[str] = []

    if not CANDIDATES_PATH.is_file():
        return [f"candidates file not found: {CANDIDATES_PATH}"]

    with CANDIDATES_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing_columns = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
        if missing_columns:
            return [f"missing required column(s): {missing_columns}"]

        seen_ids: set[str] = set()
        row_count = 0
        for row_num, row in enumerate(reader, start=2):
            row_count += 1

            for column in REQUIRED_COLUMNS:
                value = (row.get(column) or "").strip()
                if not value:
                    errors.append(f"row {row_num}: empty required field {column!r}")

            candidate_id = (row.get("candidate_id") or "").strip()
            if candidate_id:
                if candidate_id in seen_ids:
                    errors.append(
                        f"row {row_num}: duplicate candidate_id {candidate_id!r}"
                    )
                seen_ids.add(candidate_id)

            for column in SCORE_COLUMNS:
                raw = (row.get(column) or "").strip()
                try:
                    score = float(raw)
                except ValueError:
                    errors.append(
                        f"row {row_num}: {column} is not numeric: {raw!r}"
                    )
                    continue
                if not (0.0 <= score <= 1.0):
                    errors.append(
                        f"row {row_num}: {column} out of range [0,1]: {score}"
                    )

            adoption_status = (row.get("adoption_status") or "").strip()
            if adoption_status and adoption_status not in VALID_ADOPTION_STATUS:
                errors.append(
                    f"row {row_num}: invalid adoption_status {adoption_status!r}"
                )

            write_risk = (row.get("write_risk") or "").strip()
            if write_risk and write_risk not in VALID_WRITE_RISK:
                errors.append(f"row {row_num}: invalid write_risk {write_risk!r}")

            auth_requirements = (row.get("auth_requirements") or "").strip()
            if (
                auth_requirements
                and auth_requirements not in VALID_AUTH_REQUIREMENTS
            ):
                errors.append(
                    f"row {row_num}: invalid auth_requirements "
                    f"{auth_requirements!r}"
                )

            cost = (row.get("cost") or "").strip()
            if cost and cost not in VALID_COST:
                errors.append(f"row {row_num}: invalid cost {cost!r}")

            provenance_support = (row.get("provenance_support") or "").strip()
            if (
                provenance_support
                and provenance_support not in VALID_PROVENANCE_SUPPORT
            ):
                errors.append(
                    f"row {row_num}: invalid provenance_support "
                    f"{provenance_support!r}"
                )

            errors.extend(scan_row_text(row, row_num))

    if not errors:
        print(f"Validated {row_count} external MCP candidate(s).")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
