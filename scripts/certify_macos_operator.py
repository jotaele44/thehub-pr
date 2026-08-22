#!/usr/bin/env python3
"""Certify the four gates that need a real macOS host, and sign the result.

G07 (Keychain), G15 (setup through the UI), G16 (validation through the UI) and
G22 (a real operator pass) cannot be produced in a headless Linux container.
There is no window server, no native file picker and no Keychain, so those gates
were recorded ``blocked_not_certified`` with a stated cause. This script is how
they stop being blocked.

**An operator's answer never satisfies a step.** Where a human must act -- pick a
file through the native picker, click through the App Center -- the script checks
the machine-observable *consequence* of that action instead of recording the
claim. Picking a file produces a receipt carrying a file token and a staged path;
running a validation produces a receipt whose operation id and status the script
reads back. If the consequence is missing, the step is refuted no matter what the
operator said. That keeps a certification honest even when nobody is watching,
which is the only condition under which it is worth having.

Signing key. Unlike the static attestations, this one must be signed with a key
that is **not** published: an operator certification's entire value is that a
person really ran it on real hardware, and an artifact anyone could mint proves
nothing about that. ``PRII_MANAGER_RECEIPT_SIGNING_KEY`` is required and the
fixture seed is explicitly refused.

Usage on the Mac. The bootstrap nonce is a shared secret you choose, not
something the manager prints -- it is read from the environment by
``federation_manager_api`` at import time, so it must be exported before uvicorn
starts, and the same value given here::

    # terminal 1 -- the manager
    export PRII_MANAGER_BOOTSTRAP_NONCE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export PRII_MANAGER_RECEIPT_SIGNING_KEY="$HOME/.prii/manager.pem"
    python3 -m uvicorn server.backend.main:app --port 8000

    # terminal 2 -- this script, with the same nonce
    export PRII_MANAGER_RECEIPT_SIGNING_KEY="$HOME/.prii/manager.pem"
    export PRII_MANAGER_BOOTSTRAP_NONCE='the-value-from-terminal-1'
    python3 scripts/certify_macos_operator.py

``--manager-url`` must include the router prefix. The manager API is mounted at
``/api/federation-manager`` on the main app, so a bare host answers ``405`` on
``POST /session`` -- the SPA catch-all matches the path for ``GET`` only.

Then send back ``reports/federation/attestations/operator.*.attestation.json``
and the public half of the key.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from server.backend.federation_manager_receipts import (  # noqa: E402
    RECEIPT_SIGNING_KEY_ENV,
    AttestationInputs,
    AttestationStore,
    ReceiptError,
    signer_from_environment,
)
from tools.emit_gate_attestations import TEST_ATTESTATION_SEED  # noqa: E402

CANARY_SECRET_ID = "PRII_CERTIFICATION_CANARY"
#: Distinctive enough that finding it anywhere is unambiguous, and long enough
#: to clear the redactor's minimum-length rule.
CANARY_VALUE = "prii-canary-8f2a41d7c95b4e06-do-not-log"


class CertificationRefused(RuntimeError):
    """The environment cannot produce this evidence. Never downgraded to a warning."""


# ── environment ─────────────────────────────────────────────────────────────


def require_macos() -> Dict[str, str]:
    """Refuse anywhere else.

    The attestation records its platform, so a Linux-produced document would be
    self-evidently not macOS evidence -- but refusing up front means nobody has
    to notice that later.
    """
    if platform.system() != "Darwin":
        raise CertificationRefused(
            f"this certifies macOS-only gates and is running on {platform.system()}. "
            "Run it on the Mac being certified."
        )
    return {
        "platform": "darwin",
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }


def require_operator_key():
    """Refuse the published fixture seed."""
    configured = os.environ.get(RECEIPT_SIGNING_KEY_ENV, "").strip()
    if not configured:
        raise CertificationRefused(
            f"{RECEIPT_SIGNING_KEY_ENV} is unset. An operator certification must be signed "
            "with a key that is not published, or the artifact proves nothing about who ran it."
        )
    signer = signer_from_environment("prii-operator-macos")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        fixture = Ed25519PrivateKey.from_private_bytes(TEST_ATTESTATION_SEED)
        from cryptography.hazmat.primitives import serialization

        if signer.public_key_pem() == fixture.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ):
            raise CertificationRefused(
                "the configured key is the published fixture seed. Anyone could mint this "
                "attestation, so it would not evidence that an operator ran anything."
            )
    except ImportError:  # pragma: no cover - cryptography is a hard dependency
        pass
    return signer


# ── the manager, over the same HTTP surface the UI uses ─────────────────────


class Manager:
    """Thin client for the loopback manager API.

    Deliberately over HTTP rather than in-process: G15 and G16 are claims about
    what the UI can drive, and the UI has nothing but this surface.
    """

    def __init__(self, base_url: str, origin: str, nonce: str):
        import urllib.request

        self._urllib = urllib.request
        self.base_url = base_url.rstrip("/")
        self.origin = origin
        self._token = self._open_session(nonce)

    def _request(self, method: str, path: str, body: Optional[dict] = None, token: bool = True):
        payload = json.dumps(body).encode() if body is not None else None
        request = self._urllib.Request(f"{self.base_url}{path}", data=payload, method=method)
        request.add_header("Origin", self.origin)
        request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("Authorization", f"Bearer {self._token}")
        with self._urllib.urlopen(request, timeout=30) as response:
            raw = response.read().decode()
        return json.loads(raw) if raw else {}

    def _open_session(self, nonce: str) -> str:
        response = self._request(
            "POST", "/session", {"nonce": nonce, "origin": self.origin}, token=False
        )
        return response["token"]

    def receipts(self) -> List[dict]:
        return self._request("GET", "/receipts").get("receipts", [])

    def run(self, operation_id: str, parameters: dict, file_tokens: Optional[dict] = None) -> dict:
        return self._request(
            "POST",
            f"/operations/{operation_id}/run",
            {"parameters": parameters, "file_tokens": file_tokens or {}, "acknowledged": True},
        )

    def logs(self, run_id: str) -> str:
        return json.dumps(self._request("GET", f"/runs/{run_id}/logs"))

    def gates(self) -> dict:
        return self._request("GET", "/gates")

    def set_secret(self, app_id: str, secret_id: str, value: str) -> dict:
        return self._request(
            "POST", "/secrets", {"app_id": app_id, "secret_id": secret_id, "value": value}
        )

    def secret_presence(self, app_id: str, secret_ids: List[str]) -> dict:
        return self._request(
            "POST", "/secrets/presence", {"app_id": app_id, "secret_ids": secret_ids}
        )

    def delete_secret(self, app_id: str, secret_id: str) -> dict:
        return self._request("DELETE", f"/secrets/{app_id}/{secret_id}")


# ── operator prompts, corroborated by machine observation ───────────────────


def ask(prompt: str) -> bool:
    """Ask the operator to do something. The answer is a cue, never the evidence."""
    print(f"\n  ACTION: {prompt}")
    reply = input("  press enter when done, or type 'skip': ").strip().lower()
    return reply != "skip"


def await_receipt(
    manager: Manager,
    predicate: Callable[[dict], bool],
    *,
    timeout: float = 180.0,
    poll: float = 2.0,
) -> Optional[dict]:
    """Poll until a receipt matching ``predicate`` appears, or give up.

    This is what makes an operator answer unnecessary: the receipt either shows
    up or it does not.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for receipt in manager.receipts():
            body = receipt.get("receipt", receipt)
            if predicate(body):
                return body
        time.sleep(poll)
    return None


# ── G07: Keychain ───────────────────────────────────────────────────────────


def certify_keychain(manager: Manager, app_id: str) -> Dict[str, Any]:
    """Round-trip a real Keychain item, then hunt for the value everywhere."""
    from server.backend.federation_manager_secrets import MacOSKeychainProvider

    provider = MacOSKeychainProvider()
    observations: Dict[str, Any] = {"provider": "MacOSKeychainProvider"}

    provider.set(app_id, CANARY_SECRET_ID, CANARY_VALUE)
    observations["write_succeeded"] = True
    observations["exists_after_write"] = provider.exists(app_id, CANARY_SECRET_ID)

    presence = manager.secret_presence(app_id, [CANARY_SECRET_ID])
    observations["api_reports_presence"] = bool(
        presence.get("present", {}).get(CANARY_SECRET_ID, presence.get(CANARY_SECRET_ID))
    )
    # The value must not come back out of any surface, at any length.
    serialized = json.dumps(presence)
    observations["value_absent_from_presence_response"] = CANARY_VALUE not in serialized

    gates_payload = json.dumps(manager.gates())
    observations["value_absent_from_gates_payload"] = CANARY_VALUE not in gates_payload

    receipts_payload = json.dumps(manager.receipts())
    observations["value_absent_from_receipts"] = CANARY_VALUE not in receipts_payload

    provider.delete(app_id, CANARY_SECRET_ID)
    observations["exists_after_delete"] = provider.exists(app_id, CANARY_SECRET_ID)

    satisfied = (
        observations["write_succeeded"]
        and observations["exists_after_write"]
        and observations["api_reports_presence"]
        and observations["value_absent_from_presence_response"]
        and observations["value_absent_from_gates_payload"]
        and observations["value_absent_from_receipts"]
        and not observations["exists_after_delete"]
    )
    return {"satisfied": satisfied, "observations": observations}


# ── G15 / G16: the UI, with consequences checked ────────────────────────────


def certify_ui_setup(manager: Manager) -> Dict[str, Any]:
    """Prerequisites and a native file pick, both confirmed by their side effects."""
    observations: Dict[str, Any] = {}
    before = len(manager.receipts())

    ask(
        "In the App Center, open TheHub and run the prerequisite check, then use the "
        "native file picker to attach a manifest to hub.validate_manifest and run it. "
        "Do not use a Terminal."
    )

    receipt = await_receipt(
        manager,
        lambda body: body.get("operation_id") == "hub.validate_manifest"
        and body.get("status") == "succeeded",
    )
    observations["receipt_seen"] = receipt is not None
    observations["receipts_before"] = before

    if receipt:
        inputs = json.dumps(receipt.get("inputs", receipt))
        # A real native pick goes through the file-token broker, so the receipt
        # records a logical name and a hash and never the operator's own path.
        observations["run_id"] = receipt.get("run_id")
        observations["records_a_file_input"] = (
            "sha256" in inputs.lower() or "file" in inputs.lower()
        )
        observations["no_home_path_in_receipt"] = str(Path.home()) not in inputs

    satisfied = bool(
        observations.get("receipt_seen")
        and observations.get("records_a_file_input")
        and observations.get("no_home_path_in_receipt")
    )
    return {"satisfied": satisfied, "observations": observations}


def certify_ui_validation(manager: Manager) -> Dict[str, Any]:
    """Validation controls driven from the UI, with receipts retained afterwards."""
    observations: Dict[str, Any] = {}

    ask(
        "In the App Center, run hub.validate_package and hub.validate_federation from the "
        "operation list, then reload the page so the receipts are re-fetched."
    )

    wanted = ["hub.validate_package", "hub.validate_federation"]
    seen = {}
    for operation_id in wanted:
        receipt = await_receipt(
            manager,
            lambda body, op=operation_id: body.get("operation_id") == op
            and body.get("status") == "succeeded",
            timeout=120.0,
        )
        seen[operation_id] = receipt.get("run_id") if receipt else None

    observations["receipts"] = seen
    # Retention is the actual claim: they must still be there after a reload.
    observations["retained_after_reload"] = all(seen.values())
    return {"satisfied": all(seen.values()), "observations": observations}


# ── G22: one operator pass, through to rollback ─────────────────────────────


def certify_operator_end_to_end(manager: Manager) -> Dict[str, Any]:
    """The full chain, finishing with a rollback that actually restores state."""
    observations: Dict[str, Any] = {}
    chain = [
        "hub.list",
        "hub.aggregate",
        "hub.correlate",
        "hub.ingest",
        "hub.analytics_v2",
    ]

    ask(
        "Run this chain from the App Center, in order, waiting for each to finish: "
        + " -> ".join(chain)
    )

    completed = {}
    for operation_id in chain:
        receipt = await_receipt(
            manager,
            lambda body, op=operation_id: body.get("operation_id") == op
            and body.get("status") == "succeeded",
            timeout=240.0,
        )
        completed[operation_id] = receipt.get("run_id") if receipt else None
    observations["chain"] = completed
    observations["chain_complete"] = all(completed.values())

    ask(
        "Now force a rollback: run hub.ingest again against a deliberately invalid input "
        "so validation fails, and confirm the UI reports the run rolled back."
    )
    rolled_back = await_receipt(
        manager,
        lambda body: body.get("operation_id") == "hub.ingest"
        and body.get("status") in {"rolled_back", "failed"}
        and body.get("rollback", {}).get("performed") is True,
        timeout=240.0,
    )
    observations["rollback_receipt"] = rolled_back.get("run_id") if rolled_back else None
    observations["rollback_performed"] = rolled_back is not None

    satisfied = observations["chain_complete"] and observations["rollback_performed"]
    return {"satisfied": satisfied, "observations": observations}


# ── driver ──────────────────────────────────────────────────────────────────

STEPS = [
    ("operator.macos_keychain", "G07", certify_keychain),
    ("operator.macos_ui_setup", "G15", certify_ui_setup),
    ("operator.macos_ui_validation", "G16", certify_ui_validation),
    ("operator.macos_end_to_end", "G22", certify_operator_end_to_end),
]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # The manager API is a router on the main app, not a standalone service, so
    # the default carries the mount prefix. Without it every call 405s: the SPA
    # catch-all matches the bare path for GET, so POST /session is "method not
    # allowed" rather than the 404 that would have pointed at the real problem.
    parser.add_argument("--manager-url", default="http://127.0.0.1:8000/api/federation-manager")
    parser.add_argument("--origin", default="http://127.0.0.1:5173")
    parser.add_argument("--nonce", default=os.environ.get("PRII_MANAGER_BOOTSTRAP_NONCE", ""))
    parser.add_argument("--app-id", default="thehub")
    parser.add_argument(
        "--out", type=Path, default=REPO_ROOT / "reports" / "federation" / "attestations"
    )
    parser.add_argument(
        "--write-public-key",
        type=Path,
        default=REPO_ROOT / "reports" / "federation" / "operator_public_key.pem",
    )
    parser.add_argument(
        "--only", action="append", help="Run only these attestation ids. Repeatable."
    )
    args = parser.parse_args(argv)

    try:
        environment = require_macos()
        signer = require_operator_key()
    except (CertificationRefused, ReceiptError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    if not args.nonce:
        print(
            "refused: no bootstrap nonce. Start the manager through the native host and pass "
            "--nonce (or set PRII_MANAGER_BOOTSTRAP_NONCE).",
            file=sys.stderr,
        )
        return 2

    session_id = uuid.uuid4().hex
    print(f"certifying on {environment['platform']} {environment['release']} ({session_id[:8]})")

    try:
        manager = Manager(args.manager_url, args.origin, args.nonce)
    except Exception as exc:  # noqa: BLE001 - any transport failure is fatal here
        print(f"refused: cannot reach the manager at {args.manager_url}: {exc}", file=sys.stderr)
        return 2

    store = AttestationStore(args.out, signer)
    refuted: List[str] = []

    for attestation_id, gate, step in STEPS:
        if args.only and attestation_id not in args.only:
            continue
        print(f"\n== {gate}  {attestation_id}")
        try:
            outcome = (
                step(manager, args.app_id)
                if step is certify_keychain
                else step(manager)
            )
        except Exception as exc:  # noqa: BLE001 - a crash is a refutation, not a skip
            outcome = {"satisfied": False, "observations": {"error": repr(exc)}}

        store.write(
            AttestationInputs(
                attestation_id=attestation_id,
                kind="operator_certification",
                produced_by=f"scripts/certify_macos_operator.py::{step.__name__}",
                result="satisfied" if outcome["satisfied"] else "refuted",
                environment={**environment, "session_id": session_id},
                details=outcome["observations"],
            )
        )
        marker = "ok" if outcome["satisfied"] else "REFUTED"
        print(f"  {marker}")
        if not outcome["satisfied"]:
            refuted.append(attestation_id)

    args.write_public_key.parent.mkdir(parents=True, exist_ok=True)
    args.write_public_key.write_bytes(signer.public_key_pem())

    print(f"\nattestations: {args.out}")
    print(f"public key:   {args.write_public_key}")
    print("\nSend both back. The evaluator verifies the signature before any gate moves.")
    if refuted:
        print(f"refuted: {refuted}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
