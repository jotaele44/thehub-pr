"""Guard rails on the macOS operator certification.

The script itself only runs on a Mac, so what is testable here is the part that
matters most: that it refuses to produce evidence it cannot honestly produce,
and that an operator's answer never substitutes for an observed consequence.

A certification script is exactly the kind of thing that quietly degrades into a
rubber stamp -- somebody adds a fallback for the machine they happen to be on,
and afterwards it passes everywhere. These tests exist to make that a failing
build rather than a discovery six months later.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from scripts.certify_macos_operator import (  # noqa: E402
    STEPS,
    CertificationRefused,
    await_receipt,
    require_macos,
    require_operator_key,
)
from server.backend.federation_manager_receipts import (  # noqa: E402
    RECEIPT_SIGNING_KEY_ENV,
    AttestationInputs,
    GateRule,
    ReceiptSigner,
    build_attestation_body,
    evaluate_gates,
)
from tools.emit_gate_attestations import TEST_ATTESTATION_SEED  # noqa: E402


# ── it must refuse where it cannot see ──────────────────────────────────────


def test_it_refuses_to_run_anywhere_but_macos(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    with pytest.raises(CertificationRefused):
        require_macos()


def test_it_records_darwin_when_it_does_run(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    assert require_macos()["platform"] == "darwin"


def test_it_refuses_without_a_configured_key(monkeypatch):
    monkeypatch.delenv(RECEIPT_SIGNING_KEY_ENV, raising=False)
    with pytest.raises(CertificationRefused):
        require_operator_key()


def test_it_refuses_the_published_fixture_seed(tmp_path, monkeypatch):
    """The whole value of this artifact is that not everyone could have made it."""
    key_path = tmp_path / "fixture.pem"
    key_path.write_bytes(
        Ed25519PrivateKey.from_private_bytes(TEST_ATTESTATION_SEED).private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    monkeypatch.setenv(RECEIPT_SIGNING_KEY_ENV, str(key_path))
    with pytest.raises(CertificationRefused):
        require_operator_key()


def test_it_accepts_an_operator_held_key(tmp_path, monkeypatch):
    key_path = tmp_path / "operator.pem"
    key_path.write_bytes(ReceiptSigner.generate("op").private_key_pem())
    monkeypatch.setenv(RECEIPT_SIGNING_KEY_ENV, str(key_path))
    assert require_operator_key().public_key_pem()


# ── an operator's answer is never the evidence ──────────────────────────────


class FakeManager:
    def __init__(self, receipts=()):
        self._receipts = list(receipts)

    def receipts(self):
        return self._receipts


def test_await_receipt_gives_up_rather_than_assuming(monkeypatch):
    """If the consequence never appears, the step is refuted regardless of what was said."""
    monkeypatch.setattr("time.sleep", lambda _: None)
    assert await_receipt(FakeManager(), lambda body: True, timeout=0.01, poll=0.001) is None


def test_await_receipt_finds_a_matching_receipt(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    manager = FakeManager([{"receipt": {"operation_id": "hub.list", "status": "succeeded"}}])
    found = await_receipt(
        manager, lambda body: body.get("operation_id") == "hub.list", timeout=1.0, poll=0.001
    )
    assert found["status"] == "succeeded"


def test_every_step_covers_a_distinct_blocked_gate():
    """The four steps must map one-to-one onto the gates that were blocked."""
    assert {gate for _, gate, _ in STEPS} == {"G07", "G15", "G16", "G22"}
    assert len({attestation_id for attestation_id, _, _ in STEPS}) == 4


def test_step_attestation_ids_match_what_the_hub_profile_requires():
    """A rename on either side would leave the gates silently unsatisfiable."""
    from tools.evaluate_federation_gates import HUB_SLICE_RULES

    required = {
        attestation_id
        for rule in HUB_SLICE_RULES
        for attestation_id in rule.required_attestations
        if attestation_id.startswith("operator.")
    }
    assert required == {attestation_id for attestation_id, _, _ in STEPS}


# ── attestations from more than one signer ──────────────────────────────────


def _attestation(signer, attestation_id, result="satisfied"):
    return signer.sign_attestation(
        build_attestation_body(
            AttestationInputs(
                attestation_id=attestation_id,
                kind="operator_certification",
                produced_by="tests",
                result=result,
                environment={"platform": "darwin"},
                details={},
            )
        )
    )


def test_an_attestation_counts_if_any_trusted_key_signed_it():
    """Static checks and operator certifications legitimately have different signers."""
    ci = ReceiptSigner.generate("ci")
    operator = ReceiptSigner.generate("operator")
    rules = [
        GateRule("G07_NATIVE_SECRETS", "keychain", required_attestations=["operator.macos_keychain"])
    ]

    evidence = evaluate_gates(
        rules,
        [],
        public_key_pem=ci.public_key_pem(),
        attestations=[_attestation(operator, "operator.macos_keychain")],
        attestation_public_key_pem=[ci.public_key_pem(), operator.public_key_pem()],
    )
    assert evidence["gates"][0]["status"] == "passed"


def test_an_untrusted_signer_still_counts_for_nothing():
    ci = ReceiptSigner.generate("ci")
    rules = [
        GateRule("G07_NATIVE_SECRETS", "keychain", required_attestations=["operator.macos_keychain"])
    ]
    evidence = evaluate_gates(
        rules,
        [],
        public_key_pem=ci.public_key_pem(),
        attestations=[_attestation(ReceiptSigner.generate("stranger"), "operator.macos_keychain")],
        attestation_public_key_pem=[ci.public_key_pem()],
    )
    assert evidence["gates"][0]["status"] == "not_run"
    assert evidence["gates"][0]["attested_by"] == []


def test_a_refuted_operator_certification_fails_the_gate():
    """A Mac that genuinely failed must not read the same as a Mac nobody ran."""
    operator = ReceiptSigner.generate("operator")
    rules = [
        GateRule("G07_NATIVE_SECRETS", "keychain", required_attestations=["operator.macos_keychain"])
    ]
    evidence = evaluate_gates(
        rules,
        [],
        public_key_pem=operator.public_key_pem(),
        attestations=[_attestation(operator, "operator.macos_keychain", result="refuted")],
    )
    assert evidence["gates"][0]["status"] == "failed"
