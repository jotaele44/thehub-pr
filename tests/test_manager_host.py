"""The host that assembles the operations runtime.

These tests exist because of a specific failure: the first real operator
certification refuted all four macOS gates with the same
``HTTPError 503: Service Unavailable``. ``federation_manager_api.runtime`` was
``None`` and nothing outside a test fixture ever assigned it, so
``uvicorn server.backend.main:app`` served a manager whose entire operations
surface was unavailable.

The regression that matters is therefore not "does ``build_runtime`` return an
object" but "does a served manager stop answering 503". That is what
``test_a_hosted_manager_serves_operations_instead_of_503`` pins, and it is the
one test that would have caught the original defect.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

pytest.importorskip("cryptography")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from run_manager_host import HostRefused, build_runtime, main  # noqa: E402
from server.backend import federation_manager_api as api  # noqa: E402
from server.backend.federation_manager_receipts import (  # noqa: E402
    RECEIPT_SIGNING_KEY_ENV,
    ReceiptSigner,
)

NONCE = "a-bootstrap-nonce-long-enough-to-satisfy-the-model"
ORIGIN = "http://127.0.0.1:5173"


@pytest.fixture
def signing_key(tmp_path, monkeypatch):
    key_path = tmp_path / "manager.pem"
    key_path.write_bytes(ReceiptSigner.generate("host").private_key_pem())
    monkeypatch.setenv(RECEIPT_SIGNING_KEY_ENV, str(key_path))
    # A real Keychain call would prompt in CI; the provider selection itself is
    # covered by test_federation_secrets_and_files.
    monkeypatch.setenv("PRII_MANAGER_SECRET_PROVIDER", "memory")
    return key_path


def test_build_runtime_assembles_a_usable_runtime(tmp_path, signing_key):
    runtime, policy = build_runtime(tmp_path / "state", REPO_ROOT)

    assert isinstance(runtime, api.ManagerRuntime)
    assert policy.operations, "a host with no operations cannot certify anything"
    for name in ("receipts", "staging", "intake", "data"):
        assert (tmp_path / "state" / name).is_dir()


def test_a_hosted_manager_serves_operations_instead_of_503(tmp_path, signing_key, monkeypatch):
    """The regression the first operator run hit, pinned.

    Without an assigned runtime every one of these endpoints answers 503 and the
    certification refutes with no useful detail. This asserts the opposite.
    """
    runtime, _ = build_runtime(tmp_path / "state", REPO_ROOT)

    monkeypatch.setattr(api, "_bootstrap_nonce", NONCE)
    monkeypatch.setattr(api, "sessions", api.SessionManager(NONCE, api.ALLOWED_ORIGINS, 300))
    monkeypatch.setattr(api, "runtime", runtime)
    monkeypatch.setattr(api, "_stream_tickets", {})

    app = FastAPI()
    app.include_router(api.router)

    with TestClient(app, client=("127.0.0.1", 41234)) as client:
        session = client.post(
            "/api/federation-manager/session",
            json={"nonce": NONCE, "origin": ORIGIN},
            headers={"Origin": ORIGIN},
        )
        assert session.status_code == 200
        auth = {"Origin": ORIGIN, "Authorization": f"Bearer {session.json()['token']}"}

        # The three surfaces the certification touches first. Each 503'd on the
        # real run, and each refutation carried only {"error": "HTTPError 503"}.
        for path in ("/api/federation-manager/operations", "/api/federation-manager/receipts"):
            response = client.get(path, headers=auth)
            assert response.status_code != 503, f"{path} is still unhosted"
            assert response.status_code == 200, (path, response.status_code, response.text)

        presence = client.post(
            "/api/federation-manager/secrets/presence",
            json={"app_id": "thehub", "secret_ids": ["PRII_WRITE_TOKEN"]},
            headers=auth,
        )
        assert presence.status_code != 503, "secrets/presence is still unhosted"


def test_it_refuses_an_ephemeral_signing_key(tmp_path, monkeypatch):
    """Receipts signed by a key that dies with the process are not gate evidence."""
    monkeypatch.delenv(RECEIPT_SIGNING_KEY_ENV, raising=False)
    monkeypatch.setenv("PRII_MANAGER_SECRET_PROVIDER", "memory")

    with pytest.raises(HostRefused) as excinfo:
        build_runtime(tmp_path / "state", REPO_ROOT)
    assert RECEIPT_SIGNING_KEY_ENV in str(excinfo.value)


def test_it_refuses_without_a_bootstrap_nonce(monkeypatch, capsys):
    """Without the nonce, POST /session 503s and nothing can reach the surface."""
    monkeypatch.delenv("PRII_MANAGER_BOOTSTRAP_NONCE", raising=False)

    assert main([]) == 2
    assert "PRII_MANAGER_BOOTSTRAP_NONCE" in capsys.readouterr().err


def test_the_session_snippet_targets_the_key_the_client_reads():
    """The browser half of the same gap: sessionStorage is never populated.

    `managerClient.js` refuses when `prii.manager.session` is absent, and no SPA
    code performs the exchange. If the key here and the key there ever diverge,
    the operator gets 'Native manager session is unavailable' with no clue why.
    """
    from run_manager_host import _session_bootstrap_snippet

    snippet = _session_bootstrap_snippet(NONCE)
    client_js = (
        REPO_ROOT / "server" / "frontend" / "src" / "components" / "manager" / "managerClient.js"
    ).read_text(encoding="utf-8")

    assert 'SESSION_KEY = "prii.manager.session"' in client_js
    assert "prii.manager.session" in snippet
    assert NONCE in snippet
    assert "/api/federation-manager/session" in snippet
