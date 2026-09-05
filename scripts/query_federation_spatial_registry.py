#!/usr/bin/env python3
"""Read-only query adapter for the federation spatial identity registry.

TheHub orchestrates discovery and provenance. It does not transform geometry,
resolve identity, or mutate the producer-owned Spiderweb registry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "federation-spatial-contract/1.1"


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("unsupported spatial registry contract")
    return data


def summary(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": data["contract_version"],
        "source_manifestations": len(data.get("source_manifestations", [])),
        "geometry_manifestations": len(data.get("geometry_manifestations", [])),
        "canonical_entities": len(data.get("canonical_entities", [])),
        "identity_bindings": len(data.get("identity_bindings", [])),
        "unresolved": len(data.get("unresolved", [])),
    }


def query_scope(data: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    return [
        row for row in data.get("unresolved", []) if str(row.get("scope", "")) == scope
    ]


def query_canonical(data: dict[str, Any], canonical_id: str) -> list[dict[str, Any]]:
    return [
        row
        for row in data.get("canonical_entities", [])
        if str(row.get("canonical_id", "")) == canonical_id
    ]


def query_source(data: dict[str, Any], manifestation_id: str) -> list[dict[str, Any]]:
    return [
        row
        for row in data.get("source_manifestations", [])
        if str(row.get("manifestation_id", "")) == manifestation_id
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--scope")
    group.add_argument("--canonical-id")
    group.add_argument("--source-manifestation-id")
    args = parser.parse_args()

    data = load_registry(args.registry)
    if args.scope:
        result: Any = query_scope(data, args.scope)
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
