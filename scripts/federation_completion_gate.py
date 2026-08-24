#!/usr/bin/env python3
"""Fail-closed remote completion audit for the PRII federation.

This gate intentionally does not certify local worktrees, private fixtures, source
exhaustion, or production readiness. It classifies the *remote GitHub* PR surface
using current-base merge-result evidence and emits a machine-readable ledger.
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
ACTIONABLE_STATES = {
    "MERGE_READY",
    "REBASE_REQUIRED",
    "STACK_REWRITE_REQUIRED",
    "STACKED",
    "UNRESOLVED",
}
BLOCK_MARKERS = {
    "EVIDENCE_BLOCKED": "EVIDENCE_BLOCKED",
    "LOCAL_BLOCKED": "LOCAL_BLOCKED",
    "PUBLIC_SOURCE_EXHAUSTION_OPEN": "PUBLIC_SOURCE_EXHAUSTION_OPEN",
    "PUBLIC_SOURCE_EXHAUSTION = OPEN": "PUBLIC_SOURCE_EXHAUSTION_OPEN",
    "PUBLIC_SOURCE_EXHAUSTION=OPEN": "PUBLIC_SOURCE_EXHAUSTION_OPEN",
    "STACK_REWRITE_REQUIRED": "STACK_REWRITE_REQUIRED",
    "REBASE_AND_RETEST": "REBASE_REQUIRED",
}


def is_rate_limit_error(message: str) -> bool:
    lowered = message.lower()
    return "api rate limit exceeded" in lowered or "rate limit exceeded" in lowered


@dataclass
class Disposition:
    repository: str
    number: int
    title: str
    head_sha: str
    base_ref: str
    base_sha: str
    observed_main_sha: str
    merge_sha: str | None
    draft: bool
    state: str
    reasons: list[str]
    head_checks_total: int = 0
    head_checks_non_success: int = 0
    merge_checks_total: int = 0
    merge_checks_non_success: int = 0
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


def check_runs(owner: str, repo: str, sha: str, token: str) -> tuple[int, int, list[str]]:
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
    # Discovery only. A current merge-result CI surface outranks path non-overlap;
    # path non-overlap alone is never sufficient promotion evidence.
    cmp1 = request_json(f"{API}/repos/{owner}/{repo}/compare/{urllib.parse.quote(base_ref, safe='')}...{head_sha}", token)
    merge_base = cmp1["merge_base_commit"]["sha"]
    cmp2 = request_json(f"{API}/repos/{owner}/{repo}/compare/{merge_base}...{urllib.parse.quote(base_ref, safe='')}", token)
    main_paths = {f["filename"] for f in cmp2.get("files", [])}
    return sorted(changed_paths(owner, repo, number, token) & main_paths)


def classify(repo_full: str, pr: dict[str, Any], observed_main_sha: str, token: str) -> Disposition:
    owner, repo = repo_full.split("/", 1)
    number = int(pr["number"])
    body = pr.get("body") or ""
    reasons: list[str] = []
    state = "UNRESOLVED"

    if pr.get("draft"):
        reasons.append("DRAFT")
    base_ref = str(pr["base"]["ref"])
    base_sha = str(pr["base"]["sha"])
    head_sha = str(pr["head"]["sha"])
    merge_sha = pr.get("merge_commit_sha")
    if base_ref != "main":
        reasons.append(f"STACKED_BASE:{base_ref}")
    elif base_sha != observed_main_sha:
        reasons.append(f"BASE_DRIFT:{base_sha}->{observed_main_sha}")

    for marker, disposition in BLOCK_MARKERS.items():
        if marker in body:
            reasons.append(marker)
            state = disposition

    head_total, head_bad, head_bad_names = check_runs(owner, repo, head_sha, token)
    if head_total == 0:
        reasons.append("NO_EXACT_HEAD_CHECKS")
    if head_bad:
        reasons.append("NON_GREEN_EXACT_HEAD_CHECKS:" + ",".join(head_bad_names[:10]))

    merge_total = 0
    merge_bad = 0
    merge_bad_names: list[str] = []
    if base_ref == "main":
        if not merge_sha:
            reasons.append("NO_CURRENT_MERGE_SHA")
        else:
            merge_total, merge_bad, merge_bad_names = check_runs(owner, repo, str(merge_sha), token)
            if merge_total == 0:
                reasons.append("NO_CURRENT_MERGE_CHECKS")
            if merge_bad:
                reasons.append("NON_GREEN_CURRENT_MERGE_CHECKS:" + ",".join(merge_bad_names[:10]))

    threads = unresolved_threads(owner, repo, number, token)
    if threads:
        reasons.append(f"UNRESOLVED_REVIEW_THREADS:{threads}")

    overlap: list[str] = []
    if base_ref == "main":
        overlap = main_overlap(owner, repo, base_ref, head_sha, number, token)
        if overlap:
            reasons.append(f"CURRENT_MAIN_PATH_OVERLAP:{len(overlap)}")

    if state == "UNRESOLVED":
        if base_ref != "main":
            state = "STACKED"
        elif base_sha != observed_main_sha:
            state = "REBASE_REQUIRED"
        elif pr.get("draft"):
            state = "BLOCKED"
        elif not merge_sha or merge_total == 0 or merge_bad or threads:
            state = "BLOCKED"
        else:
            # Current-base merge-result CI is the promotion evidence. Exact-head
            # checks are retained as independent evidence but cannot substitute for it.
            state = "MERGE_READY"

    return Disposition(
        repository=repo_full,
        number=number,
        title=pr.get("title", ""),
        head_sha=head_sha,
        base_ref=base_ref,
        base_sha=base_sha,
        observed_main_sha=observed_main_sha,
        merge_sha=str(merge_sha) if merge_sha else None,
        draft=bool(pr.get("draft")),
        state=state,
        reasons=reasons,
        head_checks_total=head_total,
        head_checks_non_success=head_bad,
        merge_checks_total=merge_total,
        merge_checks_non_success=merge_bad,
        unresolved_review_threads=threads,
        overlap_paths=overlap,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="federation/completion-gate.json")
    ap.add_argument("--out", default="artifacts/federation-completion-ledger.json")
    ap.add_argument("--fail-on-actionable", action="store_true")
    ap.add_argument(
        "--allow-rate-limit-partial",
        action="store_true",
        help="Exit 0 when the only audit errors are GitHub rate-limit errors. "
        "The ledger still records those errors and remains non-certifying.",
    )
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("BLOCKED: GITHUB_TOKEN/GH_TOKEN is required", file=sys.stderr)
        return 2

    cfg = json.loads(Path(args.config).read_text())
    rows: list[Disposition] = []
    errors: list[str] = []
    truncated_reason: str | None = None
    observed_main: dict[str, str] = {}
    for repo_full in cfg["repositories"]:
        owner, repo = repo_full.split("/", 1)
        try:
            main_doc = request_json(f"{API}/repos/{owner}/{repo}/commits/main", token)
            main_sha = str(main_doc.get("sha", ""))
            if len(main_sha) != 40:
                raise RuntimeError(f"invalid main SHA: {main_sha!r}")
            observed_main[repo_full] = main_sha
            prs = paged(f"{API}/repos/{owner}/{repo}/pulls?state=open", token)
            for pr in prs:
                try:
                    rows.append(classify(repo_full, pr, main_sha, token))
                except Exception as exc:  # fail closed per PR; preserve denominator
                    error = f"{repo_full}#{pr.get('number')}: {exc}"
                    errors.append(error)
                    rows.append(
                        Disposition(
                            repo_full,
                            int(pr.get("number", -1)),
                            pr.get("title", ""),
                            pr.get("head", {}).get("sha", ""),
                            pr.get("base", {}).get("ref", ""),
                            pr.get("base", {}).get("sha", ""),
                            main_sha,
                            pr.get("merge_commit_sha"),
                            bool(pr.get("draft")),
                            "UNRESOLVED",
                            ["AUDIT_EXCEPTION"],
                        )
                    )
                    if args.allow_rate_limit_partial and is_rate_limit_error(error):
                        truncated_reason = error
                        break
            if truncated_reason:
                break
        except Exception as exc:
            error = f"{repo_full}: {exc}"
            errors.append(error)
            if args.allow_rate_limit_partial and is_rate_limit_error(error):
                truncated_reason = error
                break

    counts: dict[str, int] = {}
    for row in rows:
        counts[row.state] = counts.get(row.state, 0) + 1
    actionable = {state: counts[state] for state in sorted(ACTIONABLE_STATES) if counts.get(state)}
    rate_limit_errors = [err for err in errors if is_rate_limit_error(err)]
    only_rate_limit_errors = bool(errors) and len(rate_limit_errors) == len(errors)
    certification = "PASS"
    if errors:
        certification = "PROVISIONAL_RATE_LIMIT_PARTIAL" if only_rate_limit_errors else "FAIL"
    elif args.fail_on_actionable and actionable:
        certification = "FAIL_ACTIONABLE_RESIDUE"
    result = {
        "schema_version": 2,
        "scope": "REMOTE_GITHUB_ONLY",
        "certification": certification,
        "local_worktree_state": "BLOCKED_NOT_OBSERVED",
        "repositories": cfg["repositories"],
        "observed_main_shas": observed_main,
        "open_pr_denominator": len(rows),
        "audit_truncated": truncated_reason is not None,
        "truncation_reason": truncated_reason,
        "counts": dict(sorted(counts.items())),
        "actionable_counts": actionable,
        "errors": errors,
        "rate_limit_error_count": len(rate_limit_errors),
        "rows": [asdict(r) for r in rows],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(
        {k: result[k] for k in (
            "open_pr_denominator",
            "counts",
            "actionable_counts",
            "certification",
            "rate_limit_error_count",
            "errors",
        )},
        indent=2,
    ))

    if errors:
        if args.allow_rate_limit_partial and only_rate_limit_errors:
            return 0
        return 2
    if args.fail_on_actionable and actionable:
        # A completion claim fails while any current integration/reconciliation
        # residue remains. Explained evidence/local/source blockers may remain open.
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
