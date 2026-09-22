#!/usr/bin/env python3
from __future__ import annotations
import json
import tempfile
import urllib.request
from pathlib import Path
from federation_contract_guard import reconcile


def load(p):
    return json.loads(Path(p).read_text())


def validate_capability_receipt(capability_id, meta, data):
    errors = []
    checks = {
        "schema_version": data.get("schema_version"),
        "source_main_sha": data.get("source_main_sha"),
        "workflow_run_id": data.get("workflow_run_id"),
        "certification_invariant": data.get("certification_invariant"),
    }
    for key, observed in checks.items():
        expected = meta.get(key)
        if observed != expected:
            errors.append(
                f"{capability_id}: {key} mismatch expected={expected!r} got={observed!r}"
            )

    transition = data.get("transition") or {}
    transition_checks = {
        "status": meta.get("transition_status"),
        "listed_count": meta.get("transition_listed_count"),
        "transition_count": meta.get("transition_count"),
    }
    for key, expected in transition_checks.items():
        observed = transition.get(key)
        if observed != expected:
            errors.append(
                f"{capability_id}: transition.{key} mismatch "
                f"expected={expected!r} got={observed!r}"
            )

    reproducibility = data.get("reproducibility") or {}
    reproducibility_checks = {
        "status": meta.get("reproducibility_status"),
        "blocking_count": meta.get("blocking_count"),
        "identical_count": meta.get("identical_count"),
        "metadata_only_count": meta.get("metadata_only_count"),
    }
    for key, expected in reproducibility_checks.items():
        observed = reproducibility.get(key)
        if observed != expected:
            errors.append(
                f"{capability_id}: reproducibility.{key} mismatch "
                f"expected={expected!r} got={observed!r}"
            )
    return errors


def main():
    refs = load("governance/producer_receipt_refs.json")
    matrix = load("governance/compatibility_matrix.json")
    receipts = []
    errors = []
    with tempfile.TemporaryDirectory(prefix="federation-receipts-") as tmp:
        for repo_id, meta in refs["producers"].items():
            owner_repo = meta["repo"]
            sha = meta["sha"]
            path = refs["receipt_path"]
            url = f"https://raw.githubusercontent.com/{owner_repo}/{sha}/{path}"
            try:
                with urllib.request.urlopen(url, timeout=20) as r:
                    body = r.read().decode("utf-8")
                data = json.loads(body)
                if data.get("repo") != repo_id:
                    errors.append(f"{repo_id}: remote receipt repo mismatch")
                receipt_path = Path(tmp) / f"{repo_id}.json"
                receipt_path.write_text(body, encoding="utf-8")
                receipts.append(str(receipt_path))
            except Exception as exc:
                errors.append(f"{repo_id}: unable to fetch pinned receipt: {exc}")
        errors.extend(reconcile(matrix, receipts))

        capability_receipts_checked = 0
        for capability_id, meta in (refs.get("capability_receipts") or {}).items():
            url = (
                f"https://raw.githubusercontent.com/{meta['repo']}/"
                f"{meta['sha']}/{meta['path']}"
            )
            try:
                with urllib.request.urlopen(url, timeout=20) as r:
                    body = r.read().decode("utf-8")
                data = json.loads(body)
                errors.extend(validate_capability_receipt(capability_id, meta, data))
                capability_receipts_checked += 1
            except Exception as exc:
                errors.append(
                    f"{capability_id}: unable to fetch pinned capability receipt: {exc}"
                )

        print(
            json.dumps(
                {
                    "status": "PASS" if not errors else "FAIL",
                    "errors": errors,
                    "receipts_checked": len(receipts),
                    "capability_receipts_checked": capability_receipts_checked,
                },
                indent=2,
            )
        )
        return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
