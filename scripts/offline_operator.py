#!/usr/bin/env python3
"""Offline Federation operator scaffold.

Standard-library only. Generates the local offline package contract without a
localhost server, external JavaScript, or live network dependency.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROFILES: dict[str, dict[str, Any]] = {
    "thehub-pr": {"node_type": "hub", "focus": "Federation aggregation and validation.", "dims": ["child_package_ingest", "readiness_rollup", "blocker_rollup"]},
    "skywatcher-pr": {"node_type": "producer", "focus": "Airspace, SATIM, FR24, and platform normalization.", "dims": ["airspace_batches", "satim_calibration", "fr24_parser"]},
    "moneysweep-pr": {"node_type": "producer", "focus": "Contracts, procurement, permits, legislation, and public finance signals.", "dims": ["contract_pipeline", "entity_resolution", "legislation_permits"]},
    "aguayluz-pr": {"node_type": "producer", "focus": "Water, electric, and infrastructure dependency records.", "dims": ["water_assets", "electric_assets", "relationship_graph"]},
    "centinelas-pr": {"node_type": "producer", "focus": "Source-neutral watch queries, alert matching, and repo routing.", "dims": ["watch_queries", "keyword_taxonomy", "alert_matcher"]},
    "ovnis-pr": {"node_type": "producer", "focus": "Puerto Rico anomaly case registry and pattern-convergence records.", "dims": ["case_registry", "evidence_tiers", "pattern_tags"]},
    "spiderweb-pr": {"node_type": "producer", "focus": "Entity, relationship, dependency, and graph exports.", "dims": ["entity_registry", "edge_schema", "graph_exports"]},
}

STANDARD_DIMS = [
    "repo_structure", "schema_contracts", "source_registry", "data_pipeline",
    "validation_gates", "evidence_ledger", "operator_report", "offline_dashboard",
    "hub_compatibility", "production_status", "security_secrets", "documentation",
    "blocker_tracking", "release_packaging",
]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo() -> str:
    return Path.cwd().name


def profile(name: str) -> dict[str, Any]:
    return PROFILES.get(name, {"node_type": "producer", "focus": "Federation offline package.", "dims": []})


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def output_dir(argv: list[str] | None) -> Path:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--output", default="exports/federation")
    ns, _ = p.parse_known_args(argv)
    return Path(ns.output)


def readiness(name: str, stamp: str) -> dict[str, Any]:
    dims = []
    for d in STANDARD_DIMS:
        complete = 50 if d in {"operator_report", "offline_dashboard", "blocker_tracking", "release_packaging"} else 25
        dims.append({"id": d, "label": d.replace("_", " ").title(), "completion_pct": complete, "status": "yellow" if complete >= 50 else "unknown", "required": True, "blockers": [], "evidence_refs": []})
    for d in profile(name)["dims"]:
        dims.append({"id": d, "label": d.replace("_", " ").title(), "completion_pct": 0, "status": "unknown", "required": True, "blockers": ["BLOCKER-REPO-INTEGRATION"], "evidence_refs": []})
    overall = round(sum(d["completion_pct"] for d in dims) / len(dims))
    return {"schema_version": "federation.readiness.v1", "repo": name, "generated_at": stamp, "overall_status": "red" if overall < 40 else "yellow", "overall_completion_pct": overall, "dimensions": dims}


def blockers(name: str, stamp: str) -> dict[str, Any]:
    return {"schema_version": "federation.blockers.v1", "repo": name, "generated_at": stamp, "blockers": [{"id": "BLOCKER-REPO-INTEGRATION", "severity": "medium", "status": "open", "scope": "export", "title": "Connect offline scaffold to repo-native artifacts", "impact": "The offline contract exists, but repo-specific pipeline outputs still need to be mapped into readiness and evidence files.", "resolution": "Replace scaffold defaults with repo-native export, validation, and evidence outputs.", "evidence_refs": []}]}


def sources(name: str, stamp: str) -> dict[str, Any]:
    cats = ["manual_upload", "derived", "official", "media"]
    return {"schema_version": "federation.sources.v1", "repo": name, "generated_at": stamp, "sources": [{"source_id": f"SOURCE-{i:03d}", "name": c.replace("_", " ").title(), "category": c, "access_method": "manual", "scope": "puerto_rico", "authority_level": "unknown", "cadence": "unknown", "status": "candidate", "notes": "Scaffold placeholder; replace with repo-native source registry entries."} for i, c in enumerate(cats, 1)]}


def evidence(path: Path, name: str, stamp: str) -> None:
    rows = [
        ["EVID-001", name, "T1", "Manifest generated", "manifest.json", "manifest", "scripts/offline_operator.py", "generated", "", stamp],
        ["EVID-002", name, "T1", "Readiness generated", "readiness.json", "readiness", "scripts/offline_operator.py", "generated", "", stamp],
        ["EVID-003", name, "T2", "Operator report generated", "operator_report.md", "report", "scripts/offline_operator.py", "generated", "", stamp],
        ["EVID-004", name, "T2", "Offline dashboard generated", "dashboard.html", "offline_dashboard", "scripts/offline_operator.py", "pending", "", stamp],
    ]
    with (path / "evidence_ledger.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["evidence_id", "repo", "evidence_tier", "claim", "artifact_path", "artifact_type", "generated_by", "validation_status", "sha256", "notes"])
        w.writerows(rows)


def refresh_manifest(path: Path, name: str) -> None:
    r = read_json(path / "readiness.json", {})
    b = read_json(path / "blockers.json", {"blockers": []})
    s = read_json(path / "sources.json", {"sources": []})
    files = []
    for p in sorted(path.glob("*")):
        if p.is_file() and not p.name.endswith("_federation_package.zip"):
            files.append({"path": p.name, "type": p.suffix.lstrip(".") or "file", "sha256": sha256(p)})
    manifest = {"schema_version": "federation.offline_package.v1", "repo": name, "node_type": profile(name)["node_type"], "package_id": f"{name}_{now()}", "generated_at": now(), "commit_sha": git(["rev-parse", "HEAD"]), "branch": git(["rev-parse", "--abbrev-ref", "HEAD"]), "data_mode": "diagnostic_seed", "production_status": "diagnostic", "offline_ready": True, "localhost_required": False, "summary": {"records": 0, "sources": len(s.get("sources", [])), "blockers_open": sum(1 for x in b.get("blockers", []) if x.get("status") == "open"), "critical_blockers_open": sum(1 for x in b.get("blockers", []) if x.get("severity") == "critical" and x.get("status") == "open"), "evidence_items": 4, "overall_completion_pct": r.get("overall_completion_pct", 0)}, "files": files, "gates": {"tests": "unknown", "schema_validation": "unknown", "export_generated": "pass", "offline_dashboard_generated": "pass" if (path / "dashboard.html").exists() else "fail", "hub_ingest_compatible": "unknown"}}
    write_json(path / "manifest.json", manifest)


def export_cmd(argv: list[str] | None = None) -> int:
    path = output_dir(argv)
    path.mkdir(parents=True, exist_ok=True)
    (path / "artifacts").mkdir(exist_ok=True)
    name, stamp = repo(), now()
    r, b, s = readiness(name, stamp), blockers(name, stamp), sources(name, stamp)
    write_json(path / "readiness.json", r)
    write_json(path / "blockers.json", b)
    write_json(path / "sources.json", s)
    evidence(path, name, stamp)
    report = f"# {name} Offline Operator Report\n\n{profile(name)['focus']}\n\n- Overall status: `{r['overall_status']}`\n- Overall completion: `{r['overall_completion_pct']}%`\n- Localhost required: `false`\n- Production status: `diagnostic`\n\n## Open Blockers\n\n- `BLOCKER-REPO-INTEGRATION`: connect scaffold outputs to repo-native artifacts.\n"
    (path / "operator_report.md").write_text(report, encoding="utf-8")
    refresh_manifest(path, name)
    print(f"exported offline contract to {path}")
    return 0


def dashboard_cmd(argv: list[str] | None = None) -> int:
    path = output_dir(argv)
    name = repo()
    r = read_json(path / "readiness.json", readiness(name, now()))
    b = read_json(path / "blockers.json", blockers(name, now()))
    s = read_json(path / "sources.json", sources(name, now()))
    dim_rows = "".join(f"<tr><td>{html.escape(d['id'])}</td><td>{html.escape(d['status'])}</td><td>{d['completion_pct']}%</td></tr>" for d in r.get("dimensions", []))
    block_rows = "".join(f"<tr><td>{html.escape(x['id'])}</td><td>{html.escape(x['severity'])}</td><td>{html.escape(x['status'])}</td><td>{html.escape(x['title'])}</td></tr>" for x in b.get("blockers", []))
    src_rows = "".join(f"<tr><td>{html.escape(x['source_id'])}</td><td>{html.escape(x['name'])}</td><td>{html.escape(x['category'])}</td><td>{html.escape(x['status'])}</td></tr>" for x in s.get("sources", []))
    data = json.dumps({"readiness": r, "blockers": b, "sources": s}).replace("</", "<\\/")
    doc = f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(name)} Offline Dashboard</title><style>body{{font-family:system-ui;margin:2rem}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:.4rem}}th{{background:#f5f5f5}}.card{{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}}</style></head><body><h1>{html.escape(name)} Offline Dashboard</h1><p><strong>localhost_required=false</strong></p><section class='card'><h2>Summary</h2><p>Status: {r.get('overall_status')}</p><p>Completion: {r.get('overall_completion_pct')}%</p><p>Sources: {len(s.get('sources', []))}</p></section><section class='card'><h2>Readiness</h2><table><tr><th>Dimension</th><th>Status</th><th>Completion</th></tr>{dim_rows}</table></section><section class='card'><h2>Blockers</h2><table><tr><th>ID</th><th>Severity</th><th>Status</th><th>Title</th></tr>{block_rows}</table></section><section class='card'><h2>Sources</h2><table><tr><th>ID</th><th>Name</th><th>Category</th><th>Status</th></tr>{src_rows}</table></section><script id='offline-data' type='application/json'>{data}</script></body></html>\n"
    path.mkdir(parents=True, exist_ok=True)
    (path / "dashboard.html").write_text(doc, encoding="utf-8")
    refresh_manifest(path, name)
    print(f"wrote {path / 'dashboard.html'}")
    return 0


def package_cmd(argv: list[str] | None = None) -> int:
    path, name = output_dir(argv), repo()
    refresh_manifest(path, name)
    z = path / f"{name}_federation_package.zip"
    if z.exists():
        z.unlink()
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as bundle:
        for p in sorted(path.rglob("*")):
            if p.is_file() and p != z and p.name != "package.sha256":
                bundle.write(p, p.relative_to(path.parent))
    (path / "package.sha256").write_text(f"{sha256(z)}  {z.name}\n", encoding="utf-8")
    refresh_manifest(path, name)
    print(f"packaged {z}")
    return 0


def validate_dir(path: Path, require_package: bool = True) -> list[str]:
    req = ["manifest.json", "readiness.json", "blockers.json", "sources.json", "evidence_ledger.csv", "operator_report.md", "dashboard.html"]
    if require_package:
        req.append("package.sha256")
    errors = [f"missing {x}" for x in req if not (path / x).exists()]
    for x in ["manifest.json", "readiness.json", "blockers.json", "sources.json"]:
        if (path / x).exists():
            try:
                json.loads((path / x).read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"invalid {x}: {exc}")
    m = read_json(path / "manifest.json", {})
    if m.get("localhost_required") is not False:
        errors.append("manifest.localhost_required must be false")
    if m.get("offline_ready") is not True:
        errors.append("manifest.offline_ready must be true")
    if require_package and not list(path.glob("*_federation_package.zip")):
        errors.append("missing federation package zip")
    return errors


def validate_cmd(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="exports/federation")
    p.add_argument("--allow-unpackaged", action="store_true")
    ns = p.parse_args(argv)
    errors = validate_dir(Path(ns.output), not ns.allow_unpackaged)
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    if not errors:
        print(f"validation passed for {ns.output}")
    return 1 if errors else 0


def hub_validate_cmd(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="..")
    p.add_argument("--output", default="exports/federation/readiness_matrix.json")
    ns = p.parse_args(argv)
    rows = []
    for manifest in sorted(Path(ns.root).glob("*/exports/federation/manifest.json")):
        exp = manifest.parent
        m = read_json(manifest, {})
        r = read_json(exp / "readiness.json", {})
        b = read_json(exp / "blockers.json", {"blockers": []})
        rows.append({"repo": m.get("repo", exp.parent.parent.name), "status": r.get("overall_status", "unknown"), "completion_pct": r.get("overall_completion_pct", 0), "localhost_required": m.get("localhost_required"), "open_blockers": sum(1 for x in b.get("blockers", []) if x.get("status") == "open"), "validation_errors": validate_dir(exp, False)})
    out = Path(ns.output)
    write_json(out, {"schema_version": "federation.readiness_matrix.v1", "generated_at": now(), "repos": rows})
    report = Path("reports/federation_readiness_matrix.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Federation Offline Readiness Matrix", "", "| Repo | Status | Completion | Localhost Required | Open Blockers | Errors |", "|---|---:|---:|---:|---:|---|"]
    lines += [f"| {x['repo']} | {x['status']} | {x['completion_pct']}% | {x['localhost_required']} | {x['open_blockers']} | {len(x['validation_errors'])} |" for x in rows]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} and {report}")
    return 0 if all(not x["validation_errors"] for x in rows) else 1


def run(cmd: str, argv: list[str] | None = None) -> int:
    return {"export": export_cmd, "dashboard": dashboard_cmd, "package": package_cmd, "validate": validate_cmd, "hub-validate": hub_validate_cmd}[cmd](argv)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["export", "dashboard", "package", "validate", "hub-validate"])
    ns, rest = p.parse_known_args(argv)
    return run(ns.command, rest)


if __name__ == "__main__":
    raise SystemExit(main())
