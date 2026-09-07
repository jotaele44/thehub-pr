#!/usr/bin/env python3
"""Apply fail-closed negative controls to a completed HTR discovery census.

This stage never deletes discovery rows.  It preserves the original candidate
bundle and emits a parallel adjudicated ledger.  The first frozen negative
control handles SIGE Represas ``OTHER_NAME`` values that are a single
alphanumeric character (for example A/C/D/R/Y).  Those values are preserved as
source manifestations, but they are too ambiguous/code-like to act as hydro
name keys without independent evidence that the character is an actual name.

Everything not rejected remains unresolved.  This script does not promote any
candidate to identity, connectivity, eponymy, or contextual support.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

REJECTION_CODE = "AMBIGUOUS_SINGLE_CHARACTER_OTHER_NAME"
SCHEMA_VERSION = "htr-candidate-adjudication-1.0"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_ambiguous_code_manifestation(row: dict[str, Any]) -> bool:
    if row.get("name_manifestation_role") != "OTHER":
        return False
    raw = row.get("raw_name")
    if not isinstance(raw, str):
        return False
    value = raw.strip()
    return len(value) == 1 and value.isalnum()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_dir", type=Path)
    args = parser.parse_args()
    root = args.artifact_dir

    candidates_path = root / "bundle" / "candidates.jsonl"
    registry_path = root / "expanded_hydro_registry.jsonl"
    if not candidates_path.is_file() or not registry_path.is_file():
        raise SystemExit("required census artifacts are missing")

    candidates = read_jsonl(candidates_path)
    registry = read_jsonl(registry_path)
    rejected_hydro_ids = {
        str(row["hydro_entity_id"]): row
        for row in registry
        if is_ambiguous_code_manifestation(row)
    }

    adjudicated: list[dict[str, Any]] = []
    rejection_ledger: list[dict[str, Any]] = []
    unresolved_ledger: list[dict[str, Any]] = []

    for original in candidates:
        row = json.loads(json.dumps(original))
        hydro_id = str(row.get("hydro_entity_id", ""))
        if hydro_id in rejected_hydro_ids:
            row["pre_adjudication_state"] = row.get("state")
            row["state"] = "REJECTED"
            row["identity_state"] = "DISTINCT_ENTITIES"
            row["pair_binding_state"] = "UNBOUND"
            reasons = list(row.get("rejected_reasons") or [])
            reasons.append(REJECTION_CODE)
            row["rejected_reasons"] = sorted(set(reasons))
            rejection_ledger.append(
                {
                    "candidate_id": row["candidate_id"],
                    "source_observation_id": row.get("source_observation_id"),
                    "source_raw_name": (row.get("source_name") or {}).get("raw"),
                    "hydro_entity_id": hydro_id,
                    "hydro_raw_name": (row.get("hydro_name") or {}).get("raw"),
                    "rejection_code": REJECTION_CODE,
                    "source_manifestation_preserved": True,
                    "identity_claim": False,
                    "connectivity_claim": False,
                }
            )
        else:
            # Explicitly preserve unresolved status; this stage is negative-only.
            if row.get("state") != "CANDIDATE_NOT_IDENTITY":
                raise SystemExit(
                    f"unexpected promoted discovery state before adjudication: {row.get('candidate_id')}={row.get('state')}"
                )
            unresolved_ledger.append(
                {
                    "candidate_id": row["candidate_id"],
                    "source_observation_id": row.get("source_observation_id"),
                    "source_raw_name": (row.get("source_name") or {}).get("raw"),
                    "hydro_entity_id": hydro_id,
                    "hydro_raw_name": (row.get("hydro_name") or {}).get("raw"),
                    "state": "UNRESOLVED",
                    "identity_claim": False,
                    "connectivity_claim": False,
                }
            )
        adjudicated.append(row)

    if len(adjudicated) != len(candidates):
        raise SystemExit("candidate row conservation failed")
    candidate_ids = [str(row.get("candidate_id")) for row in adjudicated]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise SystemExit("duplicate candidate_id after adjudication")
    if len(rejection_ledger) + len(unresolved_ledger) != len(adjudicated):
        raise SystemExit("adjudication arithmetic did not close")

    unsafe = [
        row for row in adjudicated
        if row.get("identity_state") not in {"UNRESOLVED", "DISTINCT_ENTITIES"}
        or row.get("pair_binding_state") != "UNBOUND"
        or row.get("state") not in {"CANDIDATE_NOT_IDENTITY", "REJECTED"}
    ]
    if unsafe:
        raise SystemExit(f"unsafe candidate promotion detected: {len(unsafe)}")

    rejected_manifestations = [
        {
            "hydro_entity_id": hydro_id,
            "raw_name": row.get("raw_name"),
            "name_manifestation_role": row.get("name_manifestation_role"),
            "canonical_entity_id": row.get("canonical_entity_id"),
            "source_feature_id": row.get("source_feature_id"),
            "source_id": row.get("source_id"),
            "rejection_code": REJECTION_CODE,
            "source_manifestation_preserved": True,
            "discovery_key_eligible": False,
        }
        for hydro_id, row in sorted(rejected_hydro_ids.items())
    ]

    adjudicated_path = root / "adjudicated_candidates.jsonl"
    rejection_path = root / "rejection_ledger.jsonl"
    unresolved_path = root / "unresolved_ledger.jsonl"
    rejected_manifestations_path = root / "rejected_hydro_name_manifestations.jsonl"
    write_jsonl(adjudicated_path, adjudicated)
    write_jsonl(rejection_path, rejection_ledger)
    write_jsonl(unresolved_path, unresolved_ledger)
    write_jsonl(rejected_manifestations_path, rejected_manifestations)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "input_candidate_count": len(candidates),
        "output_candidate_count": len(adjudicated),
        "rejected_candidate_count": len(rejection_ledger),
        "unresolved_candidate_count": len(unresolved_ledger),
        "rejected_source_manifestation_count": len(rejected_manifestations),
        "rejection_codes": {REJECTION_CODE: len(rejection_ledger)},
        "identity_promotions": 0,
        "connectivity_promotions": 0,
        "context_promotions": 0,
        "transitive_context_inheritance": 0,
        "gates": {
            "candidate_row_conservation": "PASS",
            "candidate_id_uniqueness": "PASS",
            "adjudication_arithmetic": "PASS",
            "identity_nonpromotion": "PASS",
            "connectivity_nonpromotion": "PASS",
            "source_manifestation_retention": "PASS",
        },
        "certification": {
            "negative_control_scope": "PASS",
            "all_remaining_candidate_relations": "UNRESOLVED",
            "zero_unresolved_candidate_residue": len(unresolved_ledger) == 0,
        },
    }
    summary_path = root / "candidate_adjudication_summary.json"
    write_json(summary_path, summary)

    hashes = {
        str(path.relative_to(root)): {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in (
            adjudicated_path,
            rejection_path,
            unresolved_path,
            rejected_manifestations_path,
            summary_path,
        )
    }
    write_json(root / "ADJUDICATION_SHA256SUMS.json", hashes)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
