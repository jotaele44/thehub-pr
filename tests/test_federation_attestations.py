"""Signed attestations, persisted signing keys, and gate profiles.

Covers the three things a receipt cannot evidence -- code that must never run
(G03), a capability that must not exist (G20), and forced-failure rollback
(G13) -- plus F022, where an ephemeral signing key silently invalidated every
receipt written before a restart.

The emphasis throughout is negative. An attestation mechanism that only ever
passes is indistinguishable from one that returns ``satisfied`` unconditionally,
so most of what follows tries to get a false claim accepted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("cryptography")

from jsonschema import Draft202012Validator, ValidationError  # noqa: E402

from server.backend.federation_manager import RELEASE_FORMAT_CHECKER  # noqa: E402
from server.backend.federation_manager_receipts import (  # noqa: E402
    RECEIPT_SIGNING_KEY_ENV,
    AttestationInputs,
    AttestationStore,
    GateRule,
    ReceiptError,
    ReceiptSigner,
    build_attestation_body,
    evaluate_gates,
    signer_from_environment,
    verify_attestation,
    verify_receipt,
)

ATTESTATION_SCHEMA = json.loads(
    (REPO_ROOT / "schemas" / "gate_attestation.schema.json").read_text(encoding="utf-8")
)
GATE_SCHEMA = json.loads(
    (REPO_ROOT / "schemas" / "gate_evidence.schema.json").read_text(encoding="utf-8")
)


@pytest.fixture
def signer():
    return ReceiptSigner.generate("prii-manager-test")


def make_attestation(signer, attestation_id="static.no_arbitrary_shell", result="satisfied"):
    return signer.sign_attestation(
        build_attestation_body(
            AttestationInputs(
                attestation_id=attestation_id,
                kind="static_analysis",
                produced_by="tests::make_attestation",
                result=result,
                environment={"platform": "linux"},
                details={"modules_scanned": 9},
            )
        )
    )


# ── the envelope itself ─────────────────────────────────────────────────────


def test_a_valid_attestation_verifies(signer):
    document = make_attestation(signer)
    assert verify_attestation(document, public_key_pem=signer.public_key_pem())


def test_an_attestation_signed_by_another_key_is_refused(signer):
    forged = make_attestation(ReceiptSigner.generate("attacker"))
    with pytest.raises(ReceiptError):
        verify_attestation(forged, public_key_pem=signer.public_key_pem())


def test_editing_the_result_after_signing_is_detected(signer):
    document = make_attestation(signer, result="refuted")
    document["attestation"]["result"] = "satisfied"
    with pytest.raises(ReceiptError):
        verify_attestation(document, public_key_pem=signer.public_key_pem())


def test_an_unknown_kind_cannot_be_built():
    with pytest.raises(ReceiptError):
        build_attestation_body(
            AttestationInputs(
                attestation_id="x.y",
                kind="vibes",
                produced_by="p",
                result="satisfied",
                environment={},
                details={},
            )
        )


def test_an_unknown_result_cannot_be_built():
    with pytest.raises(ReceiptError):
        build_attestation_body(
            AttestationInputs(
                attestation_id="x.y",
                kind="static_analysis",
                produced_by="p",
                result="probably_fine",
                environment={},
                details={},
            )
        )


def test_attestation_matches_its_schema(signer):
    Draft202012Validator(ATTESTATION_SCHEMA, format_checker=RELEASE_FORMAT_CHECKER).validate(
        make_attestation(signer)
    )


def test_schema_rejects_a_free_text_result(signer):
    document = make_attestation(signer)
    document["attestation"]["result"] = "mostly satisfied"
    with pytest.raises(ValidationError):
        Draft202012Validator(ATTESTATION_SCHEMA, format_checker=RELEASE_FORMAT_CHECKER).validate(
            document
        )


# ── gates bound to attestations ─────────────────────────────────────────────


RULE = GateRule(
    "G03_NO_ARBITRARY_SHELL", "no shell", required_attestations=["static.no_arbitrary_shell"]
)


def _evaluate(signer, attestations):
    return evaluate_gates(
        [RULE], [], public_key_pem=signer.public_key_pem(), attestations=attestations
    )["gates"][0]


def test_a_satisfied_attestation_passes_the_gate(signer):
    gate = _evaluate(signer, [make_attestation(signer)])
    assert gate["status"] == "passed"
    assert gate["attested_by"][0]["signature_verified"] is True


def test_a_refuted_attestation_fails_the_gate_rather_than_reading_as_absent(signer):
    """'failed' and 'not_run' are different claims and must not be conflated.

    Reporting a refuted check as not_run would say "we did not look" about a
    gate we looked at and found broken.
    """
    gate = _evaluate(signer, [make_attestation(signer, result="refuted")])
    assert gate["status"] == "failed"
    assert "refuted" in gate["status_reason"]


def test_a_missing_attestation_leaves_the_gate_not_run(signer):
    gate = _evaluate(signer, [])
    assert gate["status"] == "not_run"


def test_a_forged_attestation_contributes_nothing(signer):
    """The gate must not pass, and must not report the forgery as evidence."""
    gate = _evaluate(signer, [make_attestation(ReceiptSigner.generate("attacker"))])
    assert gate["status"] == "not_run"
    assert gate["attested_by"] == []


def test_an_attestation_for_a_different_gate_does_not_satisfy_this_one(signer):
    gate = _evaluate(signer, [make_attestation(signer, attestation_id="static.something_else")])
    assert gate["status"] == "not_run"


def test_evidence_with_an_attested_gate_matches_the_v2_schema(signer):
    evidence = evaluate_gates(
        [RULE],
        [],
        public_key_pem=signer.public_key_pem(),
        attestations=[make_attestation(signer)],
        profile_id="hub_slice",
        profile_scope="TheHub only",
    )
    Draft202012Validator(GATE_SCHEMA, format_checker=RELEASE_FORMAT_CHECKER).validate(evidence)
    assert evidence["profile_id"] == "hub_slice"


def test_schema_rejects_passed_with_no_evidence_of_either_kind():
    forged = {
        "schema_version": "prii_gate_evidence_v2",
        "evaluated_at": "2026-07-27T00:00:00Z",
        "gates": [
            {
                "gate_id": "G03_NO_ARBITRARY_SHELL",
                "status": "passed",
                "blocking": True,
                "derived_from": [],
            }
        ],
    }
    with pytest.raises(ValidationError):
        Draft202012Validator(GATE_SCHEMA, format_checker=RELEASE_FORMAT_CHECKER).validate(forged)


# ── the store ───────────────────────────────────────────────────────────────


def test_store_round_trips_and_validates(tmp_path, signer):
    store = AttestationStore(tmp_path / "att", signer, schema=ATTESTATION_SCHEMA)
    store.write(
        AttestationInputs(
            attestation_id="static.no_deletion_capability",
            kind="static_analysis",
            produced_by="tests",
            result="satisfied",
            environment={"platform": "linux"},
            details={"operations_scanned": 68},
        )
    )
    documents = store.all_documents()
    assert len(documents) == 1
    assert verify_attestation(
        documents[0], public_key_pem=signer.public_key_pem(), schema=ATTESTATION_SCHEMA
    )


# ── F022: the signing key must outlive the process ──────────────────────────


def test_a_persisted_key_still_verifies_after_a_restart(tmp_path, monkeypatch):
    """The defect F022 records: receipts stop verifying once the manager restarts."""
    key_path = tmp_path / "manager.pem"
    key_path.write_bytes(ReceiptSigner.generate("seed").private_key_pem())
    monkeypatch.setenv(RECEIPT_SIGNING_KEY_ENV, str(key_path))

    before = signer_from_environment("prii-manager")
    document = before.sign({"run_id": "r1", "operation_id": "hub.list"})

    after = signer_from_environment("prii-manager")  # a fresh process would do this
    assert after.public_key_pem() == before.public_key_pem()
    # The point of the gate: a receipt written before the restart still counts.
    assert verify_receipt(document, public_key_pem=after.public_key_pem())


def test_an_ephemeral_key_does_not_survive_a_restart(monkeypatch):
    """Pins the behaviour the warning describes, so the fallback cannot look safe."""
    monkeypatch.delenv(RECEIPT_SIGNING_KEY_ENV, raising=False)
    assert (
        signer_from_environment().public_key_pem()
        != signer_from_environment().public_key_pem()
    )


def test_a_configured_key_that_is_missing_refuses_rather_than_falling_back(tmp_path, monkeypatch):
    """Silently degrading here would write evidence that stops verifying later."""
    monkeypatch.setenv(RECEIPT_SIGNING_KEY_ENV, str(tmp_path / "absent.pem"))
    with pytest.raises(ReceiptError):
        signer_from_environment()


def test_a_non_ed25519_key_is_refused(tmp_path, monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key_path = tmp_path / "rsa.pem"
    key_path.write_bytes(
        rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    monkeypatch.setenv(RECEIPT_SIGNING_KEY_ENV, str(key_path))
    with pytest.raises(ReceiptError):
        signer_from_environment()
