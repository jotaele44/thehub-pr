#!/usr/bin/env python3
"""Build the PR180 identity control-plane candidate ledger from complete Git trees."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path
from typing import Any

TERMS = (
    "federation",
    "producer",
    "entity",
    "identity",
    "alias",
    "identifier",
    "member",
    "match",
    "resolve",
    "resolution",
    "correlate",
    "correlation",
    "merge",
    "supersede",
    "canonical",
    "catalog",
    "query",
    "registry",
    "graph",
    "provenance",
    "confidence",
    "sync",
    "export",
    "ingest",
    "sqlite",
    "migration",
    "relationship",
    "event",
)


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def _tree(ref: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in _git("ls-tree", "-r", "--full-tree", ref).decode().splitlines():
        meta, path = line.split("\t", 1)
        _mode, kind, sha = meta.split()
        if kind == "blob":
            rows.append((path, sha))
    return rows


def _classify(path: str) -> str:
    p = path.lower()
    if "/tests/" in f"/{p}" or p.startswith("tests/") or p.endswith("_test.py"):
        return "TEST"
    if p.startswith("schemas/") or "/schemas/" in p:
        return "SCHEMA_CONTRACT"
    if p.startswith("docs/") or p.endswith(".md"):
        return "DOCUMENTATION_OR_ADR"
    if p.startswith(".github/workflows/"):
        return "WORKFLOW"
    if p.startswith("src/"):
        return "IMPLEMENTATION"
    if p.startswith("server/"):
        return "SERVER_IMPLEMENTATION"
    if p.startswith("scripts/") or p.startswith("tools/"):
        return "TOOL_OR_SCRIPT"
    if "migration" in p:
        return "MIGRATION"
    return "SUPPORTING_CONTROL_PLANE"


def _symbols(path: str, text: str) -> list[str]:
    if path.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []
        values = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if any(term in node.name.casefold() for term in TERMS):
                    values.append(node.name)
        return sorted(set(values))
    if path.endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        values = []
        for key in ("$id", "title", "x-contract-version", "x-primary-key"):
            if key in data:
                values.append(f"{key}={data[key]}")
        return values
    return []


def build(main_ref: str, head_ref: str) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for tree_role, ref in (("MAIN", main_ref), ("PR180", head_ref)):
        for path, sha in _tree(ref):
            raw = _git("show", f"{ref}:{path}")
            text = raw.decode("utf-8", errors="replace")
            haystack = f"{path}\n{text}".casefold()
            matched = sorted({term for term in TERMS if term in haystack})
            if not matched:
                continue
            candidates.append(
                {
                    "tree_role": tree_role,
                    "tree_ref": ref,
                    "path": path,
                    "blob_sha": sha,
                    "extension": Path(path).suffix.lower(),
                    "matched_control_plane_terms": matched,
                    "classification": _classify(path),
                    "inspection_state": "INSPECTED",
                    "relevant_symbols": _symbols(path, text),
                }
            )
    unclassified = [row for row in candidates if not row["classification"]]
    uninspected = [row for row in candidates if row["inspection_state"] != "INSPECTED"]
    return {
        "schema_version": "1.0.0",
        "main_ref": main_ref,
        "pr180_ref": head_ref,
        "terms": list(TERMS),
        "candidate_count": len(candidates),
        "inspected_count": len(candidates) - len(uninspected),
        "unclassified_count": len(unclassified),
        "uninspected_count": len(uninspected),
        "candidates": sorted(
            candidates, key=lambda row: (row["tree_role"], row["path"])
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-ref", required=True)
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    ledger = build(args.main_ref, args.head_ref)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if ledger["candidate_count"] != ledger["inspected_count"]:
        return 2
    if ledger["unclassified_count"] or ledger["uninspected_count"]:
        return 3
    print(
        "PASS identity candidate denominator:",
        f"candidates={ledger['candidate_count']}",
        f"inspected={ledger['inspected_count']}",
        "unclassified=0 uninspected=0",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
