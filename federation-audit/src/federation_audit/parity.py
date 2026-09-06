from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .strict_scan import strict_scan_repository

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
ROUTE_RE = re.compile(r"<Route\b[^>]*\bpath\s*=\s*[\"']([^\"']+)[\"']", re.S)
NAV_RE = re.compile(
    r"(?:\bto|\bhref|\bpath)\s*=\s*(?:[\"']([^\"']+)[\"']|\{[\"']([^\"']+)[\"']\})"
    r"|\bpath\s*:\s*[\"']([^\"']+)[\"']",
    re.S,
)
RISKY_LABEL_RE = re.compile(
    r"[\"']([^\"']*\b(?:CERTIFIED|CURRENT|LIVE|CONFIRMED|AUTHORITATIVE)\b[^\"']*)[\"']",
    re.I,
)


@dataclass(frozen=True)
class Finding:
    code: str
    repository: str
    dimension: str
    subject: str
    detail: str
    evidence: tuple[str, ...] = ()
    severity: str = "P1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "repository": self.repository,
            "dimension": self.dimension,
            "subject": self.subject,
            "detail": self.detail,
            "evidence": list(self.evidence),
            "severity": self.severity,
        }


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _iter_files(root: Path, configured: Iterable[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for raw in configured:
        path = root / raw
        if path.is_file():
            seen.add(path)
        elif path.is_dir():
            for item in path.rglob("*"):
                if item.is_file() and item.suffix.lower() in {".js", ".jsx", ".ts", ".tsx", ".vue"}:
                    seen.add(item)
    yield from sorted(seen)


def _git_head(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _normal_route(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    method, sep, path = value.partition(" ")
    if sep and method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        return f"{method.upper()} {path.rstrip('/') or '/'}"
    return value.rstrip("/") or "/"


def _existing_capability_bindings(root: Path, contract: dict[str, Any]) -> tuple[set[str], set[str], list[str]]:
    backend: set[str] = set()
    gui: set[str] = set()
    gaps: list[str] = []
    for rel in contract.get("discovery", {}).get("existing_gui_capability_manifests", []):
        path = root / rel
        if not path.is_file():
            gaps.append(f"missing-existing-gui-manifest:{rel}")
            continue
        try:
            manifest = _load(path)
        except (OSError, json.JSONDecodeError) as exc:
            gaps.append(f"invalid-existing-gui-manifest:{rel}:{type(exc).__name__}")
            continue
        for capability in manifest.get("capabilities", []):
            if capability.get("status") not in {None, "active", "staged"}:
                continue
            for endpoint in capability.get("backend", {}).get("endpoints", []):
                if isinstance(endpoint, str):
                    backend.add(_normal_route(endpoint))
            for route in capability.get("frontend", {}).get("routes", []):
                if isinstance(route, str):
                    gui.add(_normal_route(route))
    return backend, gui, gaps


def _gui_routes(root: Path, contract: dict[str, Any]) -> tuple[set[str], dict[str, str]]:
    routes: set[str] = set()
    evidence: dict[str, str] = {}
    for rel in contract["discovery"].get("route_files", []):
        path = root / rel
        if not path.is_file():
            continue
        source = _read(path)
        for match in ROUTE_RE.finditer(source):
            route = _normal_route(match.group(1))
            routes.add(route)
            evidence.setdefault(route, f"{rel}:{source[:match.start()].count(chr(10)) + 1}")
    return routes, evidence


def _navigation_targets(root: Path, contract: dict[str, Any]) -> set[str]:
    targets: set[str] = set()
    for rel in contract["discovery"].get("navigation_files", []):
        path = root / rel
        if not path.is_file():
            continue
        source = _read(path)
        for match in NAV_RE.finditer(source):
            value = next((group for group in match.groups() if group), None)
            if value and value.startswith("/"):
                targets.add(_normal_route(value))
    return targets


def _allowlisted(value: str, entries: list[dict[str, Any]]) -> bool:
    for entry in entries:
        try:
            if re.search(entry["pattern"], value):
                return True
        except re.error:
            continue
    return False


def _route_window(root: Path, route: Any) -> str:
    path = root / route.source
    if not path.is_file():
        return ""
    lines = _read(path).splitlines()
    start = max(0, route.line - 3)
    end = min(len(lines), route.line + 40)
    return "\n".join(lines[start:end])


def _guarded(root: Path, route: Any, patterns: list[str]) -> bool:
    window = _route_window(root, route)
    for pattern in patterns:
        try:
            if re.search(pattern, window):
                return True
        except re.error:
            continue
    return False


def _provenance_text(root: Path, contract: dict[str, Any]) -> str:
    files = contract.get("provenance", {}).get("frontend_evidence_files", [])
    return "\n".join(_read(root / rel) for rel in files if (root / rel).is_file())


def _token_variants(field: str) -> tuple[str, ...]:
    parts = field.split("_")
    camel = parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])
    return field, camel, field.replace("_", "-")


def _risky_claims(root: Path, contract: dict[str, Any]) -> list[tuple[str, str, int]]:
    claims: list[tuple[str, str, int]] = []
    frontend = contract["discovery"].get("frontend_roots", [])
    for path in _iter_files(root, frontend):
        rel = path.relative_to(root).as_posix()
        source = _read(path)
        for match in RISKY_LABEL_RE.finditer(source):
            text = " ".join(match.group(1).split())[:180]
            claims.append((text, rel, source[:match.start()].count("\n") + 1))
            if len(claims) >= 250:
                return claims
    return claims


def _claim_declared(text: str, contract: dict[str, Any]) -> bool:
    for claim in contract.get("state_claims", []):
        try:
            if re.search(claim["frontend_pattern"], text, flags=re.I):
                return True
        except re.error:
            continue
    return False


def _authority_findings(repo_id: str, contract: dict[str, Any], matrix: dict[str, Any]) -> list[Finding]:
    expected = matrix.get("repositories", {}).get(repo_id)
    if not expected:
        return [Finding("AUTHORITY_UNDECLARED", repo_id, "authority", repo_id, "Repository has no federation authority row.", severity="P0")]
    mapping = {
        "semantic_authority": "semantic_authority",
        "mutation_authority": "mutation_authority",
        "identity_authority": "identity_authority",
        "geometry_authority": "geometry_authority",
        "provenance_authority": "provenance_authority",
    }
    findings: list[Finding] = []
    for field, expected_field in mapping.items():
        actual = contract.get("authority", {}).get(field)
        target = expected.get(expected_field)
        if actual != target:
            findings.append(
                Finding(
                    "AUTHORITY_DRIFT",
                    repo_id,
                    "authority",
                    field,
                    f"contract={actual!r} federation_matrix={target!r}",
                    ("federation-audit/manifests/gui-backend-authority-matrix.json",),
                    "P0",
                )
            )
    return findings


def audit_repository(
    repo_root: Path,
    repo: dict[str, Any],
    contract: dict[str, Any],
    *,
    contract_source: str,
    authority_matrix: dict[str, Any],
) -> dict[str, Any]:
    repo_id = repo["id"]
    findings: list[Finding] = []
    expected_sha = repo["commit"]

    if contract.get("repository", "").lower() != repo["repository"].lower():
        findings.append(Finding("CONTRACT_REPOSITORY_MISMATCH", repo_id, "authority", "repository", "Contract repository does not match audit manifest.", severity="P0"))
    if contract.get("source_commit") != expected_sha:
        findings.append(Finding("CONTRACT_SHA_DRIFT", repo_id, "state", "source_commit", f"contract={contract.get('source_commit')} manifest={expected_sha}", severity="P0"))
    actual_sha = _git_head(repo_root)
    if actual_sha and actual_sha != expected_sha:
        findings.append(Finding("WORKSPACE_SHA_DRIFT", repo_id, "state", "HEAD", f"workspace={actual_sha} manifest={expected_sha}", severity="P0"))
    if contract_source != "repository":
        findings.append(Finding("CONTRACT_NOT_LOCAL", repo_id, "authority", ".federation/gui_backend_contract.json", "Parity contract is using control-plane fallback rather than a repository-local contract.", severity="P1"))

    traces, index = strict_scan_repository(repo_root, repo)
    existing_backend, existing_gui, manifest_gaps = _existing_capability_bindings(repo_root, contract)
    for gap in manifest_gaps:
        findings.append(Finding("CAPABILITY_MANIFEST_GAP", repo_id, "executability", gap, gap))

    resolved_gui_targets = {
        _normal_route(str(trace.observations.get("resolved_target")))
        for trace in traces
        if trace.surface.get("kind") == "gui-control" and trace.observations.get("resolved_target")
    }
    accounted_backend = existing_backend | resolved_gui_targets
    backend_allow = contract.get("backend_only_allowlist", [])
    for route in index.routes:
        key = _normal_route(f"{route.method} {route.path}")
        if key not in accounted_backend and not _allowlisted(key, backend_allow):
            findings.append(
                Finding(
                    "UNCLASSIFIED_BACKEND",
                    repo_id,
                    "executability",
                    key,
                    "Backend route is neither GUI-bound nor explicitly classified as intentional backend-only.",
                    (f"{route.source}:{route.line}",),
                    "P1",
                )
            )

    bad_gui = {"UI_NO_OP", "TARGET_MISSING", "CONTRACT_MISMATCH", "PARTIALLY_WIRED", "PRECONDITION_UNDECLARED", "RUNTIME_FAILURE"}
    gui_allow = contract.get("gui_only_allowlist", [])
    for trace in traces:
        if trace.surface.get("kind") != "gui-control" or trace.classification not in bad_gui:
            continue
        subject = f"{trace.surface.get('source')}:{trace.surface.get('line')}:{trace.surface.get('label')}"
        if _allowlisted(subject, gui_allow):
            continue
        findings.append(
            Finding(
                "GUI_ONLY_UNJUSTIFIED",
                repo_id,
                "executability",
                subject,
                f"GUI control classified {trace.classification}.",
                tuple(e.value for e in trace.evidence[:5]),
                "P0" if trace.classification in {"TARGET_MISSING", "CONTRACT_MISMATCH"} else "P1",
            )
        )

    gui_routes, route_evidence = _gui_routes(repo_root, contract)
    nav_targets = _navigation_targets(repo_root, contract)
    for route in sorted(gui_routes):
        if route in {"/", "*"} or route.startswith("*"):
            continue
        if route in existing_gui or route in nav_targets or _allowlisted(route, gui_allow):
            continue
        findings.append(
            Finding(
                "UNCLASSIFIED_GUI_ROUTE",
                repo_id,
                "executability",
                route,
                "GUI route is not mapped by the reviewed capability contract and has no declared navigation/presentation-only classification.",
                (route_evidence.get(route, "route-file"),),
                "P2",
            )
        )

    public_mutations = {_normal_route(v) for v in contract.get("auth", {}).get("explicit_public_mutations", [])}
    guard_patterns = contract.get("auth", {}).get("guard_patterns", [])
    for route in index.routes:
        if route.method not in MUTATING:
            continue
        key = _normal_route(f"{route.method} {route.path}")
        if key in public_mutations:
            continue
        if not _guarded(repo_root, route, guard_patterns):
            findings.append(
                Finding(
                    "AUTH_DRIFT_UNGUARDED_MUTATION",
                    repo_id,
                    "auth",
                    key,
                    "Mutating route has no configured guard pattern in its decorator/handler window and is not explicitly public.",
                    (f"{route.source}:{route.line}",),
                    "P0",
                )
            )

    provenance_text = _provenance_text(repo_root, contract).lower()
    for field in contract.get("provenance", {}).get("required_fields_when_available", []):
        if not any(variant.lower() in provenance_text for variant in _token_variants(field)):
            findings.append(
                Finding(
                    "PROVENANCE_GAP",
                    repo_id,
                    "provenance",
                    field,
                    "Required provenance field is not represented in the configured GUI provenance evidence files.",
                    tuple(contract.get("provenance", {}).get("frontend_evidence_files", [])),
                    "P2",
                )
            )

    for text, rel, line in _risky_claims(repo_root, contract):
        if not _claim_declared(text, contract):
            findings.append(
                Finding(
                    "UNDECLARED_STATE_CLAIM",
                    repo_id,
                    "state",
                    text,
                    "High-strength GUI state language has no declared backend predicate.",
                    (f"{rel}:{line}",),
                    "P1",
                )
            )

    devices = contract.get("devices", {})
    if devices.get("native_ios"):
        evidence_files = devices.get("native_evidence_files", [])
        if not evidence_files or not any((repo_root / rel).is_file() for rel in evidence_files):
            findings.append(Finding("DEVICE_DRIFT_NATIVE_UNEVIDENCED", repo_id, "device", "native_ios", "Contract claims native iOS but no configured native evidence file exists.", severity="P1"))

    findings.extend(_authority_findings(repo_id, contract, authority_matrix))

    runtime_evidence = contract.get("runtime_evidence", {})
    for dimension in ("data", "identity", "geometry", "device"):
        entry = runtime_evidence.get(dimension, {}) if isinstance(runtime_evidence, dict) else {}
        if entry.get("state") != "PASS":
            findings.append(
                Finding(
                    "RUNTIME_DIMENSION_OPEN",
                    repo_id,
                    dimension,
                    dimension,
                    "Dimension requires an explicit runtime PASS receipt; static wiring is insufficient.",
                    tuple(entry.get("evidence", [])) if isinstance(entry, dict) else (),
                    "P1",
                )
            )

    dimensions = contract.get("policy", {}).get("dimensions", [])
    by_dimension: dict[str, str] = {}
    for dimension in dimensions:
        dimension_findings = [finding for finding in findings if finding.dimension == dimension]
        by_dimension[dimension] = "PASS" if not dimension_findings else "BLOCKED" if any(f.severity == "P0" for f in dimension_findings) else "OPEN"

    material = [finding for finding in findings if finding.severity in {"P0", "P1", "P2"}]
    state = "BLOCKED" if any(f.severity == "P0" for f in material) else "OPEN" if material else "PASS"
    return {
        "repository": repo_id,
        "repository_full_name": repo["repository"],
        "source_commit": expected_sha,
        "contract_source": contract_source,
        "state": state,
        "dimensions": by_dimension,
        "inventory": {
            "backend_routes": len(index.routes),
            "gui_routes": len(gui_routes),
            "strict_traces": len(traces),
            "reviewed_backend_bindings": len(existing_backend),
            "reviewed_gui_bindings": len(existing_gui),
            "resolved_gui_api_targets": len(resolved_gui_targets),
            "resolver_gaps": len(index.gaps),
        },
        "resolver_gaps": index.gaps,
        "findings": [finding.to_dict() for finding in findings],
        "material_residue": len(material),
    }


def certify_federation(
    workspace_root: Path,
    manifest: dict[str, Any],
    *,
    authority_matrix: dict[str, Any],
    fallback_contract_root: Path | None = None,
) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    workspace_gaps: list[str] = []
    for repo in manifest["repositories"]:
        root = workspace_root / repo["workspace_directory"]
        if not root.is_dir():
            workspace_gaps.append(repo["workspace_directory"])
            continue
        local = root / ".federation" / "gui_backend_contract.json"
        fallback = fallback_contract_root / f"{repo['id']}.json" if fallback_contract_root else None
        if local.is_file():
            contract = _load(local)
            source = "repository"
        elif fallback and fallback.is_file():
            contract = _load(fallback)
            source = "control-plane-fallback"
        else:
            reports.append(
                {
                    "repository": repo["id"],
                    "repository_full_name": repo["repository"],
                    "source_commit": repo["commit"],
                    "contract_source": "missing",
                    "state": "BLOCKED",
                    "dimensions": {},
                    "inventory": {},
                    "resolver_gaps": [],
                    "findings": [
                        Finding(
                            "MISSING_GUI_BACKEND_CONTRACT",
                            repo["id"],
                            "authority",
                            ".federation/gui_backend_contract.json",
                            "Repository has no GUI/backend parity contract.",
                            severity="P0",
                        ).to_dict()
                    ],
                    "material_residue": 1,
                }
            )
            continue
        reports.append(
            audit_repository(
                root,
                repo,
                contract,
                contract_source=source,
                authority_matrix=authority_matrix,
            )
        )

    residue = sum(int(report.get("material_residue", 0)) for report in reports) + len(workspace_gaps)
    blocked = bool(workspace_gaps) or any(report.get("state") == "BLOCKED" for report in reports)
    certified = not blocked and residue == 0 and len(reports) == len(manifest["repositories"])
    return {
        "schema_version": "federation.gui-backend-parity-report/1.0",
        "certified": certified,
        "state": "PASS" if certified else "BLOCKED" if blocked else "OPEN",
        "repositories": reports,
        "workspace_gaps": workspace_gaps,
        "summary": {
            "repositories_expected": len(manifest["repositories"]),
            "repositories_audited": len(reports),
            "material_residue": residue,
            "p0": sum(1 for r in reports for f in r.get("findings", []) if f.get("severity") == "P0"),
            "p1": sum(1 for r in reports for f in r.get("findings", []) if f.get("severity") == "P1"),
            "p2": sum(1 for r in reports for f in r.get("findings", []) if f.get("severity") == "P2"),
        },
    }
