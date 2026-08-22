#!/usr/bin/env python3
"""Generate non-merging concordance and conflict reports from a raw term ledger."""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

try:
    from common import normalize_label, sha256_text
except ImportError:  # pragma: no cover
    from tools.ontology.common import normalize_label, sha256_text

ANALYZER_VERSION = "1.0.0"
PRIORITY_ALIASES = {
    "source": {"source", "source_record", "monitored_source", "source_reference", "source_id", "source_ref"},
    "observation": {"observation", "raw_observation", "canonical_observation", "airspace_observation"},
    "relationship": {"relationship", "correlation", "edge", "connection", "relationship_id"},
    "evidence": {"evidence", "evidence_item", "validation_evidence", "attestation", "gate_evidence"},
    "alert": {"alert", "alert_event", "canonical_alert_record", "governance_alerts", "alert_id"},
    "confidence": {"confidence", "confidence_score", "certainty", "confidence_assessment"},
    "status": {"status", "state", "stage", "phase", "lifecycle_state", "review_status"},
    "public_matter": {"public_matter", "matter", "matter_id"},
}
GENERIC_TERMS = {"id", "name", "type", "value", "data", "items", "result", "results", "description", "title"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"{path}:{line_no}: record must be an object")
            records.append(item)
    return records


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def semantic_signature(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        record.get("term_kind"), record.get("artifact_kind"), record.get("owner"),
        record.get("data_type"), record.get("cardinality"), record.get("scale"),
        tuple(record.get("lifecycle_values") or ()), record.get("authority_surface"),
    )


def priority_family(normalized: str) -> str | None:
    tokens = set(normalized.split("_"))
    for family, aliases in PRIORITY_ALIASES.items():
        for alias in aliases:
            if normalized == alias or normalized.endswith("_" + alias) or alias in tokens:
                return family
    return None


def summarize_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "observation_id": r.get("observation_id"), "repository": r.get("repository"),
            "path": r.get("path"), "line": r.get("line"), "term": r.get("term"),
            "term_kind": r.get("term_kind"), "artifact_kind": r.get("artifact_kind"),
            "owner": r.get("owner"), "data_type": r.get("data_type"),
            "cardinality": r.get("cardinality"), "scale": r.get("scale"),
            "lifecycle_values": r.get("lifecycle_values") or [],
        }
        for r in records
    ]


def build_synonym_candidates(by_label: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    labels = sorted(label for label in by_label if len(label) >= 4 and label not in GENERIC_TERMS)
    buckets: dict[str, list[str]] = defaultdict(list)
    for label in labels:
        tokens = [token for token in label.split("_") if len(token) >= 3]
        keys = set(tokens[:2])
        if label.endswith("s"):
            keys.add(label[:-1])
        else:
            keys.add(label + "s")
        for key in keys:
            buckets[key].append(label)
    seen: set[tuple[str, str]] = set()
    candidates: list[dict[str, Any]] = []
    for bucket_labels in buckets.values():
        if len(bucket_labels) > 200:
            bucket_labels = bucket_labels[:200]
        for left, right in combinations(sorted(set(bucket_labels)), 2):
            pair = (left, right)
            if pair in seen:
                continue
            seen.add(pair)
            left_tokens, right_tokens = set(left.split("_")), set(right.split("_"))
            union = left_tokens | right_tokens
            jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
            sequence = difflib.SequenceMatcher(a=left, b=right).ratio()
            singular_match = left.rstrip("s") == right.rstrip("s")
            if not (singular_match or jaccard >= 0.66 or sequence >= 0.88):
                continue
            owners_left = sorted({str(r.get("owner")) for r in by_label[left]})
            owners_right = sorted({str(r.get("owner")) for r in by_label[right]})
            candidates.append({
                "left": left, "right": right,
                "similarity": {"token_jaccard": round(jaccard, 4), "sequence": round(sequence, 4), "singular_match": singular_match},
                "owners": {"left": owners_left, "right": owners_right},
                "classification": "candidate_only_no_merge",
            })
    return sorted(candidates, key=lambda c: (-max(c["similarity"]["token_jaccard"], c["similarity"]["sequence"]), c["left"], c["right"]))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--coverage", type=Path)
    parser.add_argument("--resolutions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    records = load_jsonl(args.ledger)
    args.out.mkdir(parents=True, exist_ok=True)
    dedup: dict[str, dict[str, Any]] = {}
    duplicate_ids: list[str] = []
    for record in records:
        observation_id = str(record.get("observation_id"))
        if observation_id in dedup and dedup[observation_id] != record:
            duplicate_ids.append(observation_id)
        dedup[observation_id] = record
    deduplicated = sorted(dedup.values(), key=lambda r: (r.get("program_id", ""), r.get("path", ""), r.get("line", 0), r.get("observation_id", "")))
    with (args.out / "deduplicated-observations.jsonl").open("w", encoding="utf-8") as handle:
        for record in deduplicated:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in deduplicated:
        label = str(record.get("normalized_label") or normalize_label(str(record.get("term", ""))))
        if label:
            by_label[label].append(record)

    homonyms: list[dict[str, Any]] = []
    scale_conflicts: list[dict[str, Any]] = []
    identity_conflicts: list[dict[str, Any]] = []
    cardinality_conflicts: list[dict[str, Any]] = []
    lifecycle_conflicts: list[dict[str, Any]] = []
    authority_conflicts: list[dict[str, Any]] = []

    for label, group in sorted(by_label.items()):
        signatures = {semantic_signature(record) for record in group}
        owners = sorted({str(record.get("owner")) for record in group})
        scales = sorted({str(record.get("scale")) for record in group if record.get("scale")})
        cardinalities = sorted({str(record.get("cardinality")) for record in group if record.get("cardinality")})
        lifecycle_sets = sorted({tuple(record.get("lifecycle_values") or ()) for record in group if record.get("lifecycle_values")})
        data_types = sorted({str(record.get("data_type")) for record in group if record.get("data_type")})
        family = priority_family(label)
        severity = "high" if family else "medium"
        if len(signatures) > 1 and len(group) > 1 and label not in GENERIC_TERMS:
            homonyms.append({
                "normalized_label": label, "priority_family": family, "severity": severity,
                "semantic_signature_count": len(signatures), "observations": summarize_records(group),
                "disposition": "review_required_no_automatic_merge",
            })
        if len(scales) > 1:
            scale_conflicts.append({"normalized_label": label, "priority_family": family, "severity": "high", "scales": scales, "observations": summarize_records(group)})
        if len(cardinalities) > 1:
            cardinality_conflicts.append({"normalized_label": label, "priority_family": family, "severity": severity, "cardinalities": cardinalities, "observations": summarize_records(group)})
        if len(lifecycle_sets) > 1:
            lifecycle_conflicts.append({"normalized_label": label, "priority_family": family, "severity": "high" if family in {"status", "public_matter", "alert"} else severity, "lifecycle_value_sets": [list(v) for v in lifecycle_sets], "observations": summarize_records(group)})
        if len(owners) > 1 and label not in GENERIC_TERMS:
            authority_conflicts.append({"normalized_label": label, "priority_family": family, "severity": severity, "owners": owners, "observations": summarize_records(group)})
        if label.endswith("_id") and (len(data_types) > 1 or len(owners) > 1):
            identity_conflicts.append({"normalized_label": label, "priority_family": family, "severity": "high" if family else severity, "data_types": data_types, "owners": owners, "observations": summarize_records(group)})

    scale_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for label, group in by_label.items():
        family = priority_family(label)
        if family == "confidence" or any(token in label for token in ("confidence", "certainty")):
            scale_family[family or "confidence"].extend(group)
    for family, group in scale_family.items():
        scales = sorted({str(r.get("scale")) for r in group if r.get("scale")})
        if len(scales) > 1:
            scale_conflicts.append({
                "normalized_label": f"family:{family}", "priority_family": family,
                "severity": "high", "scales": scales, "observations": summarize_records(group),
            })

    resolutions_doc = yaml.safe_load(args.resolutions.read_text(encoding="utf-8")) or {}
    resolution_families = resolutions_doc.get("families", {}) if isinstance(resolutions_doc, Mapping) else {}
    priority_status: dict[str, Any] = {}
    unresolved_high = 0
    for family, aliases in PRIORITY_ALIASES.items():
        matched = [record for label, group in by_label.items() if label in aliases or priority_family(label) == family for record in group]
        resolution = resolution_families.get(family, {}) if isinstance(resolution_families, Mapping) else {}
        owner = resolution.get("owner") if isinstance(resolution, Mapping) else None
        disposition = resolution.get("disposition") if isinstance(resolution, Mapping) else None
        severity = resolution.get("severity", "high") if isinstance(resolution, Mapping) else "high"
        owned = bool(owner and disposition)
        if severity == "high" and not owned:
            unresolved_high += 1
        priority_status[family] = {
            "observations": len(matched),
            "repositories": sorted({str(r.get("program_id")) for r in matched}),
            "owner": owner,
            "co_owners": resolution.get("co_owners", []) if isinstance(resolution, Mapping) else [],
            "disposition": disposition,
            "severity": severity,
            "high_severity_has_owner_and_disposition": owned,
        }

    coverage_doc: dict[str, Any] = {}
    if args.coverage and args.coverage.exists():
        coverage_doc = json.loads(args.coverage.read_text(encoding="utf-8"))
    coverage_gate = bool(coverage_doc.get("all_repositories_100_percent")) if coverage_doc else False
    pr_gate = coverage_gate and unresolved_high == 0 and not duplicate_ids

    reports = {
        "synonym-candidates.json": build_synonym_candidates(by_label),
        "homonym-conflicts.json": homonyms,
        "scale-conflicts.json": scale_conflicts,
        "identity-conflicts.json": identity_conflicts,
        "cardinality-conflicts.json": cardinality_conflicts,
        "lifecycle-conflicts.json": lifecycle_conflicts,
        "authority-conflicts.json": authority_conflicts,
        "priority-resolution-status.json": priority_status,
    }
    for name, value in reports.items():
        write_json(args.out / name, value)

    summary = {
        "schema_version": "1.0.0",
        "analyzer_version": ANALYZER_VERSION,
        "ledger_sha256": sha256_text(args.ledger.read_text(encoding="utf-8")),
        "input_records": len(records),
        "deduplicated_records": len(deduplicated),
        "duplicate_observation_ids": sorted(set(duplicate_ids)),
        "unique_normalized_labels": len(by_label),
        "report_counts": {name: len(value) if isinstance(value, list) else len(value) for name, value in reports.items()},
        "coverage_gate": coverage_gate,
        "unowned_high_severity_priority_families": unresolved_high,
        "coordinated_pr_gate": pr_gate,
        "gate_rule": "100% eligible-file coverage in all seven repositories, no duplicate observation IDs, and every high-severity priority family has an owner and disposition",
    }
    write_json(args.out / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if pr_gate else 3


if __name__ == "__main__":
    sys.exit(main())
