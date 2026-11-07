#!/usr/bin/env python3
"""Read-only live-main Grid V2 pin drift monitor. Never grants identity authority."""
from __future__ import annotations
import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

OWNER = "jotaele44"
CONSUMERS = ("aguayluz-pr", "skywatcher-pr", "ovnis-pr", "moneysweep-pr", "centinelas-pr")
PIN_PATH = "federation/spatial/pr_grid_geographic_v2.pin.json"
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
HASH_RE = re.compile(r"^[a-f0-9]{64}$")

class RetrievalError(Exception):
    pass

@dataclass(frozen=True)
class Observation:
    repo: str
    commit: str
    authority_commit: str
    grid_hash: str
    grid_version: str
    status: str

def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "prii-grid-live-drift/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=18) as response:
            if response.status != 200:
                raise RetrievalError(f"HTTP {response.status}")
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise RetrievalError(f"GitHub request failed: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise RetrievalError("Expected GitHub object")
    return data

def read_live_pin(repo: str, fetch=fetch_json) -> Observation:
    # Resolve main once; retrieve each pin by immutable commit to avoid TOCTOU.
    branch = fetch(f"https://api.github.com/repos/{OWNER}/{repo}/branches/main")
    commit = (branch.get("commit") or {}).get("sha")
    if not isinstance(commit, str) or not SHA_RE.fullmatch(commit):
        raise RetrievalError("Invalid main commit SHA")
    raw = fetch(f"https://api.github.com/repos/{OWNER}/{repo}/contents/{PIN_PATH}?ref={commit}")
    if raw.get("encoding") != "base64" or not isinstance(raw.get("content"), str):
        raise RetrievalError("Missing base64 pin content")
    try:
        pin = json.loads(base64.b64decode(raw["content"], validate=False))
    except (ValueError, TypeError) as exc:
        raise RetrievalError("Invalid pin content") from exc
    if not isinstance(pin, dict) or pin.get("consumer") != repo:
        raise RetrievalError("Unexpected pin consumer identity")
    authority, digest, version = pin.get("authority_commit"), pin.get("grid_manifest_sha256"), pin.get("grid_version")
    if not isinstance(authority, str) or not SHA_RE.fullmatch(authority):
        raise RetrievalError("Invalid authority commit")
    if not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
        raise RetrievalError("Invalid grid hash")
    if not isinstance(version, str) or not version:
        raise RetrievalError("Invalid grid version")
    return Observation(repo, commit, authority, digest, version, "OBSERVED")

def evaluate(reference: Observation, observed: list[Observation]) -> tuple[int, list[str]]:
    lines = ["| Repository | Live main | Authority | Manifest SHA-256 | Verdict |", "|---|---|---|---|---|"]
    bad = False
    for row in observed:
        match = (row.authority_commit, row.grid_hash, row.grid_version) == (reference.authority_commit, reference.grid_hash, reference.grid_version)
        verdict = "MATCH" if match else "DRIFT"
        bad |= not match
        lines.append(f"| {row.repo} | `{row.commit[:12]}` | `{row.authority_commit[:12]}` | `{row.grid_hash[:12]}` | {verdict} |")
    return (1 if bad else 0), lines

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-pin", default=PIN_PATH)
    parser.add_argument("--summary-file", default=os.environ.get("GITHUB_STEP_SUMMARY"))
    args = parser.parse_args()
    try:
        pin = json.loads(Path(args.reference_pin).read_text(encoding="utf-8"))
        reference = Observation("thehub-pr", "LOCAL_CHECKOUT", pin["authority_commit"], pin["grid_manifest_sha256"], pin["grid_version"], "REFERENCE")
        if not SHA_RE.fullmatch(reference.authority_commit) or not HASH_RE.fullmatch(reference.grid_hash):
            raise RetrievalError("Invalid local authority/hash")
        observed = [read_live_pin(repo) for repo in CONSUMERS]
        code, lines = evaluate(reference, observed)
        state = "DRIFT" if code else "MATCH"
    except (RetrievalError, OSError, ValueError, KeyError, TypeError) as exc:
        code, state = 2, "UNRESOLVED"
        lines = [f"Observation incomplete: {type(exc).__name__}: {exc}"]
    report = "\n".join([f"### PR Grid V2 live-main monitor — {state}", "Read-only advisory; not a federation certification or canonical geometry proof.", *lines]) + "\n"
    print(report)
    if args.summary_file:
        with open(args.summary_file, "a", encoding="utf-8") as out:
            out.write(report)
    return code

if __name__ == "__main__":
    sys.exit(main())
