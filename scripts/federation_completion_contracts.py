#!/usr/bin/env python3
"""Fail-closed federation contract sidecar.

This audit complements ``federation_completion_gate.py``. The existing gate
continues to own current-base PR/merge-result CI classification. This sidecar
owns federation contract currency and acquisition invariants that are not
proven by a green PR check suite alone.

Hard rules:
* inspect hard dependency manifests and explicitly configured executable
  dependency surfaces, never repository-wide text hits;
* desktop transport and root/runtime transport are classified separately;
* immutable TheHub provenance means an explicit 40-hex commit SHA;
* PEP 508 git+ bindings and uv ``[tool.uv.sources]`` git+rev bindings are both
  executable dependency evidence;
* template drift against an old pin is not canonical-template currency;
* if a desktop job already materializes TheHub into PRII_TOOLING_ROOT, a
  dependency manifest must not trigger another git checkout of TheHub;
* failure stage and failure attribution are orthogonal dimensions;
* unattributed failures, stale generated artifacts and unclassified GUI
  candidates are fail-closed states.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API = "https://api.github.com"
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
TEMPLATE_REF_RE = re.compile(r"PRII_TEMPLATE_REF:\s*([0-9a-f]{40})")
GIT_THEHUB_RE = re.compile(
    r"git\+https://github\.com/jotaele44/thehub-pr\.git@([0-9a-f]{40})"
)
ARCHIVE_THEHUB_RE = re.compile(
    r"https://github\.com/jotaele44/thehub-pr/archive/([0-9a-f]{40})\.zip"
)
UV_REV_RE = re.compile(r"rev\s*=\s*[\"']([0-9a-f]{40})[\"']")
FAILURE_STATES = {"BASE_FAILURE", "PR_FAILURE", "TRANSIENT", "UNRESOLVED"}
FAILURE_STAGES = {
    "PRE_RUNNER",
    "SETUP",
    "DEPENDENCY_INSTALL",
    "TEST_EXECUTION",
    "BUILD",
    "PACKAGING",
    "POST_JOB",
    "UNKNOWN",
}
GUI_STATES = {"BOUND", "INTERNAL", "EXEMPT", "UNCLASSIFIED"}


def request_json(url: str, token: str) -> Any:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("User-Agent", "thehub-federation-completion-contracts")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"GitHub request failed for {url}: {exc}") from exc


def fetch_text(repo_full: str, path: str, ref: str, token: str) -> str:
    owner, repo = repo_full.split("/", 1)
    quoted = urllib.parse.quote(path, safe="/")
    doc = request_json(f"{API}/repos/{owner}/{repo}/contents/{quoted}?ref={ref}", token)
    if doc.get("encoding") != "base64" or not isinstance(doc.get("content"), str):
        raise RuntimeError(f"{repo_full}:{path}: expected base64 GitHub contents response")
    return base64.b64decode(doc["content"]).decode("utf-8")


def main_sha(repo_full: str, token: str) -> str:
    owner, repo = repo_full.split("/", 1)
    sha = str(request_json(f"{API}/repos/{owner}/{repo}/commits/main", token).get("sha", ""))
    if not FULL_SHA_RE.fullmatch(sha):
        raise RuntimeError(f"{repo_full}: invalid main SHA {sha!r}")
    return sha


def uv_thehub_source_shas(text: str) -> list[str]:
    """Return immutable revs from uv source lines that bind to TheHub git."""
    shas: list[str] = []
    for line in text.splitlines():
        if "thehub-pr.git" not in line or "git" not in line:
            continue
        match = UV_REV_RE.search(line)
        if match:
            shas.append(match.group(1))
    return shas


def manifest_transport(text: str) -> dict[str, Any]:
    pep508_git_shas = GIT_THEHUB_RE.findall(text)
    uv_git_shas = uv_thehub_source_shas(text)
    git_shas = [*pep508_git_shas, *uv_git_shas]
    archive_shas = ARCHIVE_THEHUB_RE.findall(text)
    return {
        "git_thehub_count": len(git_shas),
        "pep508_git_thehub_count": len(pep508_git_shas),
        "uv_git_thehub_count": len(uv_git_shas),
        "archive_thehub_count": len(archive_shas),
        "git_thehub_shas": sorted(set(git_shas)),
        "archive_thehub_shas": sorted(set(archive_shas)),
        "immutable_sha_provenance": all(
            FULL_SHA_RE.fullmatch(sha) for sha in [*git_shas, *archive_shas]
        ),
    }


def validate_generated_artifact_record(record: dict[str, Any]) -> list[str]:
    """Validate producer-emitted byte-regeneration evidence."""
    reasons: list[str] = []
    if record.get("state") != "PASS":
        reasons.append("GENERATED_ARTIFACT_NOT_PASS")
    if record.get("byte_identical") is not True:
        reasons.append("GENERATED_ARTIFACT_STALE")
    regenerated = str(record.get("regenerated_sha256") or "")
    committed = str(record.get("committed_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", regenerated):
        reasons.append("INVALID_REGENERATED_SHA256")
    if not re.fullmatch(r"[0-9a-f]{64}", committed):
        reasons.append("INVALID_COMMITTED_SHA256")
    if regenerated and committed and regenerated != committed:
        reasons.append("GENERATED_ARTIFACT_HASH_MISMATCH")
    return reasons


def validate_gui_candidate_record(record: dict[str, Any]) -> list[str]:
    """Validate arithmetic closure for producer-emitted GUI discovery evidence."""
    reasons: list[str] = []
    total = int(record.get("candidate_count", -1))
    counts = {
        state: int(record.get(f"{state.lower()}_count", 0)) for state in GUI_STATES
    }
    if total < 0 or total != sum(counts.values()):
        reasons.append("GUI_CANDIDATE_ARITHMETIC_NOT_CLOSED")
    if counts["UNCLASSIFIED"] != 0:
        reasons.append(f"GUI_UNCLASSIFIED_CANDIDATES:{counts['UNCLASSIFIED']}")
    return reasons


def classify_failure(
    *,
    same_signature_on_baseline: bool,
    baseline_green: bool,
    causal_binding_to_pr_delta: bool,
    same_sha_rerun_passed_without_mutation: bool,
    transient_signature_supported: bool,
) -> str:
    """Conservative failure attribution; uncertainty remains UNRESOLVED."""
    if same_signature_on_baseline:
        return "BASE_FAILURE"
    if baseline_green and causal_binding_to_pr_delta:
        return "PR_FAILURE"
    if same_sha_rerun_passed_without_mutation and transient_signature_supported:
        return "TRANSIENT"
    return "UNRESOLVED"


def failure_stage(job: dict[str, Any]) -> str:
    """Locate where a job stopped without claiming who owns the failure."""
    steps = job.get("steps") or []
    runner_id = int(job.get("runner_id") or 0)
    if job.get("conclusion") == "failure" and not steps and runner_id == 0:
        return "PRE_RUNNER"
    failed = [step for step in steps if step.get("conclusion") == "failure"]
    if not failed:
        return "UNKNOWN"
    name = str(failed[0].get("name") or "").lower()
    if any(word in name for word in ("setup", "checkout", "set up", "initialize")):
        return "SETUP"
    if any(word in name for word in ("install", "dependency", "pip", "uv sync", "npm ci")):
        return "DEPENDENCY_INSTALL"
    if any(word in name for word in ("test", "pytest", "lint", "ruff", "mypy", "validate")):
        return "TEST_EXECUTION"
    if any(word in name for word in ("build", "freeze", "compile")):
        return "BUILD"
    if any(word in name for word in ("package", "artifact", "dmg", "zip")):
        return "PACKAGING"
    if name.startswith("post ") or "cleanup" in name:
        return "POST_JOB"
    return "UNKNOWN"


def failure_evidence(job: dict[str, Any]) -> dict[str, Any]:
    """Normalize a diagnostic signature without converting stage into cause."""
    steps = job.get("steps") or []
    labels = sorted(str(label) for label in (job.get("labels") or []))
    return {
        "exact_sha": str(job.get("head_sha") or ""),
        "workflow_run_id": job.get("run_id"),
        "job_id": job.get("id"),
        "run_attempt": job.get("run_attempt"),
        "status": job.get("status"),
        "conclusion": job.get("conclusion"),
        "failure_stage": failure_stage(job),
        "step_count": len(steps),
        "runner_id": int(job.get("runner_id") or 0),
        "runner_name": str(job.get("runner_name") or ""),
        "runner_labels": labels,
    }


def same_failure_signature(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Compare diagnostic shape, not mutable IDs or workflow/job names."""
    keys = (
        "conclusion",
        "failure_stage",
        "step_count",
        "runner_id",
        "runner_name",
        "runner_labels",
    )
    return all(left.get(key) == right.get(key) for key in keys)


def audit_golden_fixture(cfg: dict[str, Any], token: str) -> dict[str, Any]:
    fixture = cfg["golden_windows_fixture"]
    repo_full = fixture["repository"]
    owner, repo = repo_full.split("/", 1)
    commit = fixture["commit"]
    runs = request_json(
        f"{API}/repos/{owner}/{repo}/actions/runs?head_sha={commit}&per_page=100", token
    ).get("workflow_runs", [])
    matching = [run for run in runs if run.get("name") == fixture["workflow"]]
    if not matching:
        return {**fixture, "state": "FAIL", "reasons": ["GOLDEN_WORKFLOW_NOT_FOUND"]}
    run = sorted(matching, key=lambda item: int(item.get("id", 0)), reverse=True)[0]
    jobs = request_json(run["jobs_url"], token).get("jobs", [])
    observed = {job.get("name"): job.get("conclusion") for job in jobs}
    missing = [name for name in fixture["required_jobs"] if name not in observed]
    bad = [name for name in fixture["required_jobs"] if observed.get(name) != "success"]
    reasons = [*(f"GOLDEN_JOB_MISSING:{name}" for name in missing)]
    reasons.extend(f"GOLDEN_JOB_NOT_SUCCESS:{name}:{observed.get(name)}" for name in bad)
    return {
        **fixture,
        "run_id": run.get("id"),
        "observed_jobs": observed,
        "state": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
    }


def _audit_transport_paths(
    repo_full: str,
    paths: list[str],
    observed_main: str,
    token: str,
    *,
    reason_prefix: str,
    reasons: list[str],
) -> tuple[list[dict[str, Any]], int, int]:
    findings: list[dict[str, Any]] = []
    git_count = 0
    archive_count = 0
    for path in paths:
        try:
            finding = manifest_transport(fetch_text(repo_full, path, observed_main, token))
            finding["path"] = path
            findings.append(finding)
            git_count += finding["git_thehub_count"]
            archive_count += finding["archive_thehub_count"]
            if not finding["immutable_sha_provenance"]:
                reasons.append(f"{reason_prefix}_NONIMMUTABLE_PROVENANCE:{path}")
        except Exception as exc:
            reasons.append(f"{reason_prefix}_AUDIT_ERROR:{path}:{exc}")
    return findings, git_count, archive_count


def audit_repository(
    repo_full: str, spec: dict[str, Any], approved_template_ref: str, token: str
) -> dict[str, Any]:
    observed_main = main_sha(repo_full, token)
    reasons: list[str] = []
    template_ref: str | None = None
    try:
        template_text = fetch_text(repo_full, spec["template_ref_path"], observed_main, token)
        match = TEMPLATE_REF_RE.search(template_text)
        if not match:
            reasons.append("TEMPLATE_REF_NOT_FOUND")
        else:
            template_ref = match.group(1)
            if template_ref != approved_template_ref:
                reasons.append(f"STALE_CANONICAL_TEMPLATE:{template_ref}->{approved_template_ref}")
    except Exception as exc:
        reasons.append(f"TEMPLATE_REF_AUDIT_ERROR:{exc}")

    desktop_manifests, desktop_git_count, desktop_archive_count = _audit_transport_paths(
        repo_full,
        spec.get("desktop_requirement_manifests", []),
        observed_main,
        token,
        reason_prefix="DESKTOP_MANIFEST",
        reasons=reasons,
    )
    root_manifests, root_git_count, root_archive_count = _audit_transport_paths(
        repo_full,
        spec.get("root_requirement_manifests", []),
        observed_main,
        token,
        reason_prefix="ROOT_MANIFEST",
        reasons=reasons,
    )
    executable_surfaces, executable_git_count, executable_archive_count = _audit_transport_paths(
        repo_full,
        spec.get("executable_dependency_surfaces", []),
        observed_main,
        token,
        reason_prefix="EXECUTABLE_SURFACE",
        reasons=reasons,
    )

    authority = spec.get("desktop_authority")
    if authority == "STANDARD":
        if desktop_git_count:
            reasons.append(f"STANDARD_DESKTOP_GIT_THEHUB:{desktop_git_count}")
        if desktop_archive_count == 0:
            reasons.append("STANDARD_DESKTOP_ARCHIVE_BINDING_MISSING")

    workflow_materializes_thehub = False
    try:
        workflow_text = fetch_text(repo_full, spec["desktop_workflow_path"], observed_main, token)
        workflow_materializes_thehub = (
            "PRII_TOOLING_ROOT" in workflow_text
            and "git clone" in workflow_text
            and "thehub-pr" in workflow_text
        )
    except Exception as exc:
        reasons.append(f"DESKTOP_WORKFLOW_AUDIT_ERROR:{exc}")

    if workflow_materializes_thehub and desktop_git_count:
        reasons.append("MULTIPLE_THEHUB_MATERIALIZATIONS_POSSIBLE")

    # Root/runtime transport is deliberately independent of desktop transport.
    if root_git_count:
        reasons.append(f"ROOT_RUNTIME_GIT_THEHUB:{root_git_count}")
    if executable_git_count:
        reasons.append(f"EXECUTABLE_SURFACE_GIT_THEHUB:{executable_git_count}")

    return {
        "repository": repo_full,
        "observed_main_sha": observed_main,
        "desktop_authority": authority,
        "template_ref": template_ref,
        "approved_canonical_template_ref": approved_template_ref,
        "canonical_template_current": template_ref == approved_template_ref,
        "desktop_manifests": desktop_manifests,
        "root_manifests": root_manifests,
        "executable_dependency_surfaces": executable_surfaces,
        "desktop_git_thehub_dependency_count": desktop_git_count,
        "desktop_archive_thehub_dependency_count": desktop_archive_count,
        "root_git_thehub_dependency_count": root_git_count,
        "root_archive_thehub_dependency_count": root_archive_count,
        "executable_surface_git_thehub_dependency_count": executable_git_count,
        "executable_surface_archive_thehub_dependency_count": executable_archive_count,
        "workflow_materializes_thehub": workflow_materializes_thehub,
        "one_thehub_materialization_contract": not (
            workflow_materializes_thehub and desktop_git_count
        ),
        "state": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="federation/completion-contracts.json")
    parser.add_argument("--out", default="artifacts/federation-completion-contracts.json")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("BLOCKED: GITHUB_TOKEN/GH_TOKEN is required")
        return 2

    cfg = json.loads(Path(args.config).read_text())
    approved = cfg["approved_canonical_template_ref"]
    if not FULL_SHA_RE.fullmatch(approved):
        raise SystemExit("approved_canonical_template_ref must be a 40-character lowercase SHA")

    errors: list[str] = []
    try:
        golden = audit_golden_fixture(cfg, token)
    except Exception as exc:
        golden = {**cfg["golden_windows_fixture"], "state": "FAIL", "reasons": [str(exc)]}
    if golden["state"] != "PASS":
        errors.extend(golden.get("reasons", []))

    rows: list[dict[str, Any]] = []
    for repo_full, spec in cfg["repositories"].items():
        try:
            row = audit_repository(repo_full, spec, approved, token)
        except Exception as exc:
            row = {
                "repository": repo_full,
                "state": "FAIL",
                "reasons": [f"AUDIT_EXCEPTION:{exc}"],
            }
        rows.append(row)
        if row["state"] != "PASS":
            errors.extend(f"{repo_full}:{reason}" for reason in row["reasons"])

    result = {
        "schema_version": 2,
        "scope": "FEDERATION_CONTRACTS_REMOTE_HARD_BINDINGS",
        "certification": "PASS" if not errors else "FAIL",
        "golden_windows_fixture": golden,
        "approved_canonical_template_ref": approved,
        "generated_artifact_contract": cfg["generated_artifact_contract"],
        "gui_candidate_contract": cfg["gui_candidate_contract"],
        "failure_attribution_contract": cfg["failure_attribution_contract"],
        "rows": rows,
        "errors": errors,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"certification": result["certification"], "errors": errors}, indent=2))
    if errors and not args.audit_only:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
