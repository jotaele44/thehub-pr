from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .parity import certify_federation as _legacy_certify_federation

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _git(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    try:
        subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, descendant],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _load_contract(
    root: Path,
    repo_id: str,
    fallback_contract_root: Path | None,
) -> tuple[dict[str, Any] | None, str]:
    local = root / ".federation" / "gui_backend_contract.json"
    fallback = fallback_contract_root / f"{repo_id}.json" if fallback_contract_root else None
    if local.is_file():
        return json.loads(local.read_text(encoding="utf-8")), "repository"
    if fallback and fallback.is_file():
        return json.loads(fallback.read_text(encoding="utf-8")), "control-plane-fallback"
    return None, "missing"


def _watched_paths(contract: dict[str, Any]) -> list[str]:
    discovery = contract.get("discovery", {})
    raw = [
        *discovery.get("backend_roots", []),
        *discovery.get("frontend_roots", []),
        *discovery.get("route_files", []),
        *discovery.get("navigation_files", []),
        *discovery.get("existing_gui_capability_manifests", []),
    ]
    return sorted({str(value).strip().rstrip("/") for value in raw if str(value).strip()})


def _covered(name: str, watched: list[str]) -> bool:
    return any(name == raw or name.startswith(raw + "/") for raw in watched)


def _changed_watched(root: Path, source: str, head: str, contract: dict[str, Any]) -> list[str]:
    changed = _git(root, "diff", "--name-only", f"{source}..{head}")
    if changed is None:
        return ["<unable-to-diff>"]
    watched = _watched_paths(contract)
    return sorted(name for name in changed.splitlines() if _covered(name, watched))


def contract_commit_relation(
    root: Path,
    contract: dict[str, Any],
    expected_head: str,
) -> dict[str, Any]:
    source = str(contract.get("source_commit", ""))
    workspace_head = _git(root, "rev-parse", "HEAD")
    receipt: dict[str, Any] = {
        "source_commit": source,
        "manifest_commit": expected_head,
        "workspace_head": workspace_head,
        "relation": "UNKNOWN",
        "changed_watched_paths": [],
    }

    if workspace_head != expected_head:
        receipt["relation"] = "WORKSPACE_MISMATCH"
        return receipt
    if not _SHA_RE.fullmatch(source):
        receipt["relation"] = "INVALID_SOURCE_COMMIT"
        return receipt
    if _git(root, "cat-file", "-e", source + "^{commit}") is None:
        receipt["relation"] = "SOURCE_COMMIT_MISSING"
        return receipt
    if source == expected_head:
        receipt["relation"] = "EXACT"
        return receipt
    if not _is_ancestor(root, source, expected_head):
        receipt["relation"] = "NOT_ANCESTOR"
        return receipt

    changed = _changed_watched(root, source, expected_head, contract)
    receipt["changed_watched_paths"] = changed
    receipt["relation"] = "ANCESTOR_CLEAN" if not changed else "ANCESTOR_STALE"
    return receipt


def _recompute_repository(report: dict[str, Any], dimensions: list[str]) -> None:
    findings = report.get("findings", [])
    by_dimension: dict[str, str] = {}
    for dimension in dimensions:
        relevant = [finding for finding in findings if finding.get("dimension") == dimension]
        by_dimension[dimension] = (
            "PASS"
            if not relevant
            else "BLOCKED"
            if any(finding.get("severity") == "P0" for finding in relevant)
            else "OPEN"
        )
    material = [finding for finding in findings if finding.get("severity") in {"P0", "P1", "P2"}]
    report["dimensions"] = by_dimension
    report["material_residue"] = len(material)
    report["state"] = (
        "BLOCKED"
        if any(finding.get("severity") == "P0" for finding in material)
        else "OPEN"
        if material
        else "PASS"
    )


def _recompute_federation(result: dict[str, Any], expected_count: int) -> None:
    reports = result.get("repositories", [])
    gaps = result.get("workspace_gaps", [])
    residue = sum(int(report.get("material_residue", 0)) for report in reports) + len(gaps)
    blocked = bool(gaps) or any(report.get("state") == "BLOCKED" for report in reports)
    certified = not blocked and residue == 0 and len(reports) == expected_count
    result["certified"] = certified
    result["state"] = "PASS" if certified else "BLOCKED" if blocked else "OPEN"
    result["summary"] = {
        "repositories_expected": expected_count,
        "repositories_audited": len(reports),
        "material_residue": residue,
        "p0": sum(1 for r in reports for f in r.get("findings", []) if f.get("severity") == "P0"),
        "p1": sum(1 for r in reports for f in r.get("findings", []) if f.get("severity") == "P1"),
        "p2": sum(1 for r in reports for f in r.get("findings", []) if f.get("severity") == "P2"),
    }


def certify_federation(
    workspace_root: Path,
    manifest: dict[str, Any],
    *,
    authority_matrix: dict[str, Any],
    fallback_contract_root: Path | None = None,
) -> dict[str, Any]:
    """Certify parity with contract-source ancestry instead of impossible self-SHA equality.

    A repository contract may identify the last audited source commit rather than the
    commit that contains the contract file itself. It is accepted only when that source
    commit is an ancestor of the exact manifest/workspace HEAD and no configured audited
    backend/frontend/capability path changed between the two. Contract/workflow-only
    commits therefore remain certifiable without weakening stale-source detection.
    """
    result = _legacy_certify_federation(
        workspace_root,
        manifest,
        authority_matrix=authority_matrix,
        fallback_contract_root=fallback_contract_root,
    )
    reports = {report.get("repository"): report for report in result.get("repositories", [])}

    for repo in manifest["repositories"]:
        report = reports.get(repo["id"])
        if not report:
            continue
        root = workspace_root / repo["workspace_directory"]
        contract, source_kind = _load_contract(root, repo["id"], fallback_contract_root)
        if not contract:
            continue

        relation = contract_commit_relation(root, contract, repo["commit"])
        relation["contract_source"] = source_kind
        report["contract_commit_relation"] = relation
        findings = report.get("findings", [])

        if relation["relation"] in {"EXACT", "ANCESTOR_CLEAN"}:
            findings[:] = [finding for finding in findings if finding.get("code") != "CONTRACT_SHA_DRIFT"]
        elif relation["relation"] == "ANCESTOR_STALE":
            findings[:] = [finding for finding in findings if finding.get("code") != "CONTRACT_SHA_DRIFT"]
            findings.append(
                {
                    "code": "CONTRACT_STALE_AFTER_SOURCE",
                    "repository": repo["id"],
                    "dimension": "state",
                    "subject": "source_commit",
                    "detail": "Audited backend/frontend/capability paths changed after the contract source_commit.",
                    "evidence": relation["changed_watched_paths"],
                    "severity": "P0",
                }
            )
        elif relation["relation"] not in {"WORKSPACE_MISMATCH"}:
            findings[:] = [finding for finding in findings if finding.get("code") != "CONTRACT_SHA_DRIFT"]
            findings.append(
                {
                    "code": "CONTRACT_SOURCE_ANCESTRY_INVALID",
                    "repository": repo["id"],
                    "dimension": "state",
                    "subject": "source_commit",
                    "detail": f"Contract source relation is {relation['relation']}; exact source ancestry cannot be proven.",
                    "evidence": [
                        f"source={relation['source_commit']}",
                        f"manifest={relation['manifest_commit']}",
                        f"workspace={relation['workspace_head']}",
                    ],
                    "severity": "P0",
                }
            )

        _recompute_repository(report, list(contract.get("policy", {}).get("dimensions", [])))

    _recompute_federation(result, len(manifest["repositories"]))
    result["contract_commit_policy"] = "source_commit_must_be_exact_or_clean_ancestor_of_exact_manifest_head"
    return result
