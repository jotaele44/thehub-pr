#!/usr/bin/env python3
"""Fail-closed remote completion audit for the PRII federation.

This gate intentionally does not certify local worktrees, private fixtures, source
exhaustion, or production readiness. It classifies the *remote GitHub* PR surface
using exact-head evidence and emits a machine-readable ledger.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

API = "https://api.github.com"
GQL = "https://api.github.com/graphql"
TERMINAL_SUCCESS = {"success", "neutral", "skipped"}
BLOCK_MARKERS = {
    "EVIDENCE_BLOCKED": "EVIDENCE_BLOCKED",
    "LOCAL_BLOCKED": "LOCAL_BLOCKED",
    "PUBLIC_SOURCE_EXHAUSTION_OPEN": "PUBLIC_SOURCE_EXHAUSTION_OPEN",
    "STACK_REWRITE_REQUIRED": "STACK_REWRITE_REQUIRED",
    "REBASE_AND_RETEST": "REBASE_REQUIRED",
}


@dataclass
class Disposition:
    repository: str
    number: int
    title: str
    head_sha: str
    base_ref: str
    draft: bool
    state: str
    reasons: list[str]
    checks_total: int = 0
    checks_non_success: int = 0
    unresolved_review_threads: int = 0
    overlap_paths: list[str] | None = None


def request_json(url: str, token: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code} for {url}: {detail}") from exc


def paged(url: str, token: str) -> list[Any]:
    out: list[Any] = []
    page = 1
    while True:
        sep = "&" if "?" in url else "?"
        batch = request_json(f"{url}{sep}per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise RuntimeError(f"Expected list from {url}")
        out.extend(batch)
        if len(batch) < 100:
            return out
        page += 1


def graphql(token: str, query: str, variables: dict[str, Any]) -> Any:
    payload = request_json(GQL, token, method="POST", body={"query": query, "variables": variables})
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {payload['errors']}")
    return payload["data"]


def unresolved_threads(owner: str, repo: str, number: int, token: str) -> int:
    query = """
    query($owner:String!, $repo:String!, $number:Int!, $after:String) {
      repository(owner:$owner, name:$repo) {
        pullRequest(number:$number) {
          reviewThreads(first:100, after:$after) {
            nodes { isResolved }
            pageInfo { hasNextPage endCursor }
          }
        }
      }
    }
    """
    count = 0
    after = None
    while True:
        data = graphql(token, query, {"owner": owner, "repo": repo, "number": number, "after": after})
        threads = data["repository"]["pullRequest"]["reviewThreads"]
        count += sum(1 for n in threads["nodes"] if not n["isResolved"])
        if not threads["pageInfo"]["hasNextPage"]:
            return count
        after = threads["pageInfo"]["endCursor"]


def exact_head_checks(owner: str, repo: str, sha: str, token: str) -> tuple[int, int, list[str]]:
    data = request_json(f"{API}/repos/{owner}/{repo}/commits/{sha}/check-runs?per_page=100", token)
    runs = data.get("check_runs", [])
    bad: list[str] = []
    for run in runs:
        conclusion = run.get("conclusion")
        status = run.get("status")
        if status != "completed" or conclusion not in TERMINAL_SUCCESS:
            bad.append(f"{run.get('name')}:{status}/{conclusion}")
    return len(runs), len(bad), bad


def changed_paths(owner: str, repo: str, number: int, token: str) -> set[str]:
    return {f["filename"] for f in paged(f"{API}/repos/{owner}/{repo}/pulls/{number}/files", token)}


def main_overlap(owner: str, repo: str, base_ref: str, head_sha: str, number: int, token: str) -> list[str]:
    # First comparison yields the true merge base for the current PR head/base pair.
    cmp1 = request_json(f"{API}/repos/{owner}/{repo}/compare/{urllib.parse.quote(base_ref, safe='')}...{head_sha}", token)
    merge_base = cmp1["merge_base_commit"]["sha"]
    cmp2 = request_json(f"{API}/repos/{owner}/{repo}/compare/{merge_base}...{urllib.parse.quote(base_ref, safe='')}", token)
    main_paths = {f["filename"] for f in cmp2.get("files", [])}
    return sorted(changed_paths(owner, repo, number, token) & main_paths)


def classify(repo_full: str, pr: dict[str, Any], token: str) -> Disposition:
    owner, repo = repo_full.split("/", 1)
    number = int(pr["number"])
    body = pr.get("body") or ""
    reasons: list[str] = []
    state = "UNRESOLVED"

    if pr.get("draft"):
        reasons.append("DRAFT")
    base_ref = pr["base"]["ref"]
    if base_ref != "main":
        reasons.append(f"STACKED_BASE:{base_ref}")
    for marker, disposition in BLOCK_MARKERS.items():
        if marker in body:
            reasons.append(marker)
            state = disposition

    checks_total, checks_bad, bad_names = exact_head_checks(owner, repo, pr["head"]["sha"], token)
    if checks_total == 0:
        reasons.append("NO_EXACT_HEAD_CHECKS")
    if checks_bad:
        reasons.append("NON_GREEN_EXACT_HEAD_CHECKS:" + ",".join(bad_names[:10]))

    threads = unresolved_threads(owner, repo, number, token)
    if threads:
        reasons.append(f"UNRESOLVED_REVIEW_THREADS:{threads}")

    overlap: list[str] = []
    if base_ref == "main":
        overlap = main_overlap(owner, repo, base_ref, pr["head"]["sha"], number, token)
        if overlap:
            reasons.append(f"CURRENT_MAIN_PATH_OVERLAP:{len(overlap)}")

    if state == "UNRESOLVED":
        if base_ref != "main":
            state = "STACKED"
        elif overlap:
            state = "REBASE_REQUIRED"
        elif pr.get("draft"):
            state = "BLOCKED"
        elif checks_total == 0 or checks_bad or threads:
            state = "BLOCKED"
        else:
            state = "MERGE_READY"

    return Disposition(
        repository=repo_full,
        number=number,
        title=pr.get("title", ""),
        head_sha=pr["head"]["sha"],
        base_ref=base_ref,
        draft=bool(pr.get("draft")),
        state=state,
        reasons=reasons,
        checks_total=checks_total,
        checks_non_success=checks_bad,
        unresolved_review_threads=threads,
        overlap_paths=overlap,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="federation/completion-gate.json")
    ap.add_argument("--out", default="artifacts/federation-completion-ledger.json")
    ap.add_argument("--fail-on-actionable", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("BLOCKED: GITHUB_TOKEN/GH_TOKEN is required", file=sys.stderr)
        return 2

    cfg = json.loads(Path(args.config).read_text())
    rows: list[Disposition] = []
    errors: list[str] = []
    for repo_full in cfg["repositories"]:
        owner, repo = repo_full.split("/", 1)
        try:
            prs = paged(f"{API}/repos/{owner}/{repo}/pulls?state=open", token)
            for pr in prs:
                try:
                    rows.append(classify(repo_full, pr, token))
                except Exception as exc:  # fail closed per PR; preserve denominator
                    errors.append(f"{repo_full}#{pr.get('number')}: {exc}")
                    rows.append(Disposition(repo_full, int(pr.get("number", -1)), pr.get("title", ""), pr.get("head", {}).get("sha", ""), pr.get("base", {}).get("ref", ""), bool(pr.get("draft")), "UNRESOLVED", ["AUDIT_EXCEPTION"]))
        except Exception as exc:
            errors.append(f"{repo_full}: {exc}")

    counts: dict[str, int] = {}
    for row in rows:
        counts[row.state] = counts.get(row.state, 0) + 1
    result = {
        "schema_version": 1,
        "scope": "REMOTE_GITHUB_ONLY",
        "local_worktree_state": "BLOCKED_NOT_OBSERVED",
        "repositories": cfg["repositories"],
        "open_pr_denominator": len(rows),
        "counts": dict(sorted(counts.items())),
        "errors": errors,
        "rows": [asdict(r) for r in rows],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in ("open_pr_denominator", "counts", "errors")}, indent=2))

    if errors:
        return 2
    if args.fail_on_actionable and counts.get("MERGE_READY", 0):
        # A completion claim fails while unexplained actionable integration residue exists.
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
