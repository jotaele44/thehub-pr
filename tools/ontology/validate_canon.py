#!/usr/bin/env python3
"""Fail-closed validation gates for the PRII federation ontology."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import jsonschema
import yaml

try:
    from generate_canon import build as build_manifest
except ImportError:  # pragma: no cover
    from tools.ontology.generate_canon import build as build_manifest

CURIE_RE = re.compile(r"^[a-z][a-z0-9_-]*:[A-Za-z][A-Za-z0-9_-]*$")
EXPECTED_PROGRAMS = {
    "thehub-pr", "spiderweb-pr", "centinelas-pr", "aguayluz-pr",
    "ovnis-pr", "skywatcher-pr", "moneysweep-pr",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_definitions(document: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for key in ("classes", "properties"):
        values = document.get(key, [])
        if isinstance(values, list):
            for value in values:
                if isinstance(value, Mapping):
                    yield value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--require-generated", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    ontology = root / "federation/ontology"
    required_paths = [
        ontology / "CHARTER.md", ontology / "NAMESPACES.yaml", ontology / "LIFECYCLE_POLICY.md",
        ontology / "repository-pins.json", ontology / "schemas/term-record.schema.json",
        ontology / "schemas/raw-term-record.schema.json", ontology / "schemas/competency-question.schema.json",
        ontology / "core/core.jsonld", root / "schemas/common/lineage.schema.json",
    ]
    for path in required_paths:
        if not path.exists():
            errors.append(f"missing required file: {path.relative_to(root)}")

    for path in sorted(ontology.rglob("*.json")) + sorted(ontology.rglob("*.jsonld")) + [root / "schemas/common/lineage.schema.json"]:
        if path.exists():
            try:
                load_json(path)
            except Exception as exc:
                errors.append(f"invalid JSON {path.relative_to(root)}: {exc}")
    for path in sorted(ontology.rglob("*.yaml")) + sorted(ontology.rglob("*.yml")):
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid YAML {path.relative_to(root)}: {exc}")

    # Validate declared JSON Schemas against their metaschemas and competency fixtures.
    schema_paths = sorted((ontology / "schemas").glob("*.schema.json")) + [root / "schemas/common/lineage.schema.json"]
    schemas: dict[str, Mapping[str, Any]] = {}
    for path in schema_paths:
        if not path.exists():
            continue
        try:
            schema = load_json(path)
            jsonschema.validators.validator_for(schema).check_schema(schema)
            schemas[path.name] = schema
        except Exception as exc:
            errors.append(f"invalid JSON Schema {path.relative_to(root)}: {exc}")
    cq_schema = schemas.get("competency-question.schema.json")
    if cq_schema:
        validator = jsonschema.validators.validator_for(cq_schema)(cq_schema)
        for path in sorted((ontology / "competency").glob("CQ-*.json")):
            for error in validator.iter_errors(load_json(path)):
                errors.append(f"competency fixture {path.name}: {error.message}")

    pins = load_json(ontology / "repository-pins.json") if (ontology / "repository-pins.json").exists() else {}
    repositories = pins.get("repositories", []) if isinstance(pins, Mapping) else []
    program_ids = [str(item.get("program_id")) for item in repositories if isinstance(item, Mapping)]
    if set(program_ids) != EXPECTED_PROGRAMS or len(program_ids) != 7:
        errors.append(f"repository pins must contain exactly the seven federation programs; got {sorted(program_ids)}")
    commits = [str(item.get("commit")) for item in repositories if isinstance(item, Mapping)]
    if any(not re.fullmatch(r"[a-f0-9]{40}", commit) for commit in commits):
        errors.append("every repository pin must be a full 40-character SHA")

    core_path = ontology / "core/core.jsonld"
    module_paths = sorted((ontology / "modules").glob("*.jsonld"))
    documents: list[tuple[Path, Mapping[str, Any]]] = []
    if core_path.exists():
        documents.append((core_path, load_json(core_path)))
    for path in module_paths:
        documents.append((path, load_json(path)))
    ids: list[str] = []
    owners: dict[str, Any] = {}
    refs: list[tuple[str, str]] = []
    for path, document in documents:
        is_module = path.parent.name == "modules"
        for definition in iter_definitions(document):
            identifier = definition.get("id")
            if not isinstance(identifier, str) or not CURIE_RE.fullmatch(identifier):
                errors.append(f"invalid or missing identifier in {path.relative_to(root)}: {identifier!r}")
                continue
            ids.append(identifier)
            owners[identifier] = definition.get("owner")
            if not definition.get("owner"):
                errors.append(f"unowned term: {identifier}")
            if is_module and identifier.startswith(("prii:", "contract:")):
                errors.append(f"repo module redefines federation namespace: {identifier} in {path.name}")
            parent = definition.get("subClassOf")
            if isinstance(parent, str):
                refs.append((identifier, parent))
    duplicate_ids = sorted(identifier for identifier, count in Counter(ids).items() if count > 1)
    if duplicate_ids:
        errors.append(f"duplicate canonical identifiers: {duplicate_ids}")
    known_ids = set(ids)
    for source, target in refs:
        if target not in known_ids:
            errors.append(f"undefined reference: {source} -> {target}")

    resolutions_path = ontology / "resolutions/priority-term-families.yaml"
    resolutions = yaml.safe_load(resolutions_path.read_text(encoding="utf-8")) if resolutions_path.exists() else {}
    families = resolutions.get("families", {}) if isinstance(resolutions, Mapping) else {}
    for family_name in ("source", "observation", "relationship", "evidence", "alert", "confidence", "status", "public_matter"):
        family = families.get(family_name) if isinstance(families, Mapping) else None
        if not isinstance(family, Mapping):
            errors.append(f"missing priority resolution family: {family_name}")
            continue
        if family.get("severity") == "high" and not family.get("owner"):
            errors.append(f"high-severity priority family has no owner: {family_name}")
        if not family.get("disposition"):
            errors.append(f"priority family has no disposition: {family_name}")
        for identifier in family.get("canonical_terms", []):
            if identifier not in known_ids and not any(identifier in {d.get('id') for d in iter_definitions(doc)} for _, doc in documents):
                errors.append(f"priority resolution references undefined term: {identifier}")
    confidence = families.get("confidence", {}) if isinstance(families, Mapping) else {}
    for prop in confidence.get("required_properties", []) if isinstance(confidence, Mapping) else []:
        if prop not in known_ids:
            errors.append(f"confidence resolution requires undefined property: {prop}")
    if len(set(confidence.get("known_scales", []))) < 2 if isinstance(confidence, Mapping) else True:
        errors.append("confidence resolution must declare both known scales")

    mappings_path = ontology / "mappings/legacy-mappings.yaml"
    mappings = yaml.safe_load(mappings_path.read_text(encoding="utf-8")) if mappings_path.exists() else {}
    for mapping in mappings.get("mappings", []) if isinstance(mappings, Mapping) else []:
        if isinstance(mapping, Mapping) and mapping.get("target") not in known_ids:
            errors.append(f"legacy mapping target undefined: {mapping.get('target')}")

    manifest_path = ontology / "CANON_MANIFEST.json"
    if manifest_path.exists():
        actual_manifest = load_json(manifest_path)
        expected_manifest = build_manifest(root)
        if actual_manifest != expected_manifest:
            errors.append("generated ontology manifest drift")
    else:
        errors.append("missing federation/ontology/CANON_MANIFEST.json")

    generated = ontology / "generated"
    if args.require_generated:
        required_generated = [
            "raw-term-ledger.jsonl", "coverage.json", "deduplicated-observations.jsonl",
            "synonym-candidates.json", "homonym-conflicts.json", "scale-conflicts.json",
            "identity-conflicts.json", "cardinality-conflicts.json", "lifecycle-conflicts.json",
            "authority-conflicts.json", "priority-resolution-status.json", "summary.json",
        ]
        for name in required_generated:
            if not (generated / name).exists():
                errors.append(f"missing generated artifact: {name}")
        if (generated / "coverage.json").exists():
            coverage = load_json(generated / "coverage.json")
            if not coverage.get("all_repositories_100_percent"):
                errors.append("seven-repository eligible-file coverage is not 100%")
            if coverage.get("repositories_scanned") != 7:
                errors.append("coverage report does not include seven repositories")
        if (generated / "summary.json").exists():
            summary = load_json(generated / "summary.json")
            if not summary.get("coordinated_pr_gate"):
                errors.append("coordinated PR gate is false")

    if args.workspace:
        for item in repositories:
            if not isinstance(item, Mapping):
                continue
            repo_root = args.workspace / str(item["directory"])
            if item.get("program_id") == "thehub-pr":
                hub_contract = repo_root / "schemas/repo_federation_manifest.schema.json"
                if not hub_contract.exists():
                    errors.append("Hub contract schema missing: thehub-pr/schemas/repo_federation_manifest.schema.json")
                continue
            manifest = repo_root / "federation.json"
            if not manifest.exists():
                errors.append(f"cross-repo contract missing: {item['program_id']}/federation.json")
                continue
            try:
                data = load_json(manifest)
            except Exception as exc:
                errors.append(f"invalid producer manifest {item['program_id']}: {exc}")
                continue
            if data.get("program_id") != item.get("program_id"):
                errors.append(f"program identity mismatch in {item['program_id']}/federation.json")
            if item.get("program_id") != "thehub-pr" and data.get("hub_parent") != "thehub-pr":
                errors.append(f"hub_parent mismatch in {item['program_id']}/federation.json")

    report = {
        "schema_version": "1.0.0",
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "canonical_identifier_count": len(ids),
        "module_count": len(module_paths),
        "repository_pin_count": len(program_ids),
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
