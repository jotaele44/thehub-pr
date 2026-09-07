#!/usr/bin/env python3
"""Validate the frozen HTR v3 road-recurrence receipt without source I/O."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_INPUTS = {
    "htr_islandwide_236933e": "880f34a55690748d955e78bdece19716959609d9628e7e40db52c91f84494fac",
    "tiger_roads_zip": "2e7d34b6e60bfe49aad48eb0a704282338822a39f6da553f5dab06b8730176a8",
    "v2_460_pair_evidence": "4e18deb59f82bff58d36e34b84be78117f781f028b06ad60ba1b8ec5ffadde98",
    "v3_adjudicated": "ea5b45d8c94630989344fd360f40c4dfea08a7852b34fd0842fad96612b76ecd",
    "v3_history": "22cd7093ad5742eeee064548a8d6375bc8ca2d9596b24fa985304a0dbf1f278c",
    "v3_scope_closed": "2212834ac56650c08c5eafa18b921e5266396069ece6310bdda8487b1e66ecd3",
}
EXPECTED_CERTIFICATION = {
    "bounded_scope": "PASS",
    "candidate_classification_arithmetic": "PASS",
    "cross_source_identity_resolution": "OPEN",
    "frozen_input_hashes": "PASS",
    "matcher_full_core_pair_equivalence": "PASS",
    "pair_binding_resolution": "OPEN",
    "road_denominator_arithmetic": "PASS",
    "v3_hydro_manifestation_arithmetic": "PASS",
    "zero_unexplained_computational_residue": "PASS",
}
EXPECTED_OUTPUT_HASHES = {
    "matcher_equivalence.json": "6b7d1d3209627848f0a694ef9e5dbd2923a63ca26b8a687ef4bcfdd780b7ee39",
    "summary.json": "6a89aa63db47e039befe989b753d11b881dd7136adb4202b01e6dd26cd080b68",
    "tiger_package_ledger.json": "555b0c71f629035906a7b655f894bcc167b80f11c6804aaca3a0333278fd4d03",
    "v2_460_pair_reassessment_with_v3_context.jsonl": "e1073c2b7916f94703429738f1b933f3aaa2198bacfc5e4ed2786992c0682a67",
    "v3_hydro_road_recurrence_key_quality.jsonl": "8358d527200480d2b309a11f82f53351f27cc2d47d7379aa2abd2fb2310809e4",
    "v3_incremental_candidates.jsonl": "0a05c18a02d9a34a835e709af1cc60ec1b144eaa9e24e88995dfdc0d0d4f0bd5",
    "v3_incremental_pair_groups.jsonl": "0163cc0ff6bbc9a320396be666bf9e40b31dc7610832e4db870ddfe2bd70438b",
}


class ContractError(RuntimeError):
    """Raised when the frozen recurrence receipt drifts from its contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "receipt",
        nargs="?",
        type=Path,
        default=Path("data/htr/runs/2026-09-02_htr_v3_frozen_road_recurrence_receipt.json"),
    )
    args = parser.parse_args()
    doc = json.loads(args.receipt.read_text(encoding="utf-8"))

    require(doc.get("schema_version") == "htr-v3-road-recurrence-terminal-receipt-1.0", "schema drift")
    require(doc.get("frozen_inputs") == EXPECTED_INPUTS, "frozen input hash drift")
    require(doc.get("certification") == EXPECTED_CERTIFICATION, "top-level certification drift")

    artifact = doc["execution_artifact"]
    require(
        artifact.get("bundle_sha256")
        == "216ff375e8ba9e4812e41576b5d0b6a3e09b455298beeae80e1b2064aba1a032",
        "execution bundle SHA256 drift",
    )
    require(artifact.get("bundle_size_bytes") == 608771, "execution bundle size drift")
    require(
        artifact.get("executor_sha256")
        == "34e3acdd5f1a3f7298c3185091a5115f8d3347d65275bd0d085bcb0aa188165c",
        "executor SHA256 drift",
    )
    require(artifact.get("output_hashes") == EXPECTED_OUTPUT_HASHES, "output hash ledger drift")

    roads = doc["road_denominator"]
    require(roads["sige"]["named_road_observations"] == 99060, "SIGE denominator drift")
    require(roads["tiger"]["municipio_packages"] == 78, "TIGER package denominator drift")
    require(roads["tiger"]["named_road_observations"] == 69846, "TIGER named-road drift")
    require(roads["union_named_observations"] == 99060 + 69846 == 168906, "road union arithmetic failed")
    require(roads["union_observation_id_uniqueness"] == "PASS", "road observation IDs not unique")
    require(roads["unique_road_core_count"] == 24436, "road-core denominator drift")

    hydro = doc["v3_hydro_denominator"]
    key_states = hydro["road_recurrence_key_state_counts"]
    require(hydro["source_manifestations_supported_for_major_discovery"] == 270, "V3 source denominator drift")
    require(key_states == {"SUPPORTED": 265, "UNSUPPORTED": 5}, "recurrence-key state drift")
    require(key_states["SUPPORTED"] + key_states["UNSUPPORTED"] == 270, "V3 key arithmetic failed")
    require(hydro["road_recurrence_eligible_manifestations"] == 265, "eligible hydro denominator drift")
    require(hydro["canonical_identity_certified"] is False, "canonical identity promotion detected")

    match = doc["matcher_equivalence"]
    require(match["unique_road_core_count"] == roads["unique_road_core_count"] == 24436, "matcher road-core denominator drift")
    require(match["unique_hydro_core_count"] == 212, "matcher hydro-core denominator drift")
    require(match["road_observation_count"] == roads["union_named_observations"] == 168906, "matcher road-observation denominator drift")
    require(match["eligible_hydro_manifestation_count"] == hydro["road_recurrence_eligible_manifestations"] == 265, "matcher hydro-manifestation denominator drift")
    require(
        match["full_core_pair_space"]
        == match["unique_road_core_count"] * match["unique_hydro_core_count"]
        == 5180432,
        "pair-space arithmetic failed",
    )
    require(match["naive_qualifying_core_pairs"] == match["indexed_qualifying_core_pairs"] == 171, "matcher count drift")
    require(match["intersection"] == match["union"] == 171, "matcher intersection/union drift")
    require(match["a_only"] == match["b_only"] == match["symmetric_difference"] == 0, "matcher equivalence failed")
    require(match["certification"] == "PASS", "matcher certification not PASS")

    incremental = doc["v3_incremental_recurrence"]
    states = incremental["candidate_state_counts"]
    require(incremental["candidate_rows"] == 3733, "V3 candidate denominator drift")
    require(states["CANDIDATE_NOT_IDENTITY"] + states["UNSUPPORTED"] == 3733, "V3 candidate arithmetic failed")
    require(states == {"CANDIDATE_NOT_IDENTITY": 3709, "UNSUPPORTED": 24}, "V3 candidate state drift")
    group_states = incremental["pair_group_state_counts"]
    require(sum(group_states.values()) == incremental["pair_groups"] == 880, "V3 pair-group arithmetic failed")
    require(group_states == {"CONTRADICTION": 6, "UNRESOLVED": 866, "UNSUPPORTED": 8}, "V3 pair-group state drift")
    require(incremental["contradiction_rows"] == 93, "contradiction-row denominator drift")
    require(incremental["identity_promotions"] == 0, "identity promotion detected")
    require(incremental["connectivity_promotions"] == 0, "connectivity promotion detected")
    require(incremental["pair_binding_promotions"] == 0, "pair-binding promotion detected")
    require(incremental["transitive_context_inheritance"] == 0, "transitive context detected")
    require(incremental["unexplained_residue"] == 0, "unexplained V3 residue")

    v2 = doc["v2_pair_binding_continuation"]
    require(v2["pair_groups_reassessed"] == 460, "V2 pair denominator drift")
    require(v2["groups_with_independent_v3_hydro_manifestation_context"] + v2["groups_without_new_v3_lexical_hydro_context"] == 460, "V2 context arithmetic failed")
    require(v2["source_row_relations_conserved"] == v2["unresolved_source_row_relations"] == 1738, "V2 relation conservation failed")
    require(v2["direct_pair_binding_evidence_found_groups"] == 0, "unexpected direct pair binding")
    require(v2["unresolved_pair_groups"] == 460, "V2 pair resolution drift")
    require(v2["independent_v3_context_is_pair_binding_evidence"] is False, "context promoted to pair binding")
    require(v2["bounded_public_web_exhaustion_claimed"] is False, "unbounded public-search exhaustion claim")

    targeted = doc["targeted_public_pair_binding_search"]
    require(targeted["receipt_sha256"] == "3f9a1fe8502481917326a854f42a06d19c39a416f3486770f396c808d65016b3", "targeted-search receipt hash drift")
    require(targeted["targeted_pair_families"] == 6, "targeted-search denominator drift")
    require(targeted["direct_pair_binding_found"] == 0 and targeted["unresolved"] == 6, "targeted-search disposition drift")
    require(targeted["arithmetic"] == "6=0+6", "targeted-search arithmetic drift")
    require(targeted["universal_public_search_exhaustion_claimed"] is False, "unbounded targeted-search exhaustion claim")

    combined = doc["combined_v2_plus_v3_recurrence"]
    require(combined["candidate_rows"] == 5569 + 3733 == 9302, "combined candidate arithmetic failed")
    require(combined["unsupported_rows"] == 3831 + 24 == 3855, "combined unsupported arithmetic failed")
    require(combined["candidate_not_identity_rows"] == 1738 + 3709 == 5447, "combined retained arithmetic failed")
    require(combined["candidate_rows"] == combined["unsupported_rows"] + combined["candidate_not_identity_rows"], "combined row conservation failed")
    require(combined["arithmetic_closed"] is True, "combined arithmetic not closed")

    semantics = doc["state_semantics"]
    require(semantics["unsupported_is_false_or_rejected"] is False, "UNSUPPORTED semantic drift")
    require(semantics["contradiction_is_disjoint_arithmetic_bucket"] is False, "contradiction arithmetic semantic drift")
    require(semantics["candidate_not_identity_may_remain_unresolved"] is True, "unresolved-state semantic drift")

    invariants = doc["invariants"]
    required_true = [
        "raw_normalized_canonical_separate",
        "unsupported_source_rows_preserved",
        "name_identity_prohibited",
        "fuzzy_identity_prohibited",
        "proximity_identity_prohibited",
        "cluster_identity_prohibited",
        "discovery_connectivity_prohibited",
    ]
    for key in required_true:
        require(invariants.get(key) is True, f"invariant drift: {key}")
    require(invariants["transitive_context_inheritance"] is False, "transitive-context invariant drift")
    require(invariants["green_code_equals_merge_authorized"] is False, "merge-authorization semantic drift")
    require(invariants["universal_hydro_exhaustion_claimed"] is False, "universal-exhaustion semantic drift")

    heads = doc["exact_heads"]
    require(heads["v3_base_head"] == "9032f5962e72d1d7465769adc50514507e16dad3", "V3 base-head drift")
    require(heads["htr_v2_head"] == "911c3433c272af66b2ef4c30267837ec22377c67", "HTR V2 head drift")
    require(heads["merge_authorized"] is False and heads["merges_performed"] == 0, "unauthorized merge state")

    print(json.dumps({"certification": "PASS", "receipt": str(args.receipt)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
