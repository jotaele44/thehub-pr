#!/usr/bin/env python3
"""Fail-closed B-phase authority-boundary validator.

The validator operates on one candidate TheHub checkout plus the six producer checkouts
pinned in registry/federation/repository_snapshots.json. It does not infer semantic identity.
It inventories declared identifier/relationship signals and reports every authority ambiguity.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

TEXT_EXTS = {".py", ".json", ".jsonl", ".yaml", ".yml", ".md", ".toml", ".csv", ".ts", ".tsx", ".js", ".jsx"}
SKIP_PARTS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
AUTHORITY = "prii-federation-spatial-identity"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTS:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        try:
            yield path, path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue


def repo_paths(root: Path, peer_root: Path, snapshots: dict) -> dict[str, Path]:
    out = {"thehub-pr": root}
    for row in snapshots["repositories"]:
        pid = row["program_id"]
        if pid == "thehub-pr":
            continue
        out[pid] = peer_root / pid
    return out


def extract_relationship_literals(text: str) -> set[str]:
    vals: set[str] = set()
    # JSON/Python object literal and keyword assignment forms.
    for rx in (
        r'["\']relationship_type["\']\s*:\s*["\']([^"\']+)["\']',
        r'\brelationship_type\s*=\s*["\']([^"\']+)["\']',
        r'^\s*-\s+id:\s*([A-Za-z0-9_.:-]+)\s*$',
    ):
        vals.update(re.findall(rx, text, flags=re.MULTILINE))
    return {v for v in vals if 1 <= len(v) <= 96 and "{" not in v}


def extract_id_signals(text: str) -> set[str]:
    vals: set[str] = set()
    for rx in (
        r'\b(?:ID_PREFIX|id_prefix|uid_prefix|visual_id_prefix)\s*[:=]\s*["\']([^"\']+)["\']',
        r'\bprefix\s*=\s*["\']([A-Za-z0-9_.:-]{2,32})["\']',
        r'\^([A-Za-z0-9_.:-]{2,24})[^$]{0,80}\$',
    ):
        vals.update(re.findall(rx, text))
    return vals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--peer-root", default="_authority_peers")
    ap.add_argument("--report", default="reports/authority_boundary_validation.json")
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    peer_root = Path(args.peer_root).resolve()
    snapshots = load_json(root / "registry/federation/repository_snapshots.json")
    idreg = load_json(root / "registry/federation/identifier_namespaces.json")
    relreg = load_json(root / "registry/federation/relationship_types.json")
    grid = load_json(root / "registry/spatial/pr_grid_full_cell_index_saturated.manifest.json")
    admin = load_json(root / "registry/spatial/federation_admin_geometry.manifest.json")

    blockers: list[dict] = []
    findings: list[dict] = []

    repos = snapshots.get("repositories", [])
    if snapshots.get("denominator") != 7 or len(repos) != 7 or len({r["program_id"] for r in repos}) != 7:
        blockers.append({"id":"B-REPO-DENOMINATOR","detail":"Seven-repository frozen denominator does not close."})

    paths = repo_paths(root, peer_root, snapshots)
    missing = sorted(pid for pid, p in paths.items() if not p.exists())
    if missing:
        blockers.append({"id":"B-REPO-MISSING","detail":missing})

    # B.1: no active implementation may assign sovereign identity authority to TheHub.
    authority_leaks = []
    for pid, rroot in paths.items():
        if not rroot.exists():
            continue
        for path, text in iter_text_files(rroot):
            rel = str(path.relative_to(rroot))
            if rel == "docs/adr/0009-persistent-federation-identity-authority.md":
                continue
            if re.search(r'FEDERATION_AUTHORITY\s*=\s*["\']thehub-pr["\']', text):
                authority_leaks.append({"repo":pid,"path":rel,"match":"FEDERATION_AUTHORITY=thehub-pr"})
            elif path.suffix.lower() in {".py", ".json", ".yaml", ".yml"} and re.search(r'federation_authority.{0,80}["\']thehub-pr["\']', text, re.I | re.S):
                authority_leaks.append({"repo":pid,"path":rel,"match":"federation_authority -> thehub-pr"})
    if authority_leaks:
        blockers.append({"id":"AB-001-ACTIVE-HUB-AUTHORITY","detail":authority_leaks})

    # B.2: pixel grid must be noncanonical; shared admin geometry must be byte-pinned.
    if grid.get("canonical_ground_geometry") is not False or grid.get("georeferenced") is not False:
        blockers.append({"id":"AB-002-GRID-NOT-DEMOTED","detail":grid.get("status")})
    layers = admin.get("layers", [])
    if admin.get("authority_plane") != AUTHORITY or len(layers) != 2:
        blockers.append({"id":"AB-005-ADMIN-AUTHORITY","detail":"admin geometry manifest incomplete"})
    for layer in layers:
        if not re.fullmatch(r"[0-9a-f]{40}", layer.get("git_blob_sha", "")) or layer.get("crs") != "EPSG:4326":
            blockers.append({"id":"AB-005-ADMIN-PIN","detail":layer})

    # B.3 registry structural and negative-collision gates.
    namespaces = idreg.get("namespaces", [])
    names = [x.get("namespace") for x in namespaces]
    if len(names) != len(set(names)):
        blockers.append({"id":"AB-003-NAMESPACE-DUPLICATE","detail":"duplicate namespace name"})
    for ns in namespaces:
        try:
            re.compile(ns["pattern"])
        except Exception as exc:
            blockers.append({"id":"AB-003-BAD-PATTERN","detail":{"namespace":ns.get("namespace"),"error":str(exc)}})
    # Shared identity namespace must have exactly the independent authority owner.
    for ns in namespaces:
        if ns.get("scope") in {"SHARED_IDENTITY","SHARED_RELATIONSHIP"} and ns.get("owner") != AUTHORITY:
            blockers.append({"id":"AB-003-SHARED-OWNER-LEAK","detail":ns})

    id_signals: dict[str, set[str]] = defaultdict(set)
    rel_literals: dict[str, set[str]] = defaultdict(set)
    for pid, rroot in paths.items():
        if not rroot.exists():
            continue
        for path, text in iter_text_files(rroot):
            # Docs are evidence surfaces, but executable/config/schema declarations carry the census gate.
            if path.suffix.lower() == ".md":
                continue
            id_signals[pid].update(extract_id_signals(text))
            rel_literals[pid].update(extract_relationship_literals(text))

    # Registry must at least contain an owning namespace for each repo that emits an ID signal.
    owners = defaultdict(list)
    for ns in namespaces:
        owners[ns.get("owner")].append(ns)
    for pid, signals in sorted(id_signals.items()):
        if signals and pid not in owners and pid != "thehub-pr":
            blockers.append({"id":"AB-003-UNDECLARED-REPO-NAMESPACE","detail":{"repo":pid,"signals":sorted(signals)}})
    findings.append({"id":"ID_SIGNAL_CENSUS","detail":{k:sorted(v) for k,v in sorted(id_signals.items())}})

    # B.4: each repo's executable relationship literals resolve to exactly one declared domain owner,
    # while the Hub may only own derived candidate correlation semantics.
    declared_domain_owners = {d["owner"] for d in relreg.get("domain_registries", [])}
    for pid, values in sorted(rel_literals.items()):
        if not values:
            continue
        if pid == "thehub-pr":
            # Hub values are allowed only as derived/candidate surfaces; shared identity verbs live in shared_relationships.
            continue
        if pid not in declared_domain_owners:
            blockers.append({"id":"AB-004-UNOWNED-RELATIONSHIPS","detail":{"repo":pid,"types":sorted(values)}})
    # Same literal emitted by multiple producers is an authority collision unless explicitly registered as shared.
    by_literal: dict[str, set[str]] = defaultdict(set)
    for pid, values in rel_literals.items():
        if pid == "thehub-pr":
            continue
        for value in values:
            by_literal[value].add(pid)
    shared_ids = {x["id"] for x in relreg.get("shared_relationships", [])}
    collisions = {k:sorted(v) for k,v in by_literal.items() if len(v) > 1 and k not in shared_ids}
    if collisions:
        blockers.append({"id":"AB-004-CROSS-PRODUCER-RELATIONSHIP-COLLISION","detail":collisions})
    findings.append({"id":"RELATIONSHIP_LITERAL_CENSUS","detail":{k:sorted(v) for k,v in sorted(rel_literals.items())}})

    # Upstream Census vintage is intentionally unknown and therefore still blocks full source-lineage certification.
    if admin.get("source_vintage") == "UNKNOWN_NOT_ASSERTED":
        blockers.append({"id":"AB-005-CENSUS-VINTAGE-UNKNOWN","detail":"Pinned bytes close operational geometry, but exact upstream Census vintage remains unproven."})

    report = {
        "schema_version":"authority_boundary_validation_v1",
        "authority_plane":AUTHORITY,
        "repository_denominator":len(repos),
        "blocker_count":len(blockers),
        "blockers":blockers,
        "findings":findings,
        "certification":"AUTHORITY_BOUNDARY_CERTIFIED" if not blockers else "NOT_CERTIFIED",
        "next_phase":"A_FEDERATION_IDENTITY_CONTRACT" if not blockers else "BLOCKED"
    }
    out = root / args.report
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
