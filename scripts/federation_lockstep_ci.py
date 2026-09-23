#!/usr/bin/env python3
"""Fail-closed cross-repository LOCKSTEP evaluator.

This gate evaluates declared dependency bindings only. It verifies that every
impacted repository exposes at least one current federation contract manifestation
at its default branch. It does not certify a Floot app, producer data, or consumer
receipt and never treats GitHub transport acceptance as ingestion evidence.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API = "https://api.github.com"
OWNER = "jotaele44"
APPS = {"aguayluz", "centinelas", "moneysweep", "ovnis", "skywatcher", "spiderweb", "thehub"}
REPOS = {app: f"{OWNER}/{app}-pr" for app in APPS}
CONTRACT_PATHS = [".federation/haf_contract.json", "federation.json"]


def request_json(url: str, token: str | None) -> Any:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "thehub-lockstep-ci")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def fetch_contract(repo: str, token: str | None) -> dict[str, Any]:
    errors: list[str] = []
    for path in CONTRACT_PATHS:
        try:
            data = request_json(f"{API}/repos/{repo}/contents/{path}", token)
            content = base64.b64decode(data["content"]).decode("utf-8")
            parsed = json.loads(content)
            return {
                "repository": repo,
                "path": path,
                "blob_sha": data.get("sha"),
                "byte_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "contract": parsed,
            }
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                errors.append(f"{path}:HTTP_{exc.code}")
        except Exception as exc:  # fail-closed evidence capture
            errors.append(f"{path}:{exc}")
    raise RuntimeError(f"NO_CURRENT_FEDERATION_CONTRACT:{repo}:{';'.join(errors)}")


def evaluate(source_app: str, change_class: str, contract_id: str | None, config: dict[str, Any], token: str | None) -> dict[str, Any]:
    if source_app not in APPS:
        return {"state": "BLOCKED", "residue": [f"UNKNOWN_SOURCE_APP:{source_app}"], "impacts": []}
    bindings = [
        row for row in config.get("bindings", [])
        if row.get("source_app") == source_app
        and change_class in row.get("change_classes", [])
        and (not contract_id or row.get("contract_id") == contract_id)
    ]
    if change_class != "APP_LOCAL" and not bindings:
        return {"state": "BLOCKED", "residue": ["NO_DECLARED_BINDING_FOR_CHANGE"], "impacts": []}
    if change_class == "APP_LOCAL" and not bindings:
        return {"state": "PASS", "residue": [], "impacts": []}

    impacts: list[dict[str, Any]] = []
    residue: list[str] = []
    for binding in bindings:
        target = str(binding.get("target_app"))
        if target not in APPS:
            residue.append(f"UNKNOWN_TARGET_APP:{target}")
            continue
        try:
            contract = fetch_contract(REPOS[target], token)
            impacts.append({
                "source_app": source_app,
                "target_app": target,
                "change_class": change_class,
                "contract_id": binding.get("contract_id"),
                "binding_evidence": binding.get("evidence"),
                "target_contract": {k: contract[k] for k in ("repository", "path", "blob_sha", "byte_sha256")},
                "state": "PASS",
            })
        except Exception as exc:
            residue.append(str(exc))
            impacts.append({"source_app": source_app, "target_app": target, "state": "BLOCKED", "error": str(exc)})
    return {"state": "PASS" if not residue else "BLOCKED", "residue": residue, "impacts": impacts}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="federation/lockstep-bindings.json")
    parser.add_argument("--source-app", required=True)
    parser.add_argument("--change-class", required=True, choices=["SHARED_CONTRACT", "SCHEMA", "GEOMETRY_AUTHORITY", "IDENTITY_RULE", "FEDERATION_PACKAGE", "PRODUCER_INTERFACE", "APP_LOCAL"])
    parser.add_argument("--contract-id")
    parser.add_argument("--out", default="artifacts/federation-lockstep-ci.json")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text())
    result = evaluate(args.source_app, args.change_class, args.contract_id, config, os.environ.get("GITHUB_TOKEN"))
    result.update({
        "schema_version": "federation-lockstep-ci/v1",
        "source_app": args.source_app,
        "change_class": args.change_class,
        "contract_id": args.contract_id,
        "rule": "PASS proves only current declared target federation-contract availability for explicit bindings; it is not app/data/native certification.",
    })
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
