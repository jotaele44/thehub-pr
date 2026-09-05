#!/usr/bin/env python3
"""B.1-B.5 authority-boundary certification gate, quarantine-aware v2."""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

AUTHORITY = "prii-federation-spatial-identity"
TEXT_EXTS = {".py", ".json", ".yaml", ".yml", ".toml", ".ts", ".tsx", ".js", ".jsx"}
SKIP = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}


def j(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in TEXT_EXTS and not any(x in SKIP for x in p.parts):
            yield p, p.read_text(encoding="utf-8", errors="replace")


def rel_literals(text: str) -> set[str]:
    out = set()
    for rx in (
        r'["\']relationship_type["\']\s*:\s*["\']([^"\']+)["\']',
        r'\brelationship_type\s*=\s*["\']([^"\']+)["\']',
        r'^\s*-\s+id:\s*([A-Za-z0-9_.:-]+)\s*$',
    ):
        out.update(re.findall(rx, text, re.M))
    return {x for x in out if 0 < len(x) <= 96 and "{" not in x}


def id_signals(text: str) -> set[str]:
    out = set()
    for rx in (
        r'\b(?:ID_PREFIX|id_prefix|uid_prefix|visual_id_prefix)\s*[:=]\s*["\']([^"\']+)["\']',
        r'\bprefix\s*=\s*["\']([A-Za-z0-9_.:-]{2,32})["\']',
    ):
        out.update(re.findall(rx, text))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--peer-root", default="_authority_peers")
    ap.add_argument("--report", default="reports/authority_boundary_validation.json")
    a = ap.parse_args()
    root, peers = Path(a.repo_root).resolve(), Path(a.peer_root).resolve()

    snapshots = j(root / "registry/federation/repository_snapshots.json")
    ids = j(root / "registry/federation/identifier_namespaces.json")
    rels = j(root / "registry/federation/relationship_types.json")
    quarantine = j(root / "registry/federation/legacy_identity_registry_quarantine.json")
    grid = j(root / "registry/spatial/pr_grid_full_cell_index_saturated.manifest.json")
    admin = j(root / "registry/spatial/federation_admin_geometry.manifest.json")

    blockers, findings = [], []
    rows = snapshots["repositories"]
    paths = {"thehub-pr": root, **{r["program_id"]: peers / r["program_id"] for r in rows if r["program_id"] != "thehub-pr"}}
    if snapshots.get("denominator") != 7 or len(rows) != 7 or len(set(paths)) != 7:
        blockers.append({"id":"B-REPO-DENOMINATOR","detail":len(rows)})
    missing = [k for k, p in paths.items() if not p.exists()]
    if missing:
        blockers.append({"id":"B-REPO-MISSING","detail":missing})

    # B.1 — The historical Hub registry is allowed only because it is explicitly quarantined and
    # production code is forbidden to import it.
    if quarantine.get("state") != "LEGACY_NONAUTHORITATIVE_TEST_FIXTURE" or quarantine.get("superseding_authority") != AUTHORITY:
        blockers.append({"id":"AB-001-BAD-QUARANTINE","detail":quarantine})
    prod_imports = []
    for p, text in files(root / "src"):
        if p.as_posix().endswith("src/hub/identity_registry.py"):
            continue
        if "hub.identity_registry" in text or "from .identity_registry" in text or "import identity_registry" in text:
            prod_imports.append(str(p.relative_to(root)))
    if prod_imports:
        blockers.append({"id":"AB-001-ACTIVE-HUB-AUTHORITY","detail":prod_imports})
    # Any separate active implementation assigning the Hub sovereignty is still forbidden.
    leaks = []
    for pid, rroot in paths.items():
        if not rroot.exists():
            continue
        for p, text in files(rroot):
            rel = str(p.relative_to(rroot))
            if pid == "thehub-pr" and rel in {quarantine["path"], "registry/federation/legacy_identity_registry_quarantine.json"}:
                continue
            if re.search(r'FEDERATION_AUTHORITY\s*=\s*["\']thehub-pr["\']', text):
                leaks.append({"repo":pid,"path":rel})
    if leaks:
        blockers.append({"id":"AB-001-OTHER-AUTHORITY-LEAK","detail":leaks})

    # B.2 — geometry substrate.
    if grid.get("canonical_ground_geometry") is not False or grid.get("georeferenced") is not False:
        blockers.append({"id":"AB-002-GRID","detail":grid.get("status")})
    if admin.get("authority_plane") != AUTHORITY or admin.get("source_vintage") != "2023" or admin.get("canonical_crs") != "EPSG:4326":
        blockers.append({"id":"AB-005-ADMIN","detail":admin})
    layer_counts = {x.get("expected_feature_count") for x in admin.get("layers", [])}
    if layer_counts != {78, 901} or any(not re.fullmatch(r"[0-9a-f]{40}", x.get("git_blob_sha", "")) for x in admin.get("layers", [])):
        blockers.append({"id":"AB-005-ADMIN-PIN","detail":admin.get("layers")})

    # B.3 — identifier registry structure plus repository emission census.
    ns = ids.get("namespaces", [])
    if len({x["namespace"] for x in ns}) != len(ns):
        blockers.append({"id":"AB-003-DUPLICATE-NAMESPACE"})
    for x in ns:
        try:
            re.compile(x["pattern"])
        except re.error as e:
            blockers.append({"id":"AB-003-BAD-REGEX","detail":[x["namespace"],str(e)]})
        if x.get("scope") in {"SHARED_IDENTITY","SHARED_RELATIONSHIP"} and x.get("owner") != AUTHORITY:
            blockers.append({"id":"AB-003-SHARED-OWNER","detail":x})
    owned = defaultdict(list)
    for x in ns:
        owned[x["owner"]].append(x)
    signal_census = defaultdict(set)
    relation_census = defaultdict(set)
    for pid, rroot in paths.items():
        if not rroot.exists():
            continue
        for p, text in files(rroot):
            signal_census[pid].update(id_signals(text))
            relation_census[pid].update(rel_literals(text))
    for pid, sigs in signal_census.items():
        if sigs and pid not in owned and pid != "thehub-pr":
            blockers.append({"id":"AB-003-UNDECLARED-REPO","detail":{"repo":pid,"signals":sorted(sigs)}})
    # Explicit provisional marker is itself blocking; remove only after the crawler output has
    # been reconciled into the registry.
    if ids.get("census_state") != "EXHAUSTIVE_CRAWLER_RECONCILED":
        blockers.append({"id":"AB-003-CENSUS-NOT-RECONCILED","detail":ids.get("census_state")})

    # B.4 — every producer with emitted relationship literals must have exactly one domain owner;
    # cross-producer same-literal collisions are prohibited unless the literal is shared.
    domain = {x["owner"] for x in rels.get("domain_registries", [])}
    for pid, vals in relation_census.items():
        if pid != "thehub-pr" and vals and pid not in domain:
            blockers.append({"id":"AB-004-UNOWNED-REPO","detail":{"repo":pid,"types":sorted(vals)}})
    shared = {x["id"] for x in rels.get("shared_relationships", [])}
    owners_by_literal = defaultdict(set)
    for pid, vals in relation_census.items():
        if pid == "thehub-pr":
            continue
        for val in vals:
            owners_by_literal[val].add(pid)
    collisions = {k:sorted(v) for k,v in owners_by_literal.items() if len(v)>1 and k not in shared}
    if collisions:
        blockers.append({"id":"AB-004-CROSS-PRODUCER-COLLISION","detail":collisions})
    if rels.get("census_state") != "EXHAUSTIVE_CRAWLER_RECONCILED":
        blockers.append({"id":"AB-004-CENSUS-NOT-RECONCILED","detail":rels.get("census_state")})

    findings.extend([
        {"id":"ID_SIGNAL_CENSUS","detail":{k:sorted(v) for k,v in signal_census.items()}},
        {"id":"RELATIONSHIP_LITERAL_CENSUS","detail":{k:sorted(v) for k,v in relation_census.items()}},
    ])
    report = {
        "schema_version":"authority_boundary_validation_v2",
        "authority_plane":AUTHORITY,
        "repository_denominator":len(rows),
        "blocker_count":len(blockers),
        "blockers":blockers,
        "findings":findings,
        "certification":"AUTHORITY_BOUNDARY_CERTIFIED" if not blockers else "NOT_CERTIFIED",
        "next_phase":"A_FEDERATION_IDENTITY_CONTRACT" if not blockers else "BLOCKED"
    }
    out = root / a.report
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
