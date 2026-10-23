#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REFS_PATH = Path("governance/producer_receipt_refs.json")
CAPABILITY_ID = "jp-flood-certification"


class FreshnessError(RuntimeError):
    pass


def load_refs(path: Path = REFS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_json(url: str, timeout: int = 20) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def classify(meta: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
    transition = latest.get("transition") or {}
    reproducibility = latest.get("reproducibility") or {}

    if latest.get("schema_version") != meta.get("schema_version"):
        raise FreshnessError("schema_version drift")

    if latest.get("certification_invariant") != meta.get("certification_invariant"):
        raise FreshnessError("certification invariant drift")

    if transition.get("status") == "TRANSPORT_BLOCKED" or reproducibility.get("status") == "TRANSPORT_BLOCKED":
        return {
            "status": "TRANSPORT_BLOCKED",
            "blocking": False,
            "reason": "latest observation is transport-blocked; frozen pin remains authoritative",
        }

    if latest.get("requires_readjudication"):
        return {
            "status": "REQUIRES_READJUDICATION",
            "blocking": True,
            "reason": "latest receipt explicitly requires readjudication",
        }

    transition_drift = (
        transition.get("status") != "PASS"
        or transition.get("listed_count") != meta.get("transition_listed_count")
        or transition.get("transition_count") != meta.get("transition_count")
    )
    reproducibility_drift = (
        reproducibility.get("status") != "PASS"
        or reproducibility.get("blocking_count") != meta.get("blocking_count")
        or reproducibility.get("identical_count") != meta.get("identical_count")
        or reproducibility.get("metadata_only_count") != meta.get("metadata_only_count")
    )
    if transition_drift or reproducibility_drift:
        return {
            "status": "REQUIRES_READJUDICATION",
            "blocking": True,
            "reason": "latest source-state or reproducibility semantics differ from pinned receipt",
        }

    pinned_run = int(meta.get("workflow_run_id", 0))
    latest_run = int(latest.get("workflow_run_id", 0))
    if latest_run < pinned_run:
        raise FreshnessError(
            f"latest workflow_run_id regressed: pinned={pinned_run} latest={latest_run}"
        )

    if latest.get("source_main_sha") != meta.get("source_main_sha"):
        return {
            "status": "PIN_UPDATE_REQUIRED",
            "blocking": True,
            "reason": "latest PASS receipt is bound to a newer/different Spiderweb main",
        }

    return {
        "status": "CURRENT_EQUIVALENT",
        "blocking": False,
        "reason": "latest receipt is semantically equivalent and bound to the pinned Spiderweb main",
    }


def run(refs_path: Path = REFS_PATH) -> tuple[int, dict[str, Any]]:
    refs = load_refs(refs_path)
    meta = (refs.get("capability_receipts") or {}).get(CAPABILITY_ID)
    if not isinstance(meta, dict):
        raise FreshnessError("missing JP flood capability receipt metadata")

    latest_ref = meta.get("latest_ref")
    latest_path = meta.get("latest_path")
    repo = meta.get("repo")
    if not all(isinstance(v, str) and v for v in (latest_ref, latest_path, repo)):
        raise FreshnessError("latest receipt locator is incomplete")

    url = f"https://raw.githubusercontent.com/{repo}/{latest_ref}/{latest_path}"
    try:
        latest = fetch_json(url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        result = {
            "schema_version": "thehub.jp-flood-receipt-freshness/v1",
            "capability": CAPABILITY_ID,
            "status": "TRANSPORT_BLOCKED",
            "blocking": False,
            "reason": f"unable to fetch latest durable receipt: {type(exc).__name__}: {exc}",
            "pinned": {
                "sha": meta.get("sha"),
                "path": meta.get("path"),
                "source_main_sha": meta.get("source_main_sha"),
                "workflow_run_id": meta.get("workflow_run_id"),
            },
        }
        return 0, result

    classification = classify(meta, latest)
    result = {
        "schema_version": "thehub.jp-flood-receipt-freshness/v1",
        "capability": CAPABILITY_ID,
        **classification,
        "pinned": {
            "sha": meta.get("sha"),
            "path": meta.get("path"),
            "source_main_sha": meta.get("source_main_sha"),
            "workflow_run_id": meta.get("workflow_run_id"),
        },
        "latest": {
            "source_main_sha": latest.get("source_main_sha"),
            "workflow_run_id": latest.get("workflow_run_id"),
            "transition": latest.get("transition"),
            "reproducibility": latest.get("reproducibility"),
        },
    }
    return (1 if classification["blocking"] else 0), result


def main() -> int:
    try:
        code, result = run()
    except FreshnessError as exc:
        print(json.dumps({
            "schema_version": "thehub.jp-flood-receipt-freshness/v1",
            "capability": CAPABILITY_ID,
            "status": "FAIL",
            "blocking": True,
            "reason": str(exc),
        }, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
