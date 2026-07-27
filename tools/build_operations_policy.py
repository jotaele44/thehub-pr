#!/usr/bin/env python3
"""Generate and sign the operations policy from the design catalog.

Reads ``federation-design/OPERATIONS_CATALOG_DESIGN_v0_2.json`` (68 declared
operations) and emits ``config/operations_policy.json``, signed with an Ed25519
key.

Two different treatments, deliberately:

* **TheHub's 13 operations are decomposed by hand** below, against the actual
  ``src/hub/cli.py`` parser. A generator cannot infer that ``--in`` maps to
  ``in_dir`` or that ``wrap-bridge`` takes its path positionally, and guessing
  would produce a policy that looks authoritative while being wrong. Twelve are
  enabled; ``hub.fetch`` is declared and left disabled.
* **The 55 producer operations are carried mechanically** as
  ``DECLARED_NOT_ENABLED`` with a reason. They are accounted for -- gate G04
  wants zero unclassified rows -- without pretending they have been decomposed
  and verified.

Signing key. A production policy is signed with an operator-held key passed via
``--key``. The committed fixture is instead signed with a key derived from
``TEST_SIGNING_SEED`` below -- a published constant, not a secret. That keeps a
private-key file out of the repository while still producing a *real* Ed25519
signature that the verifier checks against the committed public key, so the
signature path is exercised for real rather than stubbed. Anyone can regenerate
the byte-identical policy.

Usage::

    python3 tools/build_operations_policy.py                      # test-key fixture
    python3 tools/build_operations_policy.py --key <private.pem>  # operator key
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from server.backend.federation_manager_operations import canonical_json, sha256_hex  # noqa: E402

CATALOG_PATH = REPO_ROOT / "federation-design" / "OPERATIONS_CATALOG_DESIGN_v0_2.json"
OUTPUT_PATH = REPO_ROOT / "config" / "operations_policy.json"

POLICY_ID = "prii-federation-ui-only-operations"
DEFAULT_KEY_ID = "prii-operations-test-2026-07"

#: Seed for the committed fixture's signing key. This is a PUBLISHED CONSTANT and
#: deliberately not a secret: it exists so the repository can carry a genuinely
#: signed policy without carrying a private-key file. A production policy is
#: signed with an operator-held key supplied via --key and a different key_id.
TEST_SIGNING_SEED = bytes.fromhex(
    "5052494920746573742d6f6e6c79206f7073207369676e696e6720736565642100"[:64]
)

DEFERRAL_REASON = (
    "Producer operation. Declared and classified for accounting, but not enabled in this "
    "vector: certification is scoped to TheHub's 13 operations, and enabling a producer "
    "operation requires its rollback strategy, entry-point hardening, and adapter to be "
    "built and verified first. See docs/FEDERATION_UI_OPERATIONS_HANDOFF_NEXT.md."
)

COMPOSITE_REASON = (
    "Declared as a shell composite (conditional clone followed by an installer invocation). "
    "It has no trusted executable identity and cannot be represented in any permitted "
    "execution form without first being decomposed into declarative steps."
)

FETCH_REASON = (
    "Repository acquisition is an R3 lifecycle operation requiring network egress, an "
    "allow-listed and pinned source, checksum or signature verification, and a staged "
    "rollback-safe checkout. Gate G09 is not certified in this vector, so the operation is "
    "declared and left disabled."
)

TOS_REASON = (
    "MiLUMA acquisition is ToS and WAF gated. It stays policy-disabled pending explicit "
    "source authorization; no amount of implementation work substitutes for that decision."
)


def _p(kind: str, **extra: Any) -> dict[str, Any]:
    return {"type": kind, **extra}


def _lit(value: str) -> dict[str, str]:
    return {"literal": value}


def _ref(name: str) -> dict[str, str]:
    return {"param": name}


#: TheHub operations, decomposed against src/hub/cli.py. `argv` elements are
#: appended after the console script and its fixed subcommand.
HUB_OPERATIONS: dict[str, dict[str, Any]] = {
    "hub.list": {
        "subcommand": "list",
        # Fixed rather than a free string: there is exactly one producers
        # registry, and accepting a caller-supplied path here would be a file
        # read primitive relative to the pinned app root for no benefit.
        "parameters": {"registry": _p("fixed", value="registry/producers.yaml")},
        "argv": [_lit("--registry"), _ref("registry")],
    },
    "hub.validate_manifest": {
        "subcommand": "validate-manifest",
        "parameters": {"path": _p("file_token", required=True, extensions=[".json"])},
        "argv": [_ref("path")],
    },
    "hub.validate_package": {
        "subcommand": "validate-package",
        "parameters": {"path": _p("directory", required=True)},
        "argv": [_ref("path")],
    },
    "hub.validate_federation": {
        "subcommand": "validate-federation",
        "parameters": {
            "root": _p("directory", required=True),
            "json": _p("fixed", value=True),
        },
        "argv": [_lit("--root"), _ref("root"), _lit("--json"), _ref("json")],
    },
    "hub.aggregate": {
        "subcommand": "aggregate",
        "parameters": {
            "root": _p("directory", required=True),
            "out": _p("managed_output_directory", default="data/aggregate"),
            "non_strict": _p("boolean", default=False),
        },
        "argv": [
            _lit("--root"),
            _ref("root"),
            _lit("--out"),
            _ref("out"),
            _lit("--non-strict"),
            _ref("non_strict"),
        ],
    },
    "hub.wrap_bridge": {
        "subcommand": "wrap-bridge",
        "parameters": {
            "path": _p("directory", required=True),
            "producer": _p(
                "enum",
                required=True,
                values=[
                    "spiderweb-pr",
                    "ovnis-pr",
                    "centinelas-pr",
                    "aguayluz-pr",
                    "moneysweep-pr",
                    "skywatcher-pr",
                ],
            ),
            "mode": _p("enum", default="test", values=["test", "production"]),
            "created_at": _p("datetime", default="1970-01-01T00:00:00Z"),
        },
        "argv": [
            _ref("path"),
            _lit("--producer"),
            _ref("producer"),
            _lit("--mode"),
            _ref("mode"),
            _lit("--created-at"),
            _ref("created_at"),
        ],
    },
    "hub.correlate": {
        "subcommand": "correlate",
        "parameters": {
            "in_dir": _p("directory", required=True),
            "out": _p("managed_output_directory", required=True),
            "window_days": _p("integer", default=7, minimum=0, maximum=3650),
            "threshold_km": _p("number", default=1.0, minimum=0, maximum=10000),
        },
        "argv": [
            _lit("--in"),
            _ref("in_dir"),
            _lit("--out"),
            _ref("out"),
            _lit("--window-days"),
            _ref("window_days"),
            _lit("--threshold-km"),
            _ref("threshold_km"),
        ],
    },
    "hub.ingest": {
        "subcommand": "ingest",
        "parameters": {
            "in_dir": _p("directory", required=True),
            "db": _p("managed_sqlite_path", default="data/hub.db", extensions=[".db"]),
        },
        "argv": [_lit("--in"), _ref("in_dir"), _lit("--db"), _ref("db")],
    },
    "hub.graph_report": {
        "subcommand": "graph-report",
        "parameters": {
            "in_dir": _p("directory", required=True),
            "json": _p("fixed", value=True),
        },
        "argv": [_lit("--in"), _ref("in_dir"), _lit("--json"), _ref("json")],
    },
    "hub.analytics_v2": {
        "subcommand": "analytics-v2",
        "parameters": {
            "in_dir": _p("directory", required=True),
            "out": _p("managed_file", default="data/aggregate/federation_analytics_v2.json"),
        },
        "argv": [_lit("--in"), _ref("in_dir"), _lit("--out"), _ref("out")],
    },
    "hub.consume_sensor_fusion": {
        "subcommand": "consume-sensor-fusion",
        "parameters": {
            "path": _p("file_token", required=True, extensions=[".json"]),
            "out": _p("managed_file", default="data/dashboard/skywatcher_sensor_fusion.json"),
        },
        "argv": [_ref("path"), _lit("--out"), _ref("out")],
    },
    "hub.maintenance": {
        "subcommand": "maintenance",
        "parameters": {
            "root": _p("directory", required=True),
            "write_report": _p("boolean", default=True),
            "fail_on_blocker": _p("boolean", default=False),
            "json": _p("fixed", value=True),
        },
        "argv": [
            _lit("--root"),
            _ref("root"),
            _lit("--write-report"),
            _ref("write_report"),
            _lit("--fail-on-blocker"),
            _ref("fail_on_blocker"),
            _lit("--json"),
            _ref("json"),
        ],
    },
}


def _producer_target(row: Mapping[str, Any]) -> dict[str, Any]:
    """Map a catalog row to the executable identity it *would* use once enabled."""
    kind = row["execution_kind"]
    fixed = row["fixed_target"]

    if kind == "composite":
        return {"kind": "composite_unresolved", "identifier": fixed.replace(":", "_")}
    if kind == "internal_builtin":
        return {"kind": "internal_builtin", "identifier": fixed}
    if kind == "python_module":
        return {"kind": "python_module", "identifier": fixed}
    if kind == "python_script":
        return {"kind": "python_script", "identifier": fixed}
    if kind == "make_target":
        return {"kind": "make_target", "identifier": fixed}
    if kind == "console_script":
        if ":" in fixed:
            executable, subcommand = fixed.split(":", 1)
            return {"kind": "console_script", "identifier": executable, "subcommand": subcommand}
        return {"kind": "console_script", "identifier": fixed}
    raise ValueError(f"unmapped execution kind: {kind!r}")


def _deferral_reason(row: Mapping[str, Any]) -> str:
    if row["operation_id"] == "aguayluz.fetch_luma_live":
        return TOS_REASON
    if row["execution_kind"] == "composite":
        return COMPOSITE_REASON
    return DEFERRAL_REASON


def build_policy(sequence: int, key_id: str, issued_at: datetime, valid_days: int) -> dict[str, Any]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    operations: list[dict[str, Any]] = []

    for row in catalog["operations"]:
        operation_id = row["operation_id"]
        common = {
            "operation_id": operation_id,
            "app_id": row["app_id"],
            "repo": row["repo"],
            "category": row["category"],
            "risk_class": row["risk_class"],
            "approval_policy": row["approval_policy"],
            "network_policy": row["network_policy"],
            "write_scope": row["write_scope"],
            "expected_outputs": list(row.get("expected_outputs", [])),
            "local_input_refs": list(row.get("local_input_refs", [])),
            "prerequisites": list(row.get("prerequisites", [])),
            "secret_refs": list(row.get("secret_refs", [])),
            "rollback_strategy": row["rollback_strategy"],
            "promotion_state": row["promotion_state"],
            "provenance": {
                "source": row["source"],
                "declared_source_text": row["raw_declared_command"],
            },
        }

        if operation_id in HUB_OPERATIONS:
            spec = HUB_OPERATIONS[operation_id]
            operations.append(
                {
                    **common,
                    "enablement": "ENABLED",
                    "target": {
                        "kind": "console_script",
                        "identifier": "hub",
                        "subcommand": spec["subcommand"],
                    },
                    "parameters": spec["parameters"],
                    "argv": spec["argv"],
                }
            )
        elif operation_id == "hub.fetch":
            operations.append(
                {
                    **common,
                    "enablement": "DECLARED_NOT_ENABLED",
                    "enablement_reason": FETCH_REASON,
                    "target": {"kind": "internal_builtin", "identifier": "repository_acquisition"},
                    "parameters": {},
                    "argv": [],
                }
            )
        else:
            operations.append(
                {
                    **common,
                    "enablement": "DECLARED_NOT_ENABLED",
                    "enablement_reason": _deferral_reason(row),
                    "target": _producer_target(row),
                    "parameters": {},
                    "argv": [],
                }
            )

    operations.sort(key=lambda item: item["operation_id"])

    return {
        "schema_version": "prii_operations_policy_v1",
        "policy_id": POLICY_ID,
        "sequence": sequence,
        "minimum_accepted_sequence": 1,
        "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
        "expires_at": (issued_at + timedelta(days=valid_days)).isoformat().replace("+00:00", "Z"),
        "key_id": key_id,
        "security_invariants": list(catalog["security_invariants"]),
        "operations": operations,
    }


def test_signing_key():
    """The fixture signing key, derived from the published seed."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(TEST_SIGNING_SEED)


def sign_policy(body: Mapping[str, Any], private_key_pem: bytes | None, key_id: str) -> dict[str, Any]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    if private_key_pem is None:
        key = test_signing_key()
    else:
        key = load_pem_private_key(private_key_pem, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise SystemExit("signing key must be Ed25519")
    payload = canonical_json(body)
    return {
        "policy": body,
        "signature": {
            "key_id": key_id,
            "algorithm": "Ed25519",
            "value": base64.b64encode(key.sign(payload)).decode("ascii"),
            "payload_sha256": sha256_hex(payload),
        },
    }


def write_public_key(path: Path) -> None:
    """Write the fixture's *public* key. No private key is ever written."""
    from cryptography.hazmat.primitives import serialization

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        test_signing_key()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"wrote {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--key",
        type=Path,
        help="Ed25519 private key in PEM format. Omit to sign with the published test seed.",
    )
    parser.add_argument("--key-id", default=DEFAULT_KEY_ID)
    parser.add_argument("--sequence", type=int, default=1)
    parser.add_argument("--valid-days", type=int, default=3650)
    parser.add_argument("--issued-at", default="2026-07-27T00:00:00Z")
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH)
    parser.add_argument(
        "--write-public-key",
        type=Path,
        metavar="PATH",
        help="Write the fixture public key and exit.",
    )
    args = parser.parse_args(argv)

    if args.write_public_key:
        write_public_key(args.write_public_key)
        return 0

    issued_at = datetime.fromisoformat(args.issued_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    body = build_policy(args.sequence, args.key_id, issued_at, args.valid_days)
    document = sign_policy(body, args.key.read_bytes() if args.key else None, args.key_id)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    enabled = sum(1 for op in body["operations"] if op["enablement"] == "ENABLED")
    print(
        f"wrote {args.out} — {len(body['operations'])} operations "
        f"({enabled} enabled, {len(body['operations']) - enabled} declared not enabled)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
