"""Read-only ECPAF-V2.1 shadow evaluator; never an authorization service.

PASS evidence is checked for bytes, policy and exact authorities. This validates
receipt consistency, not the truth or independence of the evidence producer.
No output of this module grants merge, deployment, or certification authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

PHASES = ("build", "integration", "operational")
CLASSES = {"AI_AUTO", "AI_CONDITIONAL", "HUMAN_REQUIRED", "EXTERNAL_BLOCKED", "INDEPENDENT_REVIEW"}
STATES = {"PASS", "FAIL", "OPEN", "BLOCKED", "UNRESOLVED"}
DOMAINS = {"security", "integrity", "identity", "provenance", "authorization"}
CORE = {"jotaele44/" + name + "-pr" for name in (
    "aguayluz", "centinelas", "moneysweep", "ovnis", "skywatcher", "spiderweb", "thehub"
)}
ADJACENT = {"jotaele44/mucaro-ai"}


class ContractError(ValueError):
    """An incomplete or contradictory contract must not yield readiness."""


def canonical_sha(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def load_json(path):
    def reject_constant(value):
        raise ContractError("nonfinite JSON constant: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=reject_constant)


def _exact_set(value, expected, label):
    _require(isinstance(value, list) and len(value) == len(expected)
             and set(value) == expected, label + " denominator changed")


def validate_policy(policy):
    _require(policy.get("schema_version") == "ecpaf-policy/2.1", "unsupported policy schema")
    _require(policy.get("policy_id") == "ECPAF-V2.1", "wrong policy identity")
    _require(policy.get("mode") == "SHADOW_PILOT", "pilot mode required")
    _require(policy.get("authority") == "jotaele44/thehub-pr", "wrong control authority")
    _exact_set(policy.get("core_repositories"), CORE, "core membership")
    _exact_set(policy.get("adjacent_repositories"), ADJACENT, "adjacent membership")
    _exact_set(policy.get("execution_classes"), CLASSES, "execution classes")
    _exact_set(policy.get("states"), STATES, "states")
    _exact_set(policy.get("mandatory_domains"), DOMAINS, "critical domains")
    _exact_set(policy.get("protected_operations"), {
        "merge", "deploy", "release", "secret_write", "protection_change", "canonical_promotion"
    }, "protected operations")
    _require(policy.get("milestones") == dict(zip(PHASES, (80, 90, 95))), "thresholds changed")
    _require(all(type(value) is int for value in policy["milestones"].values()), "integer thresholds required")
    _require(policy.get("protected_release_behavior") == "UNCHANGED", "release behavior changed")
    _require(policy.get("certification") == "WITHHELD", "pilot cannot certify")
    semantics = policy.get("semantics", {})
    keys = {"percentages_are_mandatory_gate_waivers", "unknown_counts_as_pass", "missing_counts_as_pass",
            "self_review_is_independent_approval", "mucaro_is_core_member", "pilot_can_authorize_operations"}
    _require(set(semantics) == keys and all(v is False for v in semantics.values()), "unsafe semantics")
    limits = policy.get("limits", {})
    _require(set(limits) == {"max_epochs", "max_repair_rounds", "max_identical_no_delta_retries"}, "missing budgets")
    _require(all(type(v) is int and 0 < v <= cap for v, cap in zip(
        (limits.get("max_epochs"), limits.get("max_repair_rounds"), limits.get("max_identical_no_delta_retries")),
        (2, 3, 1))), "invalid budgets")


def validate_contract(policy, contract):
    validate_policy(policy)
    _require(contract.get("schema_version") == "ecpaf-checkpoints/2.1", "unsupported checkpoint schema")
    _require(contract.get("policy_sha256") == canonical_sha(policy), "policy binding mismatch")
    authorities = contract.get("authorities", {})
    _require(set(authorities) == CORE | ADJACENT, "exact eight-repository execution scope required")
    _require(all(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha)
                 for sha in authorities.values()), "invalid commit identity")
    leaves = contract.get("requirements", [])
    _require(isinstance(leaves, list) and leaves, "empty requirement denominator")
    ids = [leaf.get("id") for leaf in leaves]
    _require(all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids), "duplicate or empty requirement ID")
    _require(set(contract.get("declared_requirement_ids", [])) == set(ids)
             and len(contract["declared_requirement_ids"]) == len(ids), "declared denominator mismatch")
    by_id = dict(zip(ids, leaves))
    for leaf in leaves:
        _require(leaf.get("phase") in PHASES, "invalid phase")
        _require(leaf.get("execution_class") in CLASSES, "unclassified execution")
        _require(type(leaf.get("mandatory")) is bool, "mandatory must be explicit boolean")
        _require(leaf.get("domain") in DOMAINS | {"engineering", "operations", "review"}, "unknown domain")
        _require(leaf["domain"] not in DOMAINS or leaf["mandatory"], "critical gate cannot be optional")
        _require(type(leaf.get("weight")) is int and 0 < leaf["weight"] <= 100, "invalid weight")
        deps = leaf.get("depends_on")
        _require(isinstance(deps, list) and len(deps) == len(set(deps)) and set(deps) <= set(ids), "unknown or duplicate dependency")
        _require(all(PHASES.index(by_id[d]["phase"]) <= PHASES.index(leaf["phase"]) for d in deps), "dependency phase reversal")
    active, visited = set(), set()

    def visit(i):
        _require(i not in active, "cyclic dependency")
        if i in visited:
            return
        active.add(i)
        for dep in by_id[i]["depends_on"]:
            visit(dep)
        active.remove(i)
        visited.add(i)

    for i in ids:
        visit(i)
    return by_id


def _verify_evidence(evidence, policy, contract, root):
    _require(isinstance(evidence, dict), "PASS requires evidence")
    _require(evidence.get("policy_sha256") == canonical_sha(policy), "stale evidence policy")
    _require(evidence.get("authorities") == contract["authorities"], "stale evidence authorities")
    _require(evidence.get("verifier") and evidence.get("method"), "missing evidence method/verifier")
    relative = evidence.get("path")
    _require(isinstance(relative, str) and relative, "missing evidence path")
    path = Path(relative)
    _require(not path.is_absolute() and ".." not in path.parts, "evidence path escape")
    root = Path(root).resolve(strict=True)
    candidate = root / path
    for parent in (candidate, *candidate.parents):
        if parent == root:
            break
        _require(not parent.is_symlink(), "symlink evidence prohibited")
    resolved = candidate.resolve(strict=True)
    _require(root in resolved.parents and resolved.is_file(), "invalid evidence file")
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    _require(evidence.get("sha256") == digest, "evidence byte mismatch")


def evaluate(policy, contract, observations, evidence_root, expected_contract_sha256):
    _require(isinstance(expected_contract_sha256, str)
             and re.fullmatch(r"[0-9a-f]{64}", expected_contract_sha256), "frozen contract digest required")
    _require(canonical_sha(contract) == expected_contract_sha256, "frozen requirement contract changed")
    by_id = validate_contract(policy, contract)
    _require(observations.get("schema_version") == "ecpaf-observations/2.1", "unsupported observation schema")
    _require(observations.get("contract_sha256") == canonical_sha(contract), "contract changed")
    rows = observations.get("checkpoints", [])
    _require(isinstance(rows, list), "invalid observations")
    ids = [row.get("id") for row in rows]
    _require(len(ids) == len(set(ids)) and set(ids) == set(by_id), "missing, duplicate, or extra checkpoint")
    indexed = {row["id"]: row for row in rows}
    for row in rows:
        _require(row.get("state") in STATES, "invalid state; provisional is not PASS")
        if row["state"] == "PASS":
            _verify_evidence(row.get("evidence"), policy, contract, evidence_root)
            _require(all(indexed[d]["state"] == "PASS" for d in by_id[row["id"]]["depends_on"]), "PASS with unsatisfied dependency")
    counts = {state: sum(row["state"] == state for row in rows) for state in sorted(STATES)}
    _require(sum(counts.values()) == len(by_id), "checkpoint conservation failure")
    stages = {}
    for stage in PHASES:
        leaves = [leaf for leaf in by_id.values() if PHASES.index(leaf["phase"]) <= PHASES.index(stage)]
        _require(leaves, "empty milestone denominator")
        weight = sum(leaf["weight"] for leaf in leaves)
        passed = sum(leaf["weight"] for leaf in leaves if indexed[leaf["id"]]["state"] == "PASS")
        mandatory = [leaf["id"] for leaf in leaves if leaf["mandatory"]]
        _require(mandatory, "milestone requires explicit mandatory gates")
        missing = [i for i in mandatory if indexed[i]["state"] != "PASS"]
        threshold = policy["milestones"][stage]
        met = passed * 100 >= threshold * weight
        stages[stage] = {"threshold": threshold, "passed_weight": passed, "total_weight": weight,
                         "percent": round(100 * passed / weight, 2), "threshold_met": met,
                         "mandatory_total": len(mandatory), "mandatory_not_pass": missing,
                         "structurally_eligible": met and not missing,
                         "denominator_ids": [leaf["id"] for leaf in leaves]}
    return {"schema_version": "ecpaf-shadow-result/2.1", "policy_sha256": canonical_sha(policy),
            "contract_sha256": canonical_sha(contract), "observations_sha256": canonical_sha(observations),
            "authorities": contract["authorities"], "gate_count": len(by_id), "states": counts,
            "execution_classes": dict(Counter(leaf["execution_class"] for leaf in by_id.values())),
            "milestones": stages, "evidence_assurance": "STRUCTURAL_AND_BYTE_BINDING_ONLY",
            "independent_review": "OPEN", "certification": "WITHHELD", "release_authorized": False,
            "protected_operations_authorized": [], "protected_release_behavior": "UNCHANGED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--expected-contract-sha256", required=True,
                        help="Digest acquired from the separately frozen/reviewed execution baseline")
    args = parser.parse_args()
    try:
        result = evaluate(load_json(args.policy), load_json(args.contract), load_json(args.observations),
                          args.evidence_root, args.expected_contract_sha256)
    except (ContractError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(json.dumps({"state": "FAIL_CLOSED", "error": str(exc), "release_authorized": False,
                          "certification": "WITHHELD"}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
