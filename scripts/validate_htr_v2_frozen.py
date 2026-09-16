#!/usr/bin/env python3
"""Validate committed HTR v2 frozen denominator and receipt invariants."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIGER = ROOT / "data" / "htr" / "tiger2025_road_denominator_v1.json"
HYDRO = ROOT / "data" / "htr" / "major_hydro_asset_v2.json"
RECEIPT = ROOT / "data" / "htr" / "runs" / "2026-08-31_htr_v2_rederived_receipt.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    tiger = load(TIGER)
    hydro = load(HYDRO)
    receipt = load(RECEIPT)

    assert tiger["counts"]["municipio_packages"] == 78
    assert len(tiger["municipio_geoids"]) == 78
    assert len(set(tiger["municipio_geoids"])) == 78
    assert tiger["counts"]["source_road_rows"] == 183827
    assert tiger["counts"]["named_road_rows"] == 69846
    assert tiger["stable_observation_key"] == "municipio_geoid + LINEARID"
    assert tiger["package_ledger_sha256"] == "efd75b441b86da5071d24eecae813632e925f2dd47551182bfc0981a0c44e453"

    assert hydro["extension_manifestation_count"] == len(hydro["manifestations"]) == 38
    assert hydro["combined_discovery_manifestation_count"] == 107
    assert hydro["drna_status_counts"] == {
        "ACTIVE_INTERMEDIATE": 4,
        "ACTIVE_MAJOR": 15,
        "PLANNING_2004": 6,
        "SEDIMENTED": 7,
        "UNDER_CONSTRUCTION_2004": 2,
    }
    assert all(row["canonical_entity_id"] is None for row in hydro["manifestations"])
    assert all(row["cross_source_identity_state"] == "UNRESOLVED" for row in hydro["manifestations"])

    adjudication = receipt["candidate_adjudication"]
    assert adjudication["candidate_rows"] == 5569
    assert adjudication["unsupported_rows"] == 3831
    assert adjudication["retained_candidate_rows"] == 1738
    assert adjudication["unclassified_rows"] == 0
    assert adjudication["unexplained_residue_rows"] == 0
    assert adjudication["candidate_rows"] == (
        adjudication["unsupported_rows"] + adjudication["retained_candidate_rows"]
    )
    assert receipt["safety_invariants"] == {
        "connectivity_promotions": 0,
        "identity_promotions": 0,
        "name_fuzzy_proximity_cluster_may_promote_connectivity": False,
        "name_fuzzy_proximity_cluster_may_promote_identity": False,
        "pair_binding_promotions": 0,
        "transitive_context_inheritance": 0,
    }
    assert receipt["matcher_equivalence"]["symmetric_difference"] == 0
    assert receipt["legacy_1513_disposition"] == "SUPERSEDED_NONREPRODUCIBLE"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
