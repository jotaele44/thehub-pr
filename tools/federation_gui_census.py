#!/usr/bin/env python3
"""Generate a bounded, machine-readable GUI census for the frozen PRII federation snapshot.

This is discovery and arithmetic closure tooling, not a quality-certification shortcut.
Static regex findings remain CANDIDATE_NOT_IDENTITY-style discovery evidence until reviewed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPE_PATH = ROOT / "audit" / "federation_gui_scope.json"
OUT_DIR = ROOT / "audit" / "generated" / "federation_gui_census"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SKIP_DIRS = {
    "node_modules", "dist", "build", "coverage", ".git", ".vite",
    "playwright-report", "test-results", ".next", "storybook-static",
}
SOURCE_EXTS = {".jsx", ".tsx", ".js", ".ts", ".css", ".scss", ".html"}
VISUAL_EXTS = {".jsx", ".tsx"}
ROUTE_RE = re.compile(r"<Route\b[^>]*\bpath\s*=\s*[\"']([^\"']+)[\"']", re.S)
EVENT_RE = re.compile(r"\bon(?:Click|Change|Submit|KeyDown|KeyUp|KeyPress|Focus|Blur|Input|PointerDown|PointerUp|MouseDown|MouseUp|DragStart|DragEnd|Drop|DoubleClick)\s*=")
STATE_PATTERNS = {
    "loading": re.compile(r"\bloading\b|Skeleton|Spinner", re.I),
    "empty": re.compile(r"\bempty\b|No records|No results|EmptyState", re.I),
    "filtered_empty": re.compile(r"filtered[_ -]?empty|No matching records", re.I),
    "error": re.compile(r"\berror\b|ErrorState|ErrorBoundary", re.I),
    "partial": re.compile(r"\bpartial\b|PartialData", re.I),
    "offline": re.compile(r"\boffline\b|OfflineState", re.I),
    "degraded": re.compile(r"\bdegraded\b|DegradedState", re.I),
    "stale": re.compile(r"\bstale\b|StaleData", re.I),
    "unknown": re.compile(r"\bunknown\b", re.I),
    "unresolved": re.compile(r"\bunresolved\b", re.I),
    "superseded": re.compile(r"\bsuperseded\b", re.I),
    "contradiction": re.compile(r"\bcontradict(?:ion|ory)\b", re.I),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(repo_root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True).strip()


def classify_file(rel: Path) -> str:
    s = rel.as_posix().lower()
    name = rel.name.lower()
    if any(part in {"test", "tests", "__tests__"} for part in rel.parts) or ".test." in name or ".spec." in name:
        return "TEST"
    if "/pages/" in f"/{s}" or "/routes/" in f"/{s}":
        return "PAGE_OR_ROUTE"
    if "/components/" in f"/{s}":
        return "COMPONENT"
    if "/modules/" in f"/{s}":
        return "MODULE"
    if "/layouts/" in f"/{s}" or "layout" in name:
        return "LAYOUT"
    if "/hooks/" in f"/{s}" or name.startswith("use"):
        return "HOOK"
    if "/api/" in f"/{s}" or "client" in name:
        return "API_CLIENT"
    if rel.suffix in {".css", ".scss"}:
        return "STYLE"
    if rel.suffix in VISUAL_EXTS:
        return "VISUAL_OTHER"
    if rel.suffix in {".js", ".ts"}:
        return "NONVISUAL_SUPPORT"
    if rel.suffix == ".html":
        return "ENTRY_HTML"
    return "OTHER"


def source_files(frontend_root: Path):
    for path in frontend_root.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_EXTS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def parse_package(frontend_root: Path) -> dict:
    package_path = frontend_root / "package.json"
    if not package_path.exists():
        return {"present": False}
    package = json.loads(package_path.read_text(encoding="utf-8"))
    deps = {}
    deps.update(package.get("dependencies") or {})
    deps.update(package.get("devDependencies") or {})
    scripts = package.get("scripts") or {}
    return {
        "present": True,
        "name": package.get("name"),
        "react": deps.get("react"),
        "shared_design_package": deps.get("@pr-federation/react"),
        "scripts": sorted(scripts),
        "has_build": "build" in scripts,
        "has_lint": "lint" in scripts,
        "has_typecheck": "typecheck" in scripts,
        "has_test": "test" in scripts,
        "has_visual_test": any("visual" in key for key in scripts),
        "has_gui_parity_test": any("gui-parity" in key for key in scripts),
        "has_playwright_dependency": any("playwright" in key.lower() for key in deps),
    }


def spiderweb_modules(texts: list[tuple[str, str]]) -> list[str]:
    # SpiderWeb intentionally uses one workbench rather than a router. Capture the
    # top-level lazy module ids as its navigation-surface denominator.
    app = next((t for p, t in texts if p.endswith("src/App.tsx")), "")
    if "const MODULES" not in app:
        return []
    return sorted(set(re.findall(r"\bid\s*:\s*['\"]([^'\"]+)['\"]", app)))


def main() -> int:
    scope = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
    file_rows = []
    route_rows = []
    state_rows = []
    repo_rows = []
    fatal = []

    for item in scope["repositories"]:
        repo_name = item["repository"].split("/", 1)[1]
        checkout = ROOT if item["checkout_path"] == "." else ROOT / item["checkout_path"]
        frontend = checkout / item["frontend_root"]
        observed_head = git_head(checkout) if (checkout / ".git").exists() else None
        if observed_head != item["sha"]:
            fatal.append(f"{repo_name}: expected {item['sha']} observed {observed_head}")
        if not frontend.exists():
            fatal.append(f"{repo_name}: missing frontend root {item['frontend_root']}")
            continue

        package = parse_package(frontend)
        counts = Counter()
        state_files = defaultdict(list)
        route_candidates = set()
        interaction_occurrences = 0
        texts: list[tuple[str, str]] = []

        for path in source_files(frontend):
            rel = path.relative_to(frontend)
            category = classify_file(rel)
            counts[category] += 1
            text = path.read_text(encoding="utf-8", errors="replace")
            texts.append((rel.as_posix(), text))
            if path.suffix in VISUAL_EXTS:
                interaction_occurrences += len(EVENT_RE.findall(text))
            for route in ROUTE_RE.findall(text):
                route_candidates.add(route)
            for state, pattern in STATE_PATTERNS.items():
                if pattern.search(text):
                    state_files[state].append(rel.as_posix())
            file_rows.append({
                "repository": repo_name,
                "frontend_root": item["frontend_root"],
                "path": rel.as_posix(),
                "classification": category,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })

        for route in sorted(route_candidates):
            route_rows.append({
                "repository": repo_name,
                "surface_kind": "ROUTE",
                "surface_id": route,
                "discovery_method": "STATIC_ROUTE_DECLARATION",
                "review_state": "CANDIDATE_NOT_RUNTIME_CERTIFIED",
            })

        modules = spiderweb_modules(texts) if repo_name == "spiderweb-pr" else []
        for module in modules:
            route_rows.append({
                "repository": repo_name,
                "surface_kind": "WORKBENCH_MODULE",
                "surface_id": module,
                "discovery_method": "STATIC_MODULE_DECLARATION",
                "review_state": "CANDIDATE_NOT_RUNTIME_CERTIFIED",
            })

        for state in sorted(STATE_PATTERNS):
            files = sorted(state_files.get(state, []))
            state_rows.append({
                "repository": repo_name,
                "state": state,
                "observed_in_source": bool(files),
                "file_count": len(files),
                "files": ";".join(files),
                "review_state": "DISCOVERY_ONLY_NEEDS_BEHAVIORAL_REVIEW" if files else "NOT_OBSERVED_NOT_PROOF_OF_ABSENCE",
            })

        repo_rows.append({
            "repository": repo_name,
            "role": item["role"],
            "expected_sha": item["sha"],
            "observed_sha": observed_head,
            "frontend_root": item["frontend_root"],
            "source_files": sum(counts.values()),
            "visual_files": sum(counts[k] for k in ("PAGE_OR_ROUTE", "COMPONENT", "MODULE", "LAYOUT", "VISUAL_OTHER")),
            "tests": counts["TEST"],
            "routes": len(route_candidates),
            "workbench_modules": len(modules),
            "static_interaction_handler_occurrences": interaction_occurrences,
            "shared_design_package": package.get("shared_design_package"),
            "has_build": package.get("has_build", False),
            "has_lint": package.get("has_lint", False),
            "has_typecheck": package.get("has_typecheck", False),
            "has_test": package.get("has_test", False),
            "has_visual_test": package.get("has_visual_test", False),
            "has_gui_parity_test": package.get("has_gui_parity_test", False),
            "has_playwright_dependency": package.get("has_playwright_dependency", False),
        })

    def write_csv(name: str, rows: list[dict]):
        path = OUT_DIR / name
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    write_csv("repositories.csv", repo_rows)
    write_csv("files.csv", file_rows)
    write_csv("surfaces.csv", route_rows)
    write_csv("states.csv", state_rows)

    summary = {
        "schema_version": "1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_label": scope["snapshot_label"],
        "canonical_product": scope["canonical_product"],
        "repositories_expected": len(scope["repositories"]),
        "repositories_censused": len(repo_rows),
        "snapshot_mismatches": fatal,
        "totals": {
            "source_files": sum(r["source_files"] for r in repo_rows),
            "visual_files": sum(r["visual_files"] for r in repo_rows),
            "test_files": sum(r["tests"] for r in repo_rows),
            "routes": sum(r["routes"] for r in repo_rows),
            "workbench_modules": sum(r["workbench_modules"] for r in repo_rows),
            "static_interaction_handler_occurrences": sum(r["static_interaction_handler_occurrences"] for r in repo_rows),
        },
        "coverage": {
            "repo_snapshot_closure": "PASS" if not fatal and len(repo_rows) == len(scope["repositories"]) else "FAIL",
            "file_manifest_generated": True,
            "route_and_module_discovery_generated": True,
            "state_discovery_generated": True,
            "runtime_route_reachability": "OPEN",
            "behavioral_state_coverage": "OPEN",
            "workflow_coverage": "OPEN",
            "screenshot_coverage": "OPEN",
            "accessibility_runtime_coverage": "OPEN",
        },
        "repositories": repo_rows,
        "certification": "OPEN",
        "certification_reason": "Static census cannot certify runtime reachability, workflow/state behavior, accessibility, or screenshot completeness.",
    }
    (OUT_DIR / "census.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 2 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
