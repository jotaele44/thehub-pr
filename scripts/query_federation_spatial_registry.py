#!/usr/bin/env python3
"""Read-only query adapter for federation spatial identity and evidence state.

TheHub orchestrates discovery and provenance. It does not transform geometry,
resolve identity, promote source evidence, or mutate Spiderweb-owned artifacts.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "federation-spatial-contract/1.1"
BRIDGE_CONTRACT_VERSION = "federation-spatial-archipelago-evidence-bridge/1.1"
COLLECTION_FIELDS = (
    "source_manifestations",
    "geometry_manifestations",
    "canonical_entities",
    "identity_bindings",
    "unresolved",
)


def validate_registry_shape(data: Any) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError("spatial registry root must be an object")
    if data.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("unsupported spatial registry contract")
    for field in COLLECTION_FIELDS:
        rows = data.get(field)
        if not isinstance(rows, list):
            raise ValueError(f"spatial registry {field} must be an array")
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise ValueError(f"spatial registry {field}[{index}] must be an object")
    return dict(data)


def validate_bridge_shape(data: Any) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError("spatial evidence bridge root must be an object")
    if data.get("contract_version") != BRIDGE_CONTRACT_VERSION:
        raise ValueError("unsupported spatial evidence bridge contract")
    required = (
        "durable_freeze",
        "frozen_manifestations",
        "source_manifestation_denominator",
        "current_geometry_audit",
        "canonical_gates",
        "v1_1_ingestion_state",
    )
    for field in required:
        if not isinstance(data.get(field), Mapping):
            raise ValueError(f"spatial evidence bridge {field} must be an object")
    return dict(data)


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return validate_registry_shape(data)


def load_bridge(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return validate_bridge_shape(data)


def summary(data: dict[str, Any]) -> dict[str, Any]:
    data = validate_registry_shape(data)
    return {
        "contract_version": data["contract_version"],
        "source_manifestations": len(data.get("source_manifestations", [])),
        "geometry_manifestations": len(data.get("geometry_manifestations", [])),
        "canonical_entities": len(data.get("canonical_entities", [])),
        "identity_bindings": len(data.get("identity_bindings", [])),
        "unresolved": len(data.get("unresolved", [])),
    }


def bridge_summary(data: dict[str, Any]) -> dict[str, Any]:
    data = validate_bridge_shape(data)
    denominator = data["source_manifestation_denominator"]
    gates = data["canonical_gates"]
    durable = data["durable_freeze"]
    return {
        "contract_version": data["contract_version"],
        "source_evidence_preservation": durable.get("source_evidence_preservation"),
        "durable_release_tag": durable.get("tag"),
        "source_manifestations": denominator.get("source_manifestations"),
        "retained": denominator.get("retained"),
        "excluded": denominator.get("excluded"),
        "candidate": denominator.get("candidate"),
        "unresolved_source_partition": denominator.get("unresolved"),
        "source_arithmetic_closed": denominator.get("arithmetic_closed"),
        "canonical_identity_denominator_closed": gates.get("canonical_identity_denominator_closed"),
        "canonical_geometry_denominator_closed": gates.get("canonical_geometry_denominator_closed"),
        "known_unresolved_sige_identity_bindings": gates.get("known_unresolved_sige_identity_bindings"),
        "runtime_activation": gates.get("runtime_activation"),
        "current_pr_archipelago": gates.get("CURRENT_PR_ARCHIPELAGO"),
        "geometric_current": gates.get("GEOMETRIC_CURRENT"),
        "strict_v1_1_ingestion": data["v1_1_ingestion_state"].get("strict_source_manifestation_rows"),
    }


def query_scope(data: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    data = validate_registry_shape(data)
    return [row for row in data.get("unresolved", []) if str(row.get("scope", "")) == scope]


def query_canonical(data: dict[str, Any], canonical_id: str) -> list[dict[str, Any]]:
    data = validate_registry_shape(data)
    return [
        row
        for row in data.get("canonical_entities", [])
        if str(row.get("canonical_id", "")) == canonical_id
    ]


def query_source(data: dict[str, Any], manifestation_id: str) -> list[dict[str, Any]]:
    data = validate_registry_shape(data)
    return [
        row
        for row in data.get("source_manifestations", [])
        if str(row.get("manifestation_id", "")) == manifestation_id
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--evidence-bridge", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--scope")
    group.add_argument("--canonical-id")
    group.add_argument("--source-manifestation-id")
    group.add_argument("--bridge-summary", action="store_true")
    args = parser.parse_args()

    try:
        data = load_registry(args.registry)
        bridge = load_bridge(args.evidence_bridge) if args.evidence_bridge else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    if args.bridge_summary:
        if bridge is None:
            parser.error("--bridge-summary requires --evidence-bridge")
        result: Any = bridge_summary(bridge)
    elif args.scope:
        result = query_scope(data, args.scope)
    elif args.canonical_id:
        result = query_canonical(data, args.canonical_id)
    elif args.source_manifestation_id:
        result = query_source(data, args.source_manifestation_id)
    else:
        result = summary(data)

    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
