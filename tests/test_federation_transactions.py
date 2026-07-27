"""Transactions, atomic rollback, and forced-failure injection.

Covers gate G13. The spec requires failure injected at every boundary, with
each test proving either *no visible state change* or *complete restoration* --
never a half-applied write.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.backend.federation_manager_files import sha256_file  # noqa: E402
from server.backend.federation_manager_transactions import (  # noqa: E402
    UNIMPLEMENTED_STRATEGIES,
    Phase,
    RollbackFailed,
    RollbackState,
    TransactionError,
    count_rows,
    current_pointer,
    file_snapshot_restore,
    integrity_check,
    ledger_snapshot_restore,
    promote_version,
    prune_old_versions,
    require_strategy,
    restore,
    rollback_version,
    run_partition_restore,
    snapshot_file,
    snapshot_ledger,
    snapshot_sqlite,
    sqlite_backup_integrity_check_atomic_swap,
    stage_validate_atomic_promote,
    transaction,
    versioned_install_pointer_swap,
    write_atomic,
)


class InjectedFailure(RuntimeError):
    """Marker for a deliberately injected fault."""


@pytest.fixture
def staging(tmp_path):
    return tmp_path / "staging"


# ── write_atomic ────────────────────────────────────────────────────────────


def test_write_atomic_creates_the_file(tmp_path):
    target = tmp_path / "nested" / "out.json"
    write_atomic(target, '{"a": 1}')
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}


def test_write_atomic_replaces_contents_wholesale(tmp_path):
    target = tmp_path / "out.txt"
    write_atomic(target, "original")
    write_atomic(target, "replacement")
    assert target.read_text(encoding="utf-8") == "replacement"


def test_write_atomic_leaves_no_temp_files_behind(tmp_path):
    target = tmp_path / "out.txt"
    write_atomic(target, "x")
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "out.txt"]
    assert leftovers == []


def test_write_atomic_cleans_up_when_writing_fails(tmp_path):
    target = tmp_path / "out.txt"

    with pytest.raises(TypeError):
        write_atomic(target, 12345)  # type: ignore[arg-type]
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_write_atomic_preserves_the_old_file_when_the_new_write_raises(tmp_path):
    target = tmp_path / "out.txt"
    write_atomic(target, "original")
    with pytest.raises(TypeError):
        write_atomic(target, object())  # type: ignore[arg-type]
    assert target.read_text(encoding="utf-8") == "original"


def test_write_atomic_accepts_bytes(tmp_path):
    target = tmp_path / "out.bin"
    write_atomic(target, b"\x00\x01\x02")
    assert target.read_bytes() == b"\x00\x01\x02"


# ── snapshots and restore ───────────────────────────────────────────────────


def test_snapshot_records_absence_so_rollback_deletes(tmp_path, staging):
    target = tmp_path / "created-by-run.json"
    snapshot = snapshot_file(target, staging)
    assert snapshot.existed is False

    target.write_text("{}", encoding="utf-8")
    restore(snapshot)
    assert not target.exists(), "rollback must delete a file the run created"


def test_snapshot_restores_prior_contents(tmp_path, staging):
    target = tmp_path / "data.json"
    target.write_text('{"before": true}', encoding="utf-8")
    snapshot = snapshot_file(target, staging)

    target.write_text('{"after": true}', encoding="utf-8")
    restore(snapshot)
    assert json.loads(target.read_text(encoding="utf-8")) == {"before": True}


def test_restore_detects_a_corrupted_backup(tmp_path, staging):
    target = tmp_path / "data.json"
    target.write_text("original", encoding="utf-8")
    snapshot = snapshot_file(target, staging)

    snapshot.backup.write_text("tampered", encoding="utf-8")
    with pytest.raises(RollbackFailed, match="does not match its snapshot digest"):
        restore(snapshot)


def test_restore_fails_loudly_when_the_backup_vanished(tmp_path, staging):
    target = tmp_path / "data.json"
    target.write_text("original", encoding="utf-8")
    snapshot = snapshot_file(target, staging)
    snapshot.backup.unlink()
    with pytest.raises(RollbackFailed, match="missing its backup"):
        restore(snapshot)


def test_ledger_snapshot_records_row_count(tmp_path, staging):
    ledger = tmp_path / "signals.jsonl"
    ledger.write_text('{"a":1}\n{"a":2}\n\n{"a":3}\n', encoding="utf-8")
    snapshot = snapshot_ledger(ledger, staging)
    assert snapshot.row_count == 3, "blank lines are not rows"


# ── stage_validate_atomic_promote ───────────────────────────────────────────


def test_staged_promote_writes_the_output(tmp_path, staging):
    target = tmp_path / "analytics.json"
    with transaction("stage_validate_atomic_promote", staging) as tx:
        stage_validate_atomic_promote(
            tx, target=target, produce=lambda p: p.write_text('{"ok":1}', encoding="utf-8")
        )
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": 1}


def test_failure_during_production_leaves_no_visible_change(tmp_path, staging):
    target = tmp_path / "analytics.json"
    target.write_text('{"original": true}', encoding="utf-8")
    before = sha256_file(target)

    def explode(path):
        path.write_text("partial", encoding="utf-8")
        raise InjectedFailure("mid-process")

    with pytest.raises(InjectedFailure):
        with transaction("stage_validate_atomic_promote", staging) as tx:
            stage_validate_atomic_promote(tx, target=target, produce=explode)

    assert sha256_file(target) == before


def test_failure_during_validation_leaves_no_visible_change(tmp_path, staging):
    target = tmp_path / "analytics.json"
    target.write_text('{"original": true}', encoding="utf-8")
    before = sha256_file(target)

    def reject(path):
        raise InjectedFailure("validation rejected the staged output")

    with pytest.raises(InjectedFailure):
        with transaction("stage_validate_atomic_promote", staging) as tx:
            stage_validate_atomic_promote(
                tx,
                target=target,
                produce=lambda p: p.write_text("new", encoding="utf-8"),
                validate=reject,
            )

    assert sha256_file(target) == before


def test_failure_after_commit_restores_the_previous_content(tmp_path, staging):
    target = tmp_path / "analytics.json"
    target.write_text('{"original": true}', encoding="utf-8")
    before = sha256_file(target)

    with pytest.raises(InjectedFailure):
        with transaction("stage_validate_atomic_promote", staging) as tx:
            stage_validate_atomic_promote(
                tx, target=target, produce=lambda p: p.write_text('{"new": 1}', encoding="utf-8")
            )
            assert target.read_text(encoding="utf-8") == '{"new": 1}'
            raise InjectedFailure("blew up after the pointer swap")

    assert sha256_file(target) == before
    assert json.loads(target.read_text(encoding="utf-8")) == {"original": True}


def test_failure_after_commit_when_the_target_is_new_deletes_it(tmp_path, staging):
    target = tmp_path / "brand-new.json"
    with pytest.raises(InjectedFailure):
        with transaction("stage_validate_atomic_promote", staging) as tx:
            stage_validate_atomic_promote(
                tx, target=target, produce=lambda p: p.write_text("{}", encoding="utf-8")
            )
            raise InjectedFailure("after commit")
    assert not target.exists()


def test_staging_is_always_discarded(tmp_path, staging):
    target = tmp_path / "out.json"
    with transaction("stage_validate_atomic_promote", staging) as tx:
        run_staging = tx.staging
        stage_validate_atomic_promote(
            tx, target=target, produce=lambda p: p.write_text("{}", encoding="utf-8")
        )
    assert not run_staging.exists()


def test_phase_is_recorded_at_the_point_of_failure(tmp_path, staging):
    target = tmp_path / "out.json"
    captured = {}

    with pytest.raises(InjectedFailure):
        with transaction("stage_validate_atomic_promote", staging) as tx:
            captured["tx"] = tx
            stage_validate_atomic_promote(
                tx,
                target=target,
                produce=lambda p: p.write_text("{}", encoding="utf-8"),
                validate=lambda p: (_ for _ in ()).throw(InjectedFailure("no")),
            )

    assert captured["tx"].record.phase_reached == Phase.VALIDATE


# ── SQLite ──────────────────────────────────────────────────────────────────


def _make_db(path: Path, rows: int) -> None:
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS entities ("
            "entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, "
            "data TEXT NOT NULL, updated_at TEXT NOT NULL, "
            "PRIMARY KEY (entity_type, entity_id))"
        )
        for i in range(rows):
            connection.execute(
                "INSERT OR REPLACE INTO entities VALUES (?,?,?,?)",
                ("Thing", f"id-{i}", "{}", "2026-01-01"),
            )
        connection.commit()
    finally:
        connection.close()


def test_sqlite_swap_commits_a_valid_mutation(tmp_path, staging):
    db = tmp_path / "hub.db"
    _make_db(db, 3)

    def mutate(staged):
        _make_db(staged, 7)

    with transaction("sqlite_backup_integrity_check_atomic_swap", staging) as tx:
        sqlite_backup_integrity_check_atomic_swap(tx, database=db, mutate=mutate)

    assert count_rows(db) == 7
    assert integrity_check(db)


def test_sqlite_failure_mid_mutation_leaves_the_database_untouched(tmp_path, staging):
    db = tmp_path / "hub.db"
    _make_db(db, 3)
    before = sha256_file(db)

    def mutate(staged):
        _make_db(staged, 99)
        raise InjectedFailure("ingest crashed")

    with pytest.raises(InjectedFailure):
        with transaction("sqlite_backup_integrity_check_atomic_swap", staging) as tx:
            sqlite_backup_integrity_check_atomic_swap(tx, database=db, mutate=mutate)

    assert sha256_file(db) == before
    assert count_rows(db) == 3


def test_sqlite_corrupt_staged_database_is_refused(tmp_path, staging):
    db = tmp_path / "hub.db"
    _make_db(db, 3)
    before = sha256_file(db)

    def corrupt(staged):
        staged.write_bytes(b"this is not a database")

    with pytest.raises(TransactionError, match="integrity_check"):
        with transaction("sqlite_backup_integrity_check_atomic_swap", staging) as tx:
            sqlite_backup_integrity_check_atomic_swap(tx, database=db, mutate=corrupt)

    assert sha256_file(db) == before


def test_sqlite_row_floor_is_enforced(tmp_path, staging):
    """A mutation that silently drops rows must not be promoted."""
    db = tmp_path / "hub.db"
    _make_db(db, 10)
    before = sha256_file(db)

    def delete_most(staged: Path) -> None:
        connection = sqlite3.connect(str(staged))
        try:
            connection.execute("DELETE FROM entities WHERE entity_id != 'id-0'")
            connection.commit()
        finally:
            connection.close()

    with pytest.raises(TransactionError, match="expected at least"):
        with transaction("sqlite_backup_integrity_check_atomic_swap", staging) as tx:
            sqlite_backup_integrity_check_atomic_swap(
                tx, database=db, mutate=delete_most, expected_min_rows=10
            )

    assert count_rows(db) == 10
    assert sha256_file(db) == before


def test_sqlite_failure_after_commit_restores_from_the_backup(tmp_path, staging):
    db = tmp_path / "hub.db"
    _make_db(db, 4)

    with pytest.raises(InjectedFailure):
        with transaction("sqlite_backup_integrity_check_atomic_swap", staging) as tx:
            sqlite_backup_integrity_check_atomic_swap(
                tx, database=db, mutate=lambda staged: _make_db(staged, 40)
            )
            assert count_rows(db) == 40
            raise InjectedFailure("after swap")

    assert count_rows(db) == 4
    assert integrity_check(db)


def test_snapshot_sqlite_uses_the_backup_api(tmp_path, staging):
    db = tmp_path / "hub.db"
    _make_db(db, 5)
    snapshot = snapshot_sqlite(db, staging)
    assert snapshot.existed and snapshot.backup.exists()
    assert count_rows(snapshot.backup) == 5
    assert integrity_check(snapshot.backup)


# ── ledgers ─────────────────────────────────────────────────────────────────


def test_ledger_rewrite_commits(tmp_path, staging):
    ledger = tmp_path / "signals.jsonl"
    ledger.write_text('{"a":1}\n', encoding="utf-8")

    with transaction("ledger_snapshot_restore", staging) as tx:
        ledger_snapshot_restore(
            tx, ledger=ledger, produce=lambda p: p.write_text('{"a":1}\n{"a":2}\n', encoding="utf-8")
        )

    assert ledger.read_text(encoding="utf-8").count("\n") == 2


def test_ledger_row_loss_is_refused(tmp_path, staging):
    ledger = tmp_path / "signals.jsonl"
    ledger.write_text('{"a":1}\n{"a":2}\n{"a":3}\n', encoding="utf-8")
    before = sha256_file(ledger)

    with pytest.raises(TransactionError, match="would lose rows"):
        with transaction("ledger_snapshot_restore", staging) as tx:
            ledger_snapshot_restore(
                tx, ledger=ledger, produce=lambda p: p.write_text('{"a":1}\n', encoding="utf-8")
            )

    assert sha256_file(ledger) == before


def test_ledger_row_loss_is_allowed_when_intended(tmp_path, staging):
    ledger = tmp_path / "signals.jsonl"
    ledger.write_text('{"a":1}\n{"a":2}\n{"a":3}\n', encoding="utf-8")

    with transaction("ledger_snapshot_restore", staging) as tx:
        ledger_snapshot_restore(
            tx,
            ledger=ledger,
            produce=lambda p: p.write_text('{"a":1}\n', encoding="utf-8"),
            allow_row_loss=True,
        )

    assert ledger.read_text(encoding="utf-8") == '{"a":1}\n'


# ── versioned install ───────────────────────────────────────────────────────


def test_install_promotes_the_new_version(tmp_path, staging):
    apps = tmp_path / "apps"
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "app.py").write_text("print('hi')", encoding="utf-8")

    with transaction("versioned_install_pointer_swap", staging) as tx:
        versioned_install_pointer_swap(
            tx, apps_root=apps, app_id="thehub", version="1.0.0", payload=payload
        )

    assert current_pointer(apps, "thehub").read_text(encoding="utf-8") == "1.0.0"
    assert (apps / "thehub" / "1.0.0" / "app.py").exists()


def test_failed_smoke_test_never_promotes(tmp_path, staging):
    apps = tmp_path / "apps"
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "app.py").write_text("x", encoding="utf-8")

    promote_version(apps, "thehub", "1.0.0")
    (apps / "thehub" / "1.0.0").mkdir(parents=True, exist_ok=True)

    with pytest.raises(InjectedFailure):
        with transaction("versioned_install_pointer_swap", staging) as tx:
            versioned_install_pointer_swap(
                tx,
                apps_root=apps,
                app_id="thehub",
                version="2.0.0",
                payload=payload,
                smoke_test=lambda p: (_ for _ in ()).throw(InjectedFailure("smoke failed")),
            )

    assert current_pointer(apps, "thehub").read_text(encoding="utf-8") == "1.0.0"


def test_failure_after_pointer_swap_rolls_the_pointer_back(tmp_path, staging):
    apps = tmp_path / "apps"
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "app.py").write_text("x", encoding="utf-8")

    (apps / "thehub" / "1.0.0").mkdir(parents=True)
    promote_version(apps, "thehub", "1.0.0")

    with pytest.raises(InjectedFailure):
        with transaction("versioned_install_pointer_swap", staging) as tx:
            versioned_install_pointer_swap(
                tx, apps_root=apps, app_id="thehub", version="2.0.0", payload=payload
            )
            assert current_pointer(apps, "thehub").read_text(encoding="utf-8") == "2.0.0"
            raise InjectedFailure("post-swap validation failed")

    assert current_pointer(apps, "thehub").read_text(encoding="utf-8") == "1.0.0"


def test_rollback_refuses_when_the_prior_version_is_gone(tmp_path):
    apps = tmp_path / "apps"
    (apps / "thehub").mkdir(parents=True)
    with pytest.raises(RollbackFailed, match="no longer on disk"):
        rollback_version(apps, "thehub", "9.9.9")


def test_prune_keeps_at_least_one_prior_version(tmp_path):
    apps = tmp_path / "apps"
    for version in ("1.0.0", "2.0.0", "3.0.0", "4.0.0"):
        (apps / "thehub" / version).mkdir(parents=True)
    promote_version(apps, "thehub", "4.0.0")

    prune_old_versions(apps, "thehub", keep=2)
    remaining = sorted(p.name for p in (apps / "thehub").iterdir() if p.is_dir())
    assert len(remaining) >= 2
    assert "4.0.0" in remaining


def test_prune_never_removes_the_active_version(tmp_path):
    apps = tmp_path / "apps"
    for version in ("1.0.0", "2.0.0", "3.0.0"):
        (apps / "thehub" / version).mkdir(parents=True)
    promote_version(apps, "thehub", "1.0.0")  # oldest is active
    prune_old_versions(apps, "thehub", keep=2)
    assert (apps / "thehub" / "1.0.0").is_dir()


# ── run partitions ──────────────────────────────────────────────────────────


def test_run_partition_compensation_removes_only_this_run(tmp_path, staging):
    root = tmp_path / "partitions"
    (root / "earlier-run").mkdir(parents=True)
    (root / "earlier-run" / "kept.json").write_text("{}", encoding="utf-8")

    with pytest.raises(InjectedFailure):
        with transaction("run_partition_restore", staging) as tx:
            run_partition_restore(
                tx,
                partition_root=root,
                run_id="this-run",
                produce=lambda p: (p / "new.json").write_text("{}", encoding="utf-8"),
            )
            raise InjectedFailure("dispatch failed")

    assert (root / "earlier-run" / "kept.json").exists(), "pre-existing data must survive"
    assert not (root / "this-run").exists()


# ── file_snapshot_restore ───────────────────────────────────────────────────


def test_in_place_write_is_restored_on_failure(tmp_path, staging):
    target = tmp_path / "report.json"
    target.write_text('{"v": 1}', encoding="utf-8")

    with pytest.raises(InjectedFailure):
        with transaction("file_snapshot_restore", staging) as tx:
            file_snapshot_restore(
                tx, target=target, produce=lambda p: p.write_text('{"v": 2}', encoding="utf-8")
            )
            raise InjectedFailure("post-write validation failed")

    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 1}


# ── rollback failure is reported, never swallowed ───────────────────────────


def test_a_failing_rollback_surfaces_as_rollback_failed(tmp_path, staging):
    target = tmp_path / "data.json"
    target.write_text("original", encoding="utf-8")

    with pytest.raises(RollbackFailed):
        with transaction("stage_validate_atomic_promote", staging) as tx:
            stage_validate_atomic_promote(
                tx, target=target, produce=lambda p: p.write_text("new", encoding="utf-8")
            )
            # Destroy the backup so restore cannot succeed.
            for snapshot in tx._snapshots:
                if snapshot.backup:
                    snapshot.backup.unlink()
            raise InjectedFailure("after commit")


def test_rollback_state_is_recorded_for_the_receipt(tmp_path, staging):
    target = tmp_path / "data.json"
    target.write_text("original", encoding="utf-8")
    captured = {}

    with pytest.raises(InjectedFailure):
        with transaction("stage_validate_atomic_promote", staging) as tx:
            captured["tx"] = tx
            stage_validate_atomic_promote(
                tx, target=target, produce=lambda p: p.write_text("new", encoding="utf-8")
            )
            raise InjectedFailure("after commit")

    record = captured["tx"].record.as_receipt()
    assert record["rollback_state"] == RollbackState.SUCCEEDED.value
    assert record["strategy"] == "stage_validate_atomic_promote"
    assert record["phase_reached"] == Phase.COMMIT.value


def test_unexpected_writes_are_carried_into_the_receipt(tmp_path, staging):
    with transaction("stage_validate_atomic_promote", staging) as tx:
        tx.record_write_audit(["outside/scope.txt"])
        record = tx.record.as_receipt()
    assert record["unexpected_writes"] == ["outside/scope.txt"]


# ── strategy registry ───────────────────────────────────────────────────────


def test_unimplemented_strategies_fail_loudly_rather_than_silently(tmp_path):
    for name in sorted(UNIMPLEMENTED_STRATEGIES):
        with pytest.raises(TransactionError, match="not implemented in this vector"):
            require_strategy(name)


def test_unknown_strategy_is_rejected():
    with pytest.raises(TransactionError, match="unknown rollback strategy"):
        require_strategy("make_it_up")


def test_implemented_strategies_are_accepted():
    for name in (
        "none",
        "stage_validate_atomic_promote",
        "file_snapshot_restore",
        "sqlite_backup_integrity_check_atomic_swap",
        "versioned_install_pointer_swap",
        "ledger_snapshot_restore",
        "run_partition_restore",
    ):
        assert require_strategy(name) == name
