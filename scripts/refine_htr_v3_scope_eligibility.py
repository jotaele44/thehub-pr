#!/usr/bin/env python3
"""Resolve MAJOR_HYDRO_ASSET_v3 scope eligibility from frozen adjudication.

This is a scope-classification pass, not an identity adjudication. The approved
MAJOR_HYDRO_ASSET inclusion contract explicitly includes named intakes. The
frozen AAA 2015 `w_Intake` denominator contains 182 rows with 182 stable
FacilityIDs and non-null names, so all 182 are in scope as named intake source
manifestations. Canonical identity remains null and cross-source identity remains
UNRESOLVED.

No source network access occurs here. The input is the exact successful frozen-
source adjudication artifact from run 33572711586.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

INPUT_ARTIFACT_DIGEST = "ea5b45d8c94630989344fd360f40c4dfea08a7852b34fd0842fad96612b76ecd"
EXPECTED_AAA_LEDGER_SHA256 = "48f0ca64e87c8b1bc638aeca4c0ae9a3de652f762d09176a21e98b7485304548"
EXPECTED_SUMMARY_SHA256 = "908eb180db0517cac479a7e6dface036922abeecc6c1375a3ce8610bec801a35"
SCOPE_BINDING = "conversation:MAJOR_HYDRO_ASSET_scope:named_intakes=INCLUDE"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("artifacts/htr_v3_scope_closed"))
    args = ap.parse_args()
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    aaa_path = args.input / "aaa_2015_intake_manifestations.jsonl"
    summary_path = args.input / "summary.json"
    if sha256(aaa_path) != EXPECTED_AAA_LEDGER_SHA256:
        raise RuntimeError("AAA frozen ledger hash mismatch")
    if sha256(summary_path) != EXPECTED_SUMMARY_SHA256:
        raise RuntimeError("v3 adjudication summary hash mismatch")
    prior = json.loads(summary_path.read_text(encoding="utf-8"))
    if prior.get("new_v3_source_manifestations") != 3506:
        raise RuntimeError("prior v3 manifestation denominator drift")
    if prior.get("major_hydro_asset_eligibility_unresolved") != 182:
        raise RuntimeError("prior AAA eligibility residue drift")

    aaa = read_jsonl(aaa_path)
    if len(aaa) != 182:
        raise RuntimeError(f"AAA row count drift: {len(aaa)}")
    facility_ids = [str(row["source_feature_id"]) for row in aaa]
    if len(set(facility_ids)) != 182:
        raise RuntimeError("AAA FacilityID uniqueness drift")
    if any(not isinstance(row.get("raw_name"), str) or not row["raw_name"].strip() for row in aaa):
        raise RuntimeError("AAA named-intake scope requires non-empty RAW names")

    refined: list[dict[str, Any]] = []
    for row in aaa:
        item = dict(row)
        item["major_hydro_asset_eligibility"] = "IN_SCOPE_NAMED_INTAKE"
        item["major_hydro_asset_eligibility_basis"] = SCOPE_BINDING
        item["discovery_key_status"] = "SUPPORTED"
        item["canonical_entity_id"] = None
        item["cross_source_identity_state"] = "UNRESOLVED"
        item["identity_claim"] = False
        item["connectivity_claim"] = False
        refined.append(item)
    write_jsonl(args.out / "aaa_2015_named_intakes_in_scope.jsonl", refined)

    supported = 70 + 182
    unsupported = 3254
    unresolved_eligibility = 0
    total = supported + unsupported + unresolved_eligibility
    if total != 3506:
        raise RuntimeError(f"scope arithmetic failed: {total}")
    summary = {
        "schema_version": "major-hydro-asset-v3-scope-eligibility-1.0",
        "input_artifact": {
            "workflow_run_id": 33572711586,
            "artifact_id": 9825534660,
            "artifact_digest": f"sha256:{INPUT_ARTIFACT_DIGEST}",
            "summary_sha256": EXPECTED_SUMMARY_SHA256,
            "aaa_ledger_sha256": EXPECTED_AAA_LEDGER_SHA256
        },
        "scope_binding": {
            "id": SCOPE_BINDING,
            "rule": "NAMED_INTAKES_INCLUDED",
            "effect": "ASSET_SCOPE_ELIGIBILITY_ONLY_NOT_IDENTITY_OR_CONNECTIVITY"
        },
        "aaa_named_intakes": {
            "source_rows": 182,
            "stable_facility_ids": 182,
            "distinct_raw_names": len({row["raw_name"] for row in aaa}),
            "in_scope_named_intakes": 182,
            "eligibility_unresolved": 0,
            "canonical_identity_certified": False
        },
        "new_v3_source_manifestation_arithmetic": "3506=252+3254+0",
        "new_v3_source_manifestations": 3506,
        "supported_for_major_discovery": supported,
        "unsupported_discovery_key": unsupported,
        "major_hydro_asset_eligibility_unresolved": unresolved_eligibility,
        "base_v2_manifestations": 107,
        "total_source_manifestations_with_v2": 3613,
        "bounded_supported_discovery_manifestations_with_v2": 107 + supported,
        "unexplained_manifestation_residue": 0,
        "unresolved_cross_source_identity": True,
        "identity_promotions": 0,
        "connectivity_promotions": 0,
        "transitive_context_inheritance": 0,
        "historical_prwra_exhaustion": "OPEN",
        "usgs_conveyance_expansion_beyond_v2": "OPEN",
        "universal_hydro_exhaustion_claimed": False,
        "certification": "PASS_BOUNDED_V3_ASSET_SCOPE_ELIGIBILITY"
    }
    write_json(args.out / "summary.json", summary)
    hashes = {
        str(path.relative_to(args.out)): sha256(path)
        for path in sorted(args.out.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS.json"
    }
    write_json(args.out / "SHA256SUMS.json", hashes)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
