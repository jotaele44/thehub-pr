#!/usr/bin/env python3
"""Strict federation parity validator for PR_GRID_GEOGRAPHIC_V2 consumer pins.

By default this validates TheHub itself plus sibling repositories beneath
--root. With --require-all, every denominator consumer must be present and exact.
No geometry is read or reproduced.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DENOMINATOR_RELATIVE = Path("registry/pr_grid_v2_consumers.json")
PIN_RELATIVE = Path("federation/spatial/pr_grid_geographic_v2.pin.json")


class PinParityError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PinParityError(f"cannot read {path}") from exc
    except json.JSONDecodeError as exc:
        raise PinParityError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PinParityError(f"expected JSON object: {path}")
    return value


def _expected_contract(denom: dict[str, Any], consumer: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "pr_grid_geographic_v2_consumer_pin/1.0",
        "consumer": consumer["repo"],
        "geometry_authority": "spiderweb-pr",
        "authority_repository": denom["authority_repository"],
        "authority_commit": denom["authority_commit"],
        "grid_id": denom["grid_id"],
        "grid_version": denom["grid_version"],
        "crs": "EPSG:6566",
        "grid_manifest_sha256": denom["grid_manifest_sha256"],
        "cell_schema_sha256": denom["cell_schema_sha256"],
        "binding_schema_sha256": denom["binding_schema_sha256"],
        "binding_schema_version": "pr-grid-v2-binding/1.0",
        "mask_schema_sha256": denom["mask_schema_sha256"],
        "mask_schema_version": "pr-grid-v2-mask/1.0",
        "default_level": consumer["default_level"],
        "allowed_levels": denom["policy"]["allowed_levels"],
        "geometry_mode": denom["policy"]["geometry_mode"],
        "local_geometry_copy": denom["policy"]["local_geometry_copy"],
        "v1_coexistence": "PRESERVE_UNCHANGED",
        "compatibility_policy": denom["policy"]["compatibility_policy"],
    }


def _repo_root(
    repo: str,
    *,
    federation_root: Path,
    self_root: Path,
) -> Path:
    if repo == "thehub-pr":
        return self_root
    return federation_root / repo


def validate(
    *,
    denominator_path: Path,
    federation_root: Path,
    self_root: Path,
    require_all: bool,
) -> dict[str, Any]:
    denom = _load_json(denominator_path)
    consumers = denom.get("consumers")
    if not isinstance(consumers, list):
        raise PinParityError("denominator consumers must be a list")
    if denom.get("consumer_count") != len(consumers):
        raise PinParityError("consumer_count does not equal denominator length")
    if len(consumers) != 6:
        raise PinParityError(f"expected exactly 6 consumers, got {len(consumers)}")

    seen = set()
    rows = []
    problems = []

    for consumer in consumers:
        if not isinstance(consumer, dict):
            problems.append("invalid consumer row")
            continue
        repo = consumer.get("repo")
        if not isinstance(repo, str) or not repo:
            problems.append("consumer repo missing")
            continue
        if repo in seen:
            problems.append(f"duplicate consumer: {repo}")
            continue
        seen.add(repo)

        root = _repo_root(repo, federation_root=federation_root, self_root=self_root)
        pin_path = root / PIN_RELATIVE
        if not pin_path.exists():
            state = "MISSING"
            rows.append({"repo": repo, "state": state, "pin_path": str(pin_path)})
            if require_all:
                problems.append(f"{repo}: missing pin {pin_path}")
            continue

        pin = _load_json(pin_path)
        expected = _expected_contract(denom, consumer)
        mismatches = {
            key: {"expected": value, "actual": pin.get(key)}
            for key, value in expected.items()
            if pin.get(key) != value
        }

        blockers = pin.get("external_provider_blockers")
        blocker_map = {}
        if isinstance(blockers, list):
            for row in blockers:
                if isinstance(row, dict) and isinstance(row.get("id"), str):
                    blocker_map[row["id"]] = row.get("affects_grid_identity")
        if blocker_map != {"QA-D24-001": False, "QA-D24-003": False}:
            mismatches["external_provider_blockers"] = {
                "expected": {"QA-D24-001": False, "QA-D24-003": False},
                "actual": blocker_map,
            }

        state = "PASS" if not mismatches else "DIVERGENT"
        rows.append(
            {
                "repo": repo,
                "state": state,
                "pin_path": str(pin_path),
                "mismatches": mismatches,
            }
        )
        if mismatches:
            problems.append(f"{repo}: pin divergence")

    if seen != {row["repo"] for row in consumers if isinstance(row, dict) and "repo" in row}:
        problems.append("denominator uniqueness failure")

    result = {
        "schema_version": "pr_grid_geographic_v2_federation_parity_receipt/1.0",
        "grid_id": denom.get("grid_id"),
        "grid_version": denom.get("grid_version"),
        "authority_commit": denom.get("authority_commit"),
        "grid_manifest_sha256": denom.get("grid_manifest_sha256"),
        "denominator": len(consumers),
        "pass_count": sum(row["state"] == "PASS" for row in rows),
        "missing_count": sum(row["state"] == "MISSING" for row in rows),
        "divergent_count": sum(row["state"] == "DIVERGENT" for row in rows),
        "rows": rows,
        "state": "PASS" if not problems and len(rows) == len(consumers) else "FAIL",
        "problems": problems,
    }
    if result["state"] != "PASS":
        raise PinParityError(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("_federation"),
        help="directory containing sibling repository checkouts",
    )
    parser.add_argument(
        "--self-root",
        type=Path,
        default=Path("."),
        help="TheHub checkout root",
    )
    parser.add_argument(
        "--denominator",
        type=Path,
        default=DENOMINATOR_RELATIVE,
    )
    parser.add_argument("--require-all", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    try:
        result = validate(
            denominator_path=args.denominator,
            federation_root=args.root,
            self_root=args.self_root,
            require_all=args.require_all,
        )
    except PinParityError as exc:
        print(f"PR_GRID_V2_FEDERATION_PARITY=FAIL: {exc}")
        return 1

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(text, encoding="utf-8")
    print(text, end="")
    print("PR_GRID_V2_FEDERATION_PARITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
