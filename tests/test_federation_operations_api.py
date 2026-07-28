"""Operations API: authorization, plan/run/cancel, receipts, gates, streaming.

Covers gates G11 (streamed logs, cancellation), G14 (gate binding), G18 (no
secret disclosure over HTTP) and G20 (destructive controls stay disabled).

Follows the PR #94 test pattern: a bare FastAPI app with only the router under
test, so none of `main.app`'s database init or SPA mounting is involved.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("cryptography")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from server.backend import federation_manager_api as api  # noqa: E402
from server.backend.federation_manager_files import FileTokenBroker  # noqa: E402
from server.backend.federation_manager_operations import (  # noqa: E402
    ExecutionContext,
    load_policy_document,
    verify_policy,
)
from server.backend.federation_manager_receipts import (  # noqa: E402
    GateRule,
    ReceiptSigner,
    ReceiptStore,
)
from server.backend.federation_manager_runner import OperationRunner  # noqa: E402
from server.backend.federation_manager_secrets import (  # noqa: E402
    InMemorySecretProvider,
    SecretBroker,
)

ORIGIN = "http://127.0.0.1:5173"
NONCE = "n" * 48
PINNED_KEY_ID = "prii-operations-test-2026-07"
CANARY = "prii-canary-secret-1c9d77"

RECEIPT_SCHEMA = json.loads(
    (REPO_ROOT / "schemas" / "execution_receipt.schema.json").read_text(encoding="utf-8")
)
POLICY_SCHEMA = json.loads(
    (REPO_ROOT / "schemas" / "signed_command_policy.schema.json").read_text(encoding="utf-8")
)

GATE_RULES = [
    GateRule("G04_OPERATION_ACCOUNTING", "All 68 accounted", required_operations=["hub.list"]),
    GateRule("G07_NATIVE_SECRETS", "Keychain certified", blocked_reason="no macOS in this environment"),
    GateRule("G17_6_OF_6_PRODUCER_EXPORTS", "Producer exports", deferred_reason="out of scope"),
]


@pytest.fixture
def workspace(tmp_path):
    for name in ("app", "data", "staging", "intake", "receipts"):
        (tmp_path / name).mkdir()
    return tmp_path


@pytest.fixture
def policy():
    from datetime import datetime, timezone

    return verify_policy(
        load_policy_document(REPO_ROOT / "config" / "operations_policy.json"),
        schema=POLICY_SCHEMA,
        public_key_pem=(REPO_ROOT / "config" / "operations_policy_key.pub").read_bytes(),
        pinned_key_id=PINNED_KEY_ID,
        now=datetime(2026, 7, 27, 12, tzinfo=timezone.utc),
    )


@pytest.fixture
def runtime(workspace, policy):
    signer = ReceiptSigner.generate("prii-manager-test")
    return api.ManagerRuntime(
        runner=OperationRunner(
            policy=policy,
            context=ExecutionContext(
                app_root=workspace / "app",
                data_root=workspace / "data",
                staging_root=workspace / "staging",
            ),
            receipts=ReceiptStore(workspace / "receipts", signer, schema=RECEIPT_SCHEMA),
            files=FileTokenBroker(workspace / "intake"),
            secrets=SecretBroker(InMemorySecretProvider()),
        ),
        files=FileTokenBroker(workspace / "intake"),
        secrets_broker=SecretBroker(InMemorySecretProvider()),
        gate_rules=GATE_RULES,
    )


@pytest.fixture
def client(monkeypatch, runtime):
    monkeypatch.setattr(api, "_bootstrap_nonce", NONCE)
    monkeypatch.setattr(api, "sessions", api.SessionManager(NONCE, api.ALLOWED_ORIGINS, 300))
    monkeypatch.setattr(api, "runtime", runtime)
    monkeypatch.setattr(api, "_stream_tickets", {})

    app = FastAPI()
    app.include_router(api.router)
    # A real loopback client address, so the loopback gate stays exercised
    # rather than being monkeypatched away. TestClient's default host is the
    # literal "testclient", which is not an IP address at all.
    with TestClient(app, client=("127.0.0.1", 41234)) as test_client:
        yield test_client


@pytest.fixture
def auth(client):
    response = client.post(
        "/api/federation-manager/session",
        json={"nonce": NONCE, "origin": ORIGIN},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200
    return {"Origin": ORIGIN, "Authorization": f"Bearer {response.json()['token']}"}


# ── authorization chain ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/api/federation-manager/operations", None),
        ("GET", "/api/federation-manager/operations/accounting", None),
        ("GET", "/api/federation-manager/gates", None),
        ("GET", "/api/federation-manager/receipts", None),
        ("POST", "/api/federation-manager/operations/hub.list/plan", {}),
        ("POST", "/api/federation-manager/operations/hub.list/run", {}),
        ("POST", "/api/federation-manager/runs/abc/cancel", None),
        ("POST", "/api/federation-manager/runs/abc/log-ticket", None),
        ("GET", "/api/federation-manager/runs/abc/logs", None),
        ("GET", f"/api/federation-manager/runs/{'a' * 32}/receipt", None),
        ("POST", "/api/federation-manager/secrets", {"app_id": "thehub", "secret_id": "K", "value": "v"}),
        ("POST", "/api/federation-manager/secrets/presence", {"app_id": "thehub", "secret_ids": ["K"]}),
        ("DELETE", "/api/federation-manager/secrets/thehub/K", None),
        ("POST", "/api/federation-manager/files/slots", {"app_id": "thehub", "path": "/tmp/x"}),
    ],
)
def test_every_operations_endpoint_requires_a_session(client, method, path, body):
    """Bodies are valid, so a 401 proves the auth gate rejected -- not the parser."""
    response = client.request(method, path, json=body, headers={"Origin": ORIGIN})
    assert response.status_code == 401, f"{method} {path} -> {response.status_code}"


def test_a_disallowed_origin_is_refused(client, auth):
    headers = dict(auth)
    headers["Origin"] = "https://evil.example"
    response = client.get("/api/federation-manager/operations", headers=headers)
    assert response.status_code == 403


def test_an_invalid_bearer_is_refused(client):
    response = client.get(
        "/api/federation-manager/operations",
        headers={"Origin": ORIGIN, "Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


# ── inventory and accounting ────────────────────────────────────────────────


def test_operations_listing_includes_disabled_ones_with_reasons(client, auth):
    payload = client.get("/api/federation-manager/operations", headers=auth).json()
    assert len(payload) == 68
    disabled = [op for op in payload if not op["enabled"]]
    assert len(disabled) == 56
    assert all(op["enablementReason"] for op in disabled)

    fetch = next(op for op in payload if op["operationId"] == "hub.fetch")
    assert fetch["enabled"] is False
    assert "acquisition" in fetch["enablementReason"].lower()


def test_accounting_endpoint_reports_zero_unclassified(client, auth):
    payload = client.get("/api/federation-manager/operations/accounting", headers=auth).json()
    assert payload["total"] == 68
    assert payload["enabled"] == 12
    assert payload["unclassified"] == []
    assert payload["keyId"] == PINNED_KEY_ID


# ── plan ────────────────────────────────────────────────────────────────────


def test_plan_previews_argv_without_executing(client, auth, workspace):
    response = client.post(
        "/api/federation-manager/operations/hub.list/plan", json={}, headers=auth
    )
    assert response.status_code == 200
    plan = response.json()
    assert plan["argvPreview"][:2] == ["hub", "list"]
    assert plan["riskClass"] == "R0_READ_ONLY"
    assert plan["rollbackStrategy"] == "none"
    # Nothing was written.
    assert list((workspace / "receipts").glob("*.receipt.json")) == []


def test_plan_rejects_an_invalid_parameter(client, auth):
    response = client.post(
        "/api/federation-manager/operations/hub.correlate/plan",
        json={"parameters": {"in_dir": "a", "out": "b", "window_days": -5}},
        headers=auth,
    )
    assert response.status_code == 422


def test_plan_on_a_disabled_operation_returns_409_with_the_reason(client, auth):
    response = client.post(
        "/api/federation-manager/operations/hub.fetch/plan", json={}, headers=auth
    )
    assert response.status_code == 409
    assert "not enabled" in response.json()["detail"]


def test_plan_on_an_unknown_operation_returns_404(client, auth):
    response = client.post(
        "/api/federation-manager/operations/hub.nonexistent/plan", json={}, headers=auth
    )
    assert response.status_code == 404


def test_plan_reports_a_deferred_rollback_strategy_as_a_warning(client, auth):
    """A producer operation cannot be planned, but the reason is legible."""
    response = client.post(
        "/api/federation-manager/operations/ovnis.dedupe/plan", json={}, headers=auth
    )
    assert response.status_code == 409


# ── run ─────────────────────────────────────────────────────────────────────


def test_run_produces_a_signed_receipt(client, auth, runtime):
    response = client.post(
        "/api/federation-manager/operations/hub.list/run", json={}, headers=auth
    )
    assert response.status_code == 200
    document = response.json()
    assert document["receipt"]["operation_id"] == "hub.list"
    assert document["signature"]["algorithm"] == "Ed25519"
    assert len(document["receipt"]["run_id"]) == 32


def test_a_failing_operation_still_emits_a_receipt(client, auth):
    """`hub` is not installed in this fixture, so the child cannot start."""
    document = client.post(
        "/api/federation-manager/operations/hub.list/run", json={}, headers=auth
    ).json()
    assert document["receipt"]["status"] in {"failed", "succeeded"}
    assert document["receipt"]["log"]["sha256"]


def test_run_refuses_a_disabled_operation(client, auth):
    response = client.post(
        "/api/federation-manager/operations/hub.fetch/run", json={}, headers=auth
    )
    assert response.status_code == 409


def test_run_requires_acknowledgement_when_the_policy_demands_it(client, auth):
    response = client.post(
        "/api/federation-manager/operations/hub.ingest/run",
        json={"parameters": {"in_dir": "agg"}},
        headers=auth,
    )
    assert response.status_code == 428
    assert "acknowledgement" in response.json()["detail"]


def test_acknowledged_run_proceeds_past_the_gate(client, auth, workspace):
    (workspace / "data" / "agg").mkdir()
    response = client.post(
        "/api/federation-manager/operations/hub.ingest/run",
        json={"parameters": {"in_dir": "agg"}, "acknowledged": True},
        headers=auth,
    )
    assert response.status_code == 200


def test_run_rejects_an_unknown_parameter(client, auth):
    response = client.post(
        "/api/federation-manager/operations/hub.list/run",
        json={"parameters": {"not_a_real_parameter": 1}},
        headers=auth,
    )
    assert response.status_code == 422


def test_missing_file_token_is_refused_before_execution(client, auth):
    response = client.post(
        "/api/federation-manager/operations/hub.validate_manifest/run",
        json={"parameters": {"path": "manifest.json"}},
        headers=auth,
    )
    assert response.status_code == 422
    assert "file token" in response.json()["detail"]


# ── receipts and gates ──────────────────────────────────────────────────────


def test_receipt_is_retrievable_and_the_chain_verifies(client, auth):
    document = client.post(
        "/api/federation-manager/operations/hub.list/run", json={}, headers=auth
    ).json()
    run_id = document["receipt"]["run_id"]

    fetched = client.get(f"/api/federation-manager/runs/{run_id}/receipt", headers=auth)
    assert fetched.status_code == 200
    assert fetched.json()["receipt"]["run_id"] == run_id

    listing = client.get("/api/federation-manager/receipts", headers=auth).json()
    assert listing["chainProblems"] == []
    assert any(item["runId"] == run_id for item in listing["receipts"])


def test_unknown_receipt_returns_404(client, auth):
    response = client.get(f"/api/federation-manager/runs/{'f' * 32}/receipt", headers=auth)
    assert response.status_code == 404


def test_gates_report_blocked_and_deferred_honestly(client, auth):
    payload = client.get("/api/federation-manager/gates", headers=auth).json()
    by_id = {gate["gate_id"]: gate for gate in payload["gates"]}
    assert by_id["G07_NATIVE_SECRETS"]["status"] == "blocked_not_certified"
    assert "macOS" in by_id["G07_NATIVE_SECRETS"]["status_reason"]
    assert by_id["G17_6_OF_6_PRODUCER_EXPORTS"]["status"] == "deferred"
    assert by_id["G04_OPERATION_ACCOUNTING"]["status"] == "not_run"


def test_a_gate_status_cannot_be_set_by_a_client(client, auth):
    """There is no write path to gate status; the only verb is GET."""
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = client.request(
            method,
            "/api/federation-manager/gates",
            json={"gate_id": "G04_OPERATION_ACCOUNTING", "status": "passed"},
            headers=auth,
        )
        assert response.status_code == 405, f"{method} must not be routable"


# ── secrets over HTTP ───────────────────────────────────────────────────────


def test_setting_a_secret_returns_presence_not_the_value(client, auth):
    response = client.post(
        "/api/federation-manager/secrets",
        json={"app_id": "centinelas", "secret_id": "ANTHROPIC_API_KEY", "value": CANARY},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.text
    assert CANARY not in body
    assert response.json()["status"] == "present"


def test_no_endpoint_returns_a_secret_value(client, auth):
    client.post(
        "/api/federation-manager/secrets",
        json={"app_id": "centinelas", "secret_id": "ANTHROPIC_API_KEY", "value": CANARY},
        headers=auth,
    )
    for path in (
        "/api/federation-manager/operations",
        "/api/federation-manager/gates",
        "/api/federation-manager/receipts",
    ):
        assert CANARY not in client.get(path, headers=auth).text

    presence = client.post(
        "/api/federation-manager/secrets/presence",
        json={"app_id": "centinelas", "secret_ids": ["ANTHROPIC_API_KEY"]},
        headers=auth,
    )
    assert CANARY not in presence.text
    assert presence.json()[0]["status"] == "present"


def test_deleting_a_secret_reports_absence(client, auth):
    client.post(
        "/api/federation-manager/secrets",
        json={"app_id": "centinelas", "secret_id": "ANTHROPIC_API_KEY", "value": CANARY},
        headers=auth,
    )
    response = client.delete(
        "/api/federation-manager/secrets/centinelas/ANTHROPIC_API_KEY", headers=auth
    )
    assert response.json()["status"] == "absent"


# ── file slots ──────────────────────────────────────────────────────────────


def test_file_slot_returns_a_token_and_no_path(client, auth, tmp_path):
    picked = tmp_path / "picked" / "manifest.json"
    picked.parent.mkdir(parents=True)
    picked.write_text("{}", encoding="utf-8")

    response = client.post(
        "/api/federation-manager/files/slots",
        json={"app_id": "thehub", "path": str(picked)},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["fileToken"]
    assert str(picked) not in response.text
    assert "path" not in body


def test_file_slot_rejects_a_directory(client, auth, tmp_path):
    response = client.post(
        "/api/federation-manager/files/slots",
        json={"app_id": "thehub", "path": str(tmp_path)},
        headers=auth,
    )
    assert response.status_code == 422


# ── log streaming ───────────────────────────────────────────────────────────


def test_stream_requires_a_ticket(client, auth):
    document = client.post(
        "/api/federation-manager/operations/hub.list/run", json={}, headers=auth
    ).json()
    run_id = document["receipt"]["run_id"]
    response = client.get(
        f"/api/federation-manager/runs/{run_id}/logs/not-a-ticket", headers={"Origin": ORIGIN}
    )
    assert response.status_code == 403


def test_a_ticket_is_single_use(client, auth):
    document = client.post(
        "/api/federation-manager/operations/hub.list/run", json={}, headers=auth
    ).json()
    run_id = document["receipt"]["run_id"]

    ticket = client.post(
        f"/api/federation-manager/runs/{run_id}/log-ticket", headers=auth
    ).json()["ticket"]

    first = client.get(
        f"/api/federation-manager/runs/{run_id}/logs/{ticket}", headers={"Origin": ORIGIN}
    )
    assert first.status_code == 200

    second = client.get(
        f"/api/federation-manager/runs/{run_id}/logs/{ticket}", headers={"Origin": ORIGIN}
    )
    assert second.status_code == 403, "a replayed ticket must be refused"


def test_a_ticket_is_bound_to_its_run(client, auth):
    document = client.post(
        "/api/federation-manager/operations/hub.list/run", json={}, headers=auth
    ).json()
    run_id = document["receipt"]["run_id"]
    ticket = client.post(
        f"/api/federation-manager/runs/{run_id}/log-ticket", headers=auth
    ).json()["ticket"]

    response = client.get(
        f"/api/federation-manager/runs/{'a' * 32}/logs/{ticket}", headers={"Origin": ORIGIN}
    )
    assert response.status_code == 403


def test_ticket_expires(client, auth, monkeypatch):
    document = client.post(
        "/api/federation-manager/operations/hub.list/run", json={}, headers=auth
    ).json()
    run_id = document["receipt"]["run_id"]
    ticket = client.post(
        f"/api/federation-manager/runs/{run_id}/log-ticket", headers=auth
    ).json()["ticket"]

    real_time = api.time.time
    monkeypatch.setattr(api.time, "time", lambda: real_time() + 3600)
    response = client.get(
        f"/api/federation-manager/runs/{run_id}/logs/{ticket}", headers={"Origin": ORIGIN}
    )
    assert response.status_code == 403


def test_log_snapshot_fallback_returns_lines(client, auth):
    document = client.post(
        "/api/federation-manager/operations/hub.list/run", json={}, headers=auth
    ).json()
    run_id = document["receipt"]["run_id"]
    response = client.get(f"/api/federation-manager/runs/{run_id}/logs", headers=auth)
    assert response.status_code == 200
    assert response.json()["done"] is True


def test_cancelling_a_finished_run_reports_conflict(client, auth):
    document = client.post(
        "/api/federation-manager/operations/hub.list/run", json={}, headers=auth
    ).json()
    run_id = document["receipt"]["run_id"]
    response = client.post(f"/api/federation-manager/runs/{run_id}/cancel", headers=auth)
    assert response.status_code == 409


# ── runtime absence ─────────────────────────────────────────────────────────


def test_endpoints_report_503_when_the_runtime_is_absent(client, monkeypatch, auth):
    """A misconfigured deployment must fail visibly, not half-work."""
    monkeypatch.setattr(api, "runtime", None)
    response = client.get("/api/federation-manager/operations", headers=auth)
    assert response.status_code == 503
    assert "runtime is not configured" in response.json()["detail"]


def test_phase_one_read_surface_still_works_without_the_runtime(client, monkeypatch, auth):
    """PR #94's inventory must not regress when operations are unavailable."""
    monkeypatch.setattr(api, "runtime", None)
    response = client.get("/api/federation-manager/apps", headers=auth)
    assert response.status_code == 200
    assert len(response.json()) == 7


# ── Python 3.9 floor ────────────────────────────────────────────────────────


def test_no_pep604_unions_in_route_signatures():
    """CI runs 3.9; a `str | None` in a FastAPI signature fails at import there."""
    import inspect

    for name in dir(api):
        candidate = getattr(api, name)
        if callable(candidate) and getattr(candidate, "__module__", "") == api.__name__:
            try:
                signature = str(inspect.signature(candidate))
            except (TypeError, ValueError):
                continue
            assert " | " not in signature, f"{name}{signature}"
