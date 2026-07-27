"""Signed, hash-chained execution receipts and the gate evaluator.

A receipt is the only evidence a readiness gate accepts. It is signed by the
manager and chained to its predecessor, so removing or reordering a receipt
breaks the chain visibly rather than quietly improving the record.

The gate evaluator is deliberately blunt: a gate reaches ``passed`` only from
receipts whose signatures verified. Annotations are carried through untouched
and ignored when computing status -- the point of machine-derived gates is that
a note cannot turn a red gate green.

Structured as a pure core plus a thin store, matching
``server/backend/notifications.py``: signing, chaining, and evaluation are
ordinary functions over plain data, and persistence is a small separate layer.
"""
from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from jsonschema import Draft202012Validator

from server.backend.federation_manager import RELEASE_FORMAT_CHECKER
from server.backend.federation_manager_operations import canonical_json, sha256_hex
from server.backend.federation_manager_transactions import write_atomic

RECEIPT_SCHEMA_VERSION = "prii_execution_receipt_v1"
GATE_EVIDENCE_SCHEMA_VERSION = "prii_gate_evidence_v1"


class ReceiptError(RuntimeError):
    """A receipt could not be produced, verified, or chained."""


def new_run_id() -> str:
    return uuid.uuid4().hex


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── signing ─────────────────────────────────────────────────────────────────


class ReceiptSigner:
    """Signs receipts with the manager's own Ed25519 key.

    Distinct from the policy key by design: the policy says what *may* run and
    is issued upstream; a receipt says what *did* run and is attested locally.
    One key doing both would let anyone who could issue a policy also forge
    evidence that it had been executed.
    """

    def __init__(self, private_key, key_id: str):
        self._key = private_key
        self.key_id = key_id

    @classmethod
    def from_pem(cls, pem: bytes, key_id: str) -> "ReceiptSigner":
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        key = load_pem_private_key(pem, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ReceiptError("receipt signing key must be Ed25519")
        return cls(key, key_id)

    @classmethod
    def generate(cls, key_id: str = "prii-manager-local") -> "ReceiptSigner":
        """Create an ephemeral manager key.

        Fine for a single manager process: receipts are verified within the same
        run of the manager that produced them. A deployment that must verify
        receipts across restarts should persist a key and pass it to ``from_pem``.
        """
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        return cls(Ed25519PrivateKey.generate(), key_id)

    def public_key_pem(self) -> bytes:
        from cryptography.hazmat.primitives import serialization

        return self._key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def sign(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        payload = canonical_json(body)
        return {
            "receipt": dict(body),
            "signature": {
                "key_id": self.key_id,
                "algorithm": "Ed25519",
                "value": base64.b64encode(self._key.sign(payload)).decode("ascii"),
                "payload_sha256": sha256_hex(payload),
            },
        }


def verify_receipt(
    document: Mapping[str, Any],
    *,
    public_key_pem: bytes,
    schema: Optional[Mapping[str, Any]] = None,
) -> str:
    """Verify one receipt and return its canonical digest.

    Raises rather than returning a boolean: a caller that forgot to check a
    boolean would silently treat a forged receipt as evidence.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    if schema is not None:
        Draft202012Validator(schema, format_checker=RELEASE_FORMAT_CHECKER).validate(document)

    body = document["receipt"]
    signature = document["signature"]
    payload = canonical_json(body)
    digest = sha256_hex(payload)

    if digest != signature["payload_sha256"]:
        raise ReceiptError("receipt digest does not match its signature block")

    key = load_pem_public_key(public_key_pem)
    if not isinstance(key, Ed25519PublicKey):
        raise ReceiptError("receipt verification key is not Ed25519")
    try:
        key.verify(base64.b64decode(signature["value"], validate=True), payload)
    except (InvalidSignature, ValueError) as exc:
        raise ReceiptError("receipt signature verification failed") from exc

    return digest


# ── building ────────────────────────────────────────────────────────────────


@dataclass
class ReceiptInputs:
    """Everything a receipt records. Assembled by the runner as a run proceeds."""

    run_id: str
    operation_id: str
    app_id: str
    policy_id: str
    policy_sequence: int
    policy_sha256: str
    policy_key_id: str
    status: str
    started_at: str
    finished_at: str
    argv_redacted: Sequence[str]
    argv_sha256: str
    parameters_redacted: Mapping[str, Any]
    environment_allowlist: Sequence[str]
    transaction: Mapping[str, Any]
    log_sha256: str
    log_bytes: int
    log_truncated: bool
    log_redactions: int
    exit_code: Optional[int] = None
    inputs: Sequence[Mapping[str, Any]] = ()
    outputs: Sequence[Mapping[str, Any]] = ()
    validators: Sequence[Mapping[str, Any]] = ()


def build_receipt_body(
    data: ReceiptInputs, previous_receipt_sha256: Optional[str]
) -> Dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "run_id": data.run_id,
        "operation_id": data.operation_id,
        "app_id": data.app_id,
        "policy": {
            "policy_id": data.policy_id,
            "sequence": data.policy_sequence,
            "payload_sha256": data.policy_sha256,
            "key_id": data.policy_key_id,
        },
        "status": data.status,
        "exit_code": data.exit_code,
        "started_at": data.started_at,
        "finished_at": data.finished_at,
        "argv_redacted": list(data.argv_redacted),
        "argv_sha256": data.argv_sha256,
        "parameters_redacted": dict(data.parameters_redacted),
        "environment_allowlist": list(data.environment_allowlist),
        "inputs": [dict(item) for item in data.inputs],
        "outputs": [dict(item) for item in data.outputs],
        "validators": [dict(item) for item in data.validators],
        "transaction": dict(data.transaction),
        "log": {
            "sha256": data.log_sha256,
            "bytes": data.log_bytes,
            "truncated": data.log_truncated,
            "redactions": data.log_redactions,
        },
        "previous_receipt_sha256": previous_receipt_sha256,
    }


# ── store ───────────────────────────────────────────────────────────────────


class ReceiptStore:
    """Append-only receipt chain on disk.

    Each receipt records its predecessor's digest, so a reader can walk the
    chain and detect a removed or reordered entry. The head digest is kept in a
    small pointer file, written atomically, so a crash between appending and
    updating the head leaves a detectable mismatch rather than a silently
    forked chain.
    """

    def __init__(self, root: Path, signer: ReceiptSigner, schema: Optional[Mapping[str, Any]] = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._signer = signer
        self._schema = schema

    @property
    def signer(self) -> ReceiptSigner:
        return self._signer

    @property
    def _head_path(self) -> Path:
        return self.root / "HEAD"

    def head(self) -> Optional[str]:
        if not self._head_path.exists():
            return None
        value = self._head_path.read_text(encoding="utf-8").strip()
        return value or None

    def path_for(self, run_id: str) -> Path:
        return self.root / f"{run_id}.receipt.json"

    def append(self, data: ReceiptInputs) -> Dict[str, Any]:
        body = build_receipt_body(data, self.head())
        if self._schema is not None:
            document_for_validation = self._signer.sign(body)
            Draft202012Validator(self._schema, format_checker=RELEASE_FORMAT_CHECKER).validate(
                document_for_validation
            )
            document = document_for_validation
        else:
            document = self._signer.sign(body)

        write_atomic(
            self.path_for(data.run_id), json.dumps(document, indent=2, sort_keys=True) + "\n"
        )
        write_atomic(self._head_path, document["signature"]["payload_sha256"])
        return document

    def load(self, run_id: str) -> Dict[str, Any]:
        path = self.path_for(run_id)
        if not path.exists():
            raise ReceiptError(f"no receipt for run {run_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def all_documents(self) -> List[Dict[str, Any]]:
        documents = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in self.root.glob("*.receipt.json")
        ]
        documents.sort(key=lambda d: d["receipt"]["finished_at"])
        return documents

    def verify_chain(self) -> List[str]:
        """Verify every receipt and its links. Returns the problems found."""
        public_key = self._signer.public_key_pem()
        problems: List[str] = []
        documents = self.all_documents()

        digests: Dict[str, str] = {}
        for document in documents:
            run_id = document["receipt"]["run_id"]
            try:
                digests[run_id] = verify_receipt(
                    document, public_key_pem=public_key, schema=self._schema
                )
            except ReceiptError as exc:
                problems.append(f"{run_id}: {exc}")

        known = set(digests.values())
        for document in documents:
            previous = document["receipt"]["previous_receipt_sha256"]
            if previous is not None and previous not in known:
                problems.append(
                    f"{document['receipt']['run_id']}: predecessor {previous[:12]} is missing "
                    "from the chain"
                )
        return problems


# ── gate evaluation ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GateRule:
    gate_id: str
    requirement: str
    blocking: bool = True
    #: Operations whose successful receipts satisfy this gate.
    required_operations: Sequence[str] = ()
    #: Set when the gate cannot be evaluated from receipts in this environment.
    blocked_reason: str = ""
    deferred_reason: str = ""


def evaluate_gates(
    rules: Sequence[GateRule],
    documents: Sequence[Mapping[str, Any]],
    *,
    public_key_pem: bytes,
    schema: Optional[Mapping[str, Any]] = None,
    annotations: Optional[Mapping[str, Sequence[Mapping[str, Any]]]] = None,
    policy_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Derive gate status from verified receipts only.

    A receipt that fails verification contributes nothing -- it is not "evidence
    we could not check", it is not evidence.
    """
    annotations = annotations or {}
    verified: List[tuple[Mapping[str, Any], str]] = []
    for document in documents:
        try:
            digest = verify_receipt(document, public_key_pem=public_key_pem, schema=schema)
        except (ReceiptError, Exception):  # noqa: BLE001 - unverifiable is simply excluded
            continue
        verified.append((document["receipt"], digest))

    gates: List[Dict[str, Any]] = []
    for rule in rules:
        gate: Dict[str, Any] = {
            "gate_id": rule.gate_id,
            "requirement": rule.requirement,
            "blocking": rule.blocking,
            "derived_from": [],
        }
        notes = list(annotations.get(rule.gate_id, ()))
        if notes:
            gate["annotations"] = [dict(note) for note in notes]

        if rule.blocked_reason:
            gate["status"] = "blocked_not_certified"
            gate["status_reason"] = rule.blocked_reason
            gates.append(gate)
            continue
        if rule.deferred_reason:
            gate["status"] = "deferred"
            gate["status_reason"] = rule.deferred_reason
            gates.append(gate)
            continue

        satisfying = [
            (receipt, digest)
            for receipt, digest in verified
            if receipt["operation_id"] in rule.required_operations
            and receipt["status"] == "succeeded"
        ]
        covered = {receipt["operation_id"] for receipt, _ in satisfying}
        missing = sorted(set(rule.required_operations) - covered)

        gate["derived_from"] = [
            {"run_id": receipt["run_id"], "receipt_sha256": digest, "signature_verified": True}
            for receipt, digest in satisfying
        ]

        if not rule.required_operations:
            gate["status"] = "not_run"
            gate["status_reason"] = "no receipt-producing operation is bound to this gate"
        elif missing:
            gate["status"] = "not_run"
            gate["status_reason"] = f"no verified successful receipt for: {missing}"
        else:
            gate["status"] = "passed"

        gates.append(gate)

    evidence: Dict[str, Any] = {
        "schema_version": GATE_EVIDENCE_SCHEMA_VERSION,
        "evaluated_at": utc_now_iso(),
        "gates": gates,
    }
    if policy_sha256:
        evidence["policy_sha256"] = policy_sha256
    return evidence


def annotate(
    evidence: Mapping[str, Any], gate_id: str, author: str, note: str
) -> Dict[str, Any]:
    """Attach a human note to a gate without touching its status.

    The returned evidence is a copy with the note appended; the status field is
    carried through byte-for-byte. This function is the *only* supported way to
    add commentary, so there is one obvious path and it cannot pass.
    """
    result = json.loads(json.dumps(evidence))
    for gate in result["gates"]:
        if gate["gate_id"] == gate_id:
            gate.setdefault("annotations", []).append(
                {"author": author, "note": note, "recorded_at": utc_now_iso()}
            )
            return result
    raise ReceiptError(f"unknown gate: {gate_id}")


def write_gate_evidence(path: Path, evidence: Mapping[str, Any]) -> Path:
    return write_atomic(Path(path), json.dumps(evidence, indent=2, sort_keys=True) + "\n")


def summarize(evidence: Mapping[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for gate in evidence["gates"]:
        counts[gate["status"]] = counts.get(gate["status"], 0) + 1
    return dict(sorted(counts.items()))


def default_receipt_root() -> Path:
    override = os.environ.get("PRII_MANAGER_RECEIPT_ROOT")
    if override:
        return Path(override)
    from server.backend.federation_manager import resolve_os_paths

    return resolve_os_paths().data / "receipts"


def receipts_for_operation(
    documents: Iterable[Mapping[str, Any]], operation_id: str
) -> List[Mapping[str, Any]]:
    return [d for d in documents if d["receipt"]["operation_id"] == operation_id]
