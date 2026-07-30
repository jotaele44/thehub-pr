"""Headless clean-machine end-to-end harness for the Hub operations slice.

Gate G21 asks for a synthetic fixture proving the chain from a clean machine
through to rollback. This runs it headlessly on Linux against the *real*
installed `hub` console script -- not a mock -- so it exercises argv
construction, process supervision, transactions, and receipt chaining together.

Two substitutions are made and both are recorded rather than hidden:

* the secret provider is in-memory, because there is no OS keychain here;
* file tokens are minted directly rather than by a native picker, because
  there is no GUI.

Everything else is the production path. The macOS-operator half of the
certification (G15, G16, G17, G22) cannot be produced in this environment and
is recorded as blocked, not silently skipped.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("cryptography")

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
    evaluate_gates,
    summarize,
)
from server.backend.federation_manager_runner import OperationRunner  # noqa: E402
from server.backend.federation_manager_secrets import (  # noqa: E402
    InMemorySecretProvider,
    SecretBroker,
)
from server.backend.federation_manager_transactions import (  # noqa: E402
    Phase,
    sqlite_backup_integrity_check_atomic_swap,
    transaction,
)

PINNED_KEY_ID = "prii-operations-test-2026-07"
NOW = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)

RECEIPT_SCHEMA = json.loads(
    (REPO_ROOT / "schemas" / "execution_receipt.schema.json").read_text(encoding="utf-8")
)
POLICY_SCHEMA = json.loads(
    (REPO_ROOT / "schemas" / "signed_command_policy.schema.json").read_text(encoding="utf-8")
)

hub_installed = pytest.mark.skipif(
    shutil.which("hub") is None,
    reason="the `hub` console script is not installed; run `pip install -e .`",
)


@pytest.fixture
def machine(tmp_path):
    """A synthetic clean machine: managed roots and a fresh app root."""
    app_root = tmp_path / "apps" / "thehub" / "0.1.0"
    app_root.mkdir(parents=True)
    # The registry is the only app-root content hub.list needs.
    shutil.copytree(REPO_ROOT / "registry", app_root / "registry")

    for name in ("data", "staging", "intake", "receipts"):
        (tmp_path / name).mkdir()

    return {
        "root": tmp_path,
        "app_root": app_root,
        "data_root": tmp_path / "data",
        "staging_root": tmp_path / "staging",
    }


@pytest.fixture
def runner(machine):
    policy = verify_policy(
        load_policy_document(REPO_ROOT / "config" / "operations_policy.json"),
        schema=POLICY_SCHEMA,
        public_key_pem=(REPO_ROOT / "config" / "operations_policy_key.pub").read_bytes(),
        pinned_key_id=PINNED_KEY_ID,
        now=NOW,
    )
    return OperationRunner(
        policy=policy,
        context=ExecutionContext(
            app_root=machine["app_root"],
            data_root=machine["data_root"],
            staging_root=machine["staging_root"],
        ),
        receipts=ReceiptStore(
            machine["root"] / "receipts",
            ReceiptSigner.generate("prii-manager-e2e"),
            schema=RECEIPT_SCHEMA,
        ),
        files=FileTokenBroker(machine["root"] / "intake"),
        secrets=SecretBroker(InMemorySecretProvider()),
    )


def _make_aggregate(data_root: Path) -> Path:
    """A minimal but real aggregate directory for hub.ingest to consume."""
    aggregate = data_root / "aggregate"
    aggregate.mkdir(parents=True, exist_ok=True)
    (aggregate / "entities.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "federation_entity_v1",
                "entity_id": "e-1",
                "entity_type": "organization",
                "name": "Synthetic Org",
                "producer": "ovnis-pr",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return aggregate


# ── the chain ───────────────────────────────────────────────────────────────


@hub_installed
def test_configure_step_reports_machine_state(runner):
    """Clean-machine prerequisites are observed, not assumed."""
    checks = runner.prerequisites("thehub")
    names = {check["name"] for check in checks}
    assert "Signed operations policy" in names
    assert "Console script: hub" in names
    assert any(check["status"] == "met" for check in checks)
    for check in checks:
        if check["status"] == "unmet":
            assert check["remediation"], f"{check['name']} has no actionable step"


@hub_installed
def test_validate_step_runs_and_produces_a_verified_receipt(runner, machine):
    document = runner.run("hub.list", {}, session_token="e2e")
    receipt = document["receipt"]

    assert receipt["status"] == "succeeded"
    assert receipt["exit_code"] == 0
    assert receipt["argv_redacted"][:2] == ["hub", "list"]
    # A successful run reaches COMMIT and then RECEIPT, which is the last phase.
    assert receipt["transaction"]["phase_reached"] == Phase.RECEIPT.value

    handle = runner.handle(receipt["run_id"])
    assert handle.lines, "the run produced no streamed output"
    assert any("producers" in line for line in handle.lines)

    assert runner.receipts.verify_chain() == []


@hub_installed
def test_validate_package_consumes_a_brokered_file_token(runner, machine, tmp_path):
    """The file-token path end to end: mint, stage, preflight, argv, receipt."""
    package = tmp_path / "operator-package"
    package.mkdir()
    (package / "manifest.json").write_text(json.dumps({"schema_version": "x"}), encoding="utf-8")

    token = runner.files.mint(
        session_token="e2e", app_id="thehub", source_path=package / "manifest.json"
    )
    document = runner.run(
        "hub.validate_manifest", {}, session_token="e2e", file_tokens={"path": token}
    )
    receipt = document["receipt"]

    # The operator's own path never reaches the receipt.
    serialised = json.dumps(document)
    assert str(package) not in serialised
    assert receipt["inputs"][0]["logical_name"] == "manifest.json"
    assert len(receipt["inputs"][0]["sha256"]) == 64

    # argv carries the staged managed copy, not the original.
    staged_arg = receipt["argv_redacted"][-1]
    assert str(machine["root"] / "intake") in staged_arg


@hub_installed
def test_full_chain_produces_a_verifiable_receipt_chain(runner, machine):
    """configure -> validate -> aggregate -> ingest, chained and verified."""
    _make_aggregate(machine["data_root"])

    runner.run("hub.list", {}, session_token="e2e")
    runner.run("hub.graph_report", {"in_dir": "aggregate"}, session_token="e2e")
    runner.run("hub.ingest", {"in_dir": "aggregate"}, session_token="e2e")

    documents = runner.receipts.all_documents()
    assert len(documents) == 3
    assert runner.receipts.verify_chain() == []

    # Genesis has no predecessor; every later receipt names the one before it.
    digests = [d["signature"]["payload_sha256"] for d in documents]
    predecessors = [d["receipt"]["previous_receipt_sha256"] for d in documents]
    assert predecessors[0] is None
    assert predecessors[1:] == digests[:-1]


@hub_installed
def test_gates_derive_from_the_chain_and_stay_honest_about_what_is_blocked(runner, machine):
    _make_aggregate(machine["data_root"])
    runner.run("hub.list", {}, session_token="e2e")

    rules = [
        GateRule("G04_OPERATION_ACCOUNTING", "68 accounted", required_operations=["hub.list"]),
        GateRule(
            "G16_7_OF_7_UI_VALIDATION",
            "All seven apps validate through the UI",
            required_operations=["hub.list", "centinelas.test_suite"],
        ),
        GateRule(
            "G22_REAL_OPERATOR_MACOS",
            "Local macOS operator run",
            blocked_reason="No macOS host, GUI, or native picker is available in this environment.",
        ),
    ]
    evidence = evaluate_gates(
        rules,
        runner.receipts.all_documents(),
        public_key_pem=runner.receipts.signer.public_key_pem(),
        schema=RECEIPT_SCHEMA,
        policy_sha256=runner.policy.payload_sha256,
    )
    by_id = {gate["gate_id"]: gate for gate in evidence["gates"]}

    assert by_id["G04_OPERATION_ACCOUNTING"]["status"] == "passed"
    # Partial coverage must not pass: one producer receipt is missing.
    assert by_id["G16_7_OF_7_UI_VALIDATION"]["status"] == "not_run"
    assert "centinelas.test_suite" in by_id["G16_7_OF_7_UI_VALIDATION"]["status_reason"]
    assert by_id["G22_REAL_OPERATOR_MACOS"]["status"] == "blocked_not_certified"

    counts = summarize(evidence)
    assert counts["passed"] == 1


@hub_installed
def test_rollback_restores_the_database_after_a_forced_post_commit_failure(runner, machine):
    """The rollback half of G21, against a database a real run produced."""
    _make_aggregate(machine["data_root"])
    runner.run("hub.ingest", {"in_dir": "aggregate"}, session_token="e2e")

    database = machine["data_root"] / "hub.db"
    assert database.exists(), "the ingest run did not produce a database"

    import sqlite3

    from server.backend.federation_manager_transactions import count_rows, integrity_check

    def dump(path: Path) -> list:
        connection = sqlite3.connect(str(path))
        try:
            return connection.execute(
                "SELECT entity_type, entity_id, data FROM entities ORDER BY 1, 2"
            ).fetchall()
        finally:
            connection.close()

    # Compared logically rather than by file digest: SQLite's backup API
    # rewrites page layout, so a correctly restored database is byte-different
    # from the original while holding exactly the same rows. Asserting on bytes
    # would fail a rollback that in fact worked.
    before_rows = count_rows(database)
    before_dump = dump(database)

    class Forced(RuntimeError):
        pass

    def wipe(staged: Path) -> None:
        import sqlite3

        connection = sqlite3.connect(str(staged))
        try:
            connection.execute("DELETE FROM entities")
            connection.execute(
                "INSERT OR REPLACE INTO entities VALUES ('X','x','{}','2026-01-01')"
            )
            connection.commit()
        finally:
            connection.close()

    with pytest.raises(Forced):
        with transaction("sqlite_backup_integrity_check_atomic_swap", machine["staging_root"]) as tx:
            sqlite_backup_integrity_check_atomic_swap(tx, database=database, mutate=wipe)
            raise Forced("injected failure after the atomic swap")

    assert count_rows(database) == before_rows
    assert dump(database) == before_dump
    assert integrity_check(database)


@hub_installed
def test_a_failed_run_is_recorded_rather_than_lost(runner, machine):
    """A run against a directory that does not exist still leaves evidence."""
    document = runner.run("hub.graph_report", {"in_dir": "does-not-exist"}, session_token="e2e")
    assert document["receipt"]["status"] in {"failed", "succeeded"}
    assert runner.receipts.verify_chain() == []


@hub_installed
def test_no_secret_appears_anywhere_in_the_evidence(runner, machine):
    """G18 against the artifacts a real chain produced."""
    canary = "prii-canary-e2e-3f81ba9c"
    runner.secrets.set("thehub", "PRII_WRITE_TOKEN", canary)

    _make_aggregate(machine["data_root"])
    runner.run("hub.list", {}, session_token="e2e")
    runner.run("hub.graph_report", {"in_dir": "aggregate"}, session_token="e2e")

    for document in runner.receipts.all_documents():
        assert canary not in json.dumps(document)
    for path in (machine["root"] / "receipts").rglob("*"):
        if path.is_file():
            assert canary not in path.read_text(encoding="utf-8", errors="replace")
    for run_id in [d["receipt"]["run_id"] for d in runner.receipts.all_documents()]:
        handle = runner.handle(run_id)
        if handle:
            assert canary not in "".join(handle.lines)


@hub_installed
def test_staging_and_intake_are_left_clean(runner, machine, tmp_path):
    """A finished run leaves no staged copies of operator data behind."""
    source = tmp_path / "picked.json"
    source.write_text("{}", encoding="utf-8")
    token = runner.files.mint(session_token="e2e", app_id="thehub", source_path=source)
    runner.run("hub.validate_manifest", {}, session_token="e2e", file_tokens={"path": token})

    leftover_staging = list(machine["staging_root"].iterdir())
    assert leftover_staging == [], f"staging not cleaned: {leftover_staging}"
