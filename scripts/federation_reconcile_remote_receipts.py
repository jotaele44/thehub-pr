#!/usr/bin/env python3
from __future__ import annotations
import json
import tempfile
import urllib.request
from pathlib import Path
from federation_contract_guard import reconcile


def load(p):
    return json.loads(Path(p).read_text())


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
        print(
            json.dumps(
                {
                    "status": "PASS" if not errors else "FAIL",
                    "errors": errors,
                    "receipts_checked": len(receipts),
                },
                indent=2,
            )
        )
        return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
