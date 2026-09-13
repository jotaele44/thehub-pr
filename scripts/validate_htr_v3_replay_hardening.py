#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = ROOT / "data" / "htr" / "runs" / "2026-09-13_htr_v3_frozen_replay_hardening_receipt.json"


class GateFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateFailure(message)


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "receipt root must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    doc = load(args.receipt)

    require(doc["schema_version"] == "htr-v3-frozen-replay-hardening-1.0", "schema drift")

    heads = doc["historical_heads"]
    require(heads["htr_v2_head"] == "911c3433c272af66b2ef4c30267837ec22377c67", "HTR V2 head drift")
    require(heads["v3_base_head"] == "9032f5962e72d1d7465769adc50514507e16dad3", "V3 base head drift")
    require(heads["v3_recurrence_historical_head"] == "fa9146b81bbae65f85380a694961ed343680acf2", "V3 recurrence head drift")

    merge = doc["merge_governance"]
    require(merge["green_code_equals_merge_authorized"] is False, "GREEN_CODE must not imply merge authorization")
    require(merge["merge_authorized"] is False, "hardening receipt unexpectedly authorizes merge")
    require(merge["merges_performed_by_this_hardening"] == 0, "hardening performed a merge")

    frozen = doc["frozen_inputs"]
    expected_hashes = {
        "htr_islandwide_236933e": "880f34a55690748d955e78bdece19716959609d9628e7e40db52c91f84494fac",
        "tiger_roads_zip": "2e7d34b6e60bfe49aad48eb0a704282338822a39f6da553f5dab06b8730176a8",
        "v2_460_pair_evidence": "4e18deb59f82bff58d36e34b84be78117f781f028b06ad60ba1b8ec5ffadde98",
        "v3_adjudicated": "ea5b45d8c94630989344fd360f40c4dfea08a7852b34fd0842fad96612b76ecd",
        "v3_history": "22cd7093ad5742eeee064548a8d6375bc8ca2d9596b24fa985304a0dbf1f278c",
        "v3_scope_closed": "2212834ac56650c08c5eafa18b921e5266396069ece6310bdda8487b1e66ecd3",
        "historical_execution_bundle": "216ff375e8ba9e4812e41576b5d0b6a3e09b455298beeae80e1b2064aba1a032",
        "historical_executor": "34e3acdd5f1a3f7298c3185091a5115f8d3347d65275bd0d085bcb0aa188165c",
    }
    require(frozen == expected_hashes, "frozen input hash registry drift")

    roads = doc["road_denominator"]
    require(roads["sige_named_observations"] + roads["tiger_named_observations"] == roads["union_named_observations"] == 168906, "road denominator arithmetic failed")
    require(roads["tiger_municipio_packages"] == 78, "TIGER municipio denominator drift")
    require(roads["unique_road_cores"] == 24436, "road-core denominator drift")
    require(roads["observation_id_uniqueness"] == "PASS", "road observation IDs not certified unique")

    src = doc["v3_source_manifestations"]
    require(src["total"] == src["supported_for_major_discovery"] + src["unsupported_discovery_key"] + src["asset_scope_eligibility_unresolved"] == 3524, "V3 source manifestation arithmetic failed")

    keys = doc["recurrence_key_quality"]
    require(keys["source_manifestations_considered"] == keys["supported"] + keys["unsupported"] == 270, "recurrence-key arithmetic failed")
    require(keys["supported"] == 265 and keys["unsupported"] == 5, "recurrence-key state drift")

    matcher = doc["matcher_equivalence"]
    require(matcher["full_core_pair_space"] == roads["unique_road_cores"] * matcher["unique_hydro_cores"], "full pair-space arithmetic failed")
    require(matcher["naive_qualifying_core_pairs"] == matcher["indexed_qualifying_core_pairs"] == matcher["intersection"] == matcher["union"] == 171, "matcher qualifying-set mismatch")
    require(matcher["a_only"] == matcher["b_only"] == matcher["symmetric_difference"] == matcher["score_mismatches"] == 0, "matcher equivalence residue")

    inc = doc["incremental_recurrence"]
    require(inc["candidate_rows"] == inc["candidate_not_identity_rows"] + inc["unsupported_rows"] == 3733, "incremental candidate arithmetic failed")
    require(inc["pair_groups"] == inc["unresolved_groups"] + inc["unsupported_groups"] + inc["contradiction_groups"] == 880, "pair-group arithmetic failed")
    require(inc["contradiction_rows_subset"] == 93, "contradiction subset drift")
    require(inc["unexplained_residue"] == 0, "unexpected computational residue")

    pair = doc["v2_pair_binding_continuation"]
    require(pair["pair_groups_reassessed"] == 460, "V2 pair-group conservation failed")
    require(pair["source_row_relations_conserved"] == 1738, "V2 source-relation conservation failed")
    require(pair["direct_pair_binding_evidence_found"] == 0, "unexpected direct pair-binding evidence")
    require(pair["pair_binding_promotions"] == 0, "pair binding promotion detected")
    require(pair["unresolved_pair_groups"] == 460, "V2 unresolved pair denominator changed")

    pred = pair["context_predicate_adjudication"]
    require(pred["intersection"] == 409, "context intersection drift")
    require(pred["a_only"] == 0, "unexpected exact-only context groups")
    require(pred["b_only"] == 28, "fuzzy-only context delta drift")
    require(pred["union"] == 437, "context union drift")
    require(pred["symmetric_difference"] == 28, "context symmetric difference drift")
    require(pred["historical_executor_predicate_identity"] == "UNRESOLVED", "historical executor predicate must remain unresolved")
    require(pair["historical_exact_core_context_groups"] + pair["fuzzy_only_additional_groups"] + pair["no_exact_or_fuzzy_context_groups"] == 460, "context partition does not close")

    combined = doc["combined_v2_plus_v3"]
    require(combined["candidate_rows"] == combined["unsupported_rows"] + combined["candidate_not_identity_unresolved_rows"] == 9302, "combined V2+V3 arithmetic failed")
    require(combined["closed"] is True, "combined arithmetic not closed")

    inv = doc["invariants"]
    for key in (
        "raw_normalized_canonical_separate",
        "unsupported_preserved_not_false",
        "candidate_preserved_not_identity",
        "contradiction_preserved",
        "unresolved_preserved",
    ):
        require(inv[key] is True, f"required preservation invariant failed: {key}")
    for key in (
        "name_identity_promotion",
        "fuzzy_identity_promotion",
        "proximity_identity_promotion",
        "cluster_identity_promotion",
        "name_connectivity_promotion",
        "fuzzy_connectivity_promotion",
        "proximity_connectivity_promotion",
        "cluster_connectivity_promotion",
        "pair_binding_promotion",
        "transitive_context_inheritance",
    ):
        require(inv[key] == 0, f"forbidden promotion detected: {key}")

    residue = doc["open_required_residue"]
    require(residue["original_2026_09_02_executor_byte_identity"] == "OPEN", "original executor identity must remain OPEN")
    require(residue["original_2026_09_02_output_member_byte_equivalence"] == "OPEN", "original output byte equivalence must remain OPEN")
    require(residue["direct_documentary_pair_binding"] == "OPEN", "pair-binding residue must remain OPEN")
    require(residue["cross_source_canonical_identity"] == "OPEN", "canonical identity residue must remain OPEN")
    require(residue["universal_public_source_exhaustion"] == "NOT_CLAIMED", "universal public-source exhaustion must not be claimed")
    require(residue["universal_hydro_denominator"] == "NOT_CLAIMED", "universal hydro exhaustion must not be claimed")

    cert = doc["certification"]
    required_passes = (
        "frozen_input_hash_registry",
        "road_denominator_arithmetic",
        "v3_source_manifestation_arithmetic",
        "recurrence_key_arithmetic",
        "matcher_equivalence",
        "incremental_candidate_arithmetic",
        "pair_group_arithmetic",
        "v2_pair_group_conservation",
        "v2_source_relation_conservation",
        "context_predicate_set_arithmetic",
        "identity_connectivity_pair_binding_nonpromotion",
        "transitive_context_noninheritance",
        "zero_unexplained_computational_residue",
        "bounded_replay_hardening_scope",
    )
    for key in required_passes:
        require(cert[key] == "PASS", f"certification gate not PASS: {key}")
    require(cert["canonical_identity_resolution"] == "OPEN", "canonical identity improperly certified")
    require(cert["pair_binding_resolution"] == "OPEN", "pair binding improperly certified")

    print(json.dumps({"certification": "PASS", "receipt": str(args.receipt), "merge_authorized": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
