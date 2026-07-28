"""Staged transactions with atomic promotion and rollback.

Every operation runs through one pipeline::

    PLAN -> PREFLIGHT -> SNAPSHOT -> EXECUTE_IN_STAGING -> VALIDATE -> COMMIT -> RECEIPT

A failure *before* COMMIT deletes staging and leaves no visible change. A
failure *during or after* COMMIT invokes the strategy's rollback and records
whether it succeeded -- a rollback that fails is a reportable outcome, not an
exception that vanishes.

The repository had no atomic-write, staging, or snapshot helper of any kind
before this: every writer was a plain truncating write. :func:`write_atomic` is
the single shared primitive, so there is one implementation rather than a
second parallel convention.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence

from server.backend.federation_manager_files import sha256_file

BUSY_TIMEOUT_MS = 10_000


class Phase(str, Enum):
    PLAN = "PLAN"
    PREFLIGHT = "PREFLIGHT"
    SNAPSHOT = "SNAPSHOT"
    EXECUTE_IN_STAGING = "EXECUTE_IN_STAGING"
    VALIDATE = "VALIDATE"
    COMMIT = "COMMIT"
    RECEIPT = "RECEIPT"


PHASE_ORDER: Sequence[Phase] = (
    Phase.PLAN,
    Phase.PREFLIGHT,
    Phase.SNAPSHOT,
    Phase.EXECUTE_IN_STAGING,
    Phase.VALIDATE,
    Phase.COMMIT,
    Phase.RECEIPT,
)


class RollbackState(str, Enum):
    NOT_REQUIRED = "not_required"
    NOT_ATTEMPTED = "not_attempted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TransactionError(RuntimeError):
    """The transaction could not complete."""


class RollbackFailed(TransactionError):
    """Rollback itself failed. This is a stop condition, never a silent skip."""


# ── the shared atomic-write primitive ───────────────────────────────────────


def write_atomic(path: Path, data: "str | bytes", *, encoding: str = "utf-8") -> Path:
    """Write ``data`` to ``path`` atomically.

    Writes to a temporary file in the *same directory* -- so the final rename
    cannot cross a filesystem boundary and degrade to a copy -- fsyncs, then
    ``os.replace``. A reader either sees the whole previous file or the whole
    new one, never a half-written mix.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.encode(encoding) if isinstance(data, str) else data

    handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    # Durability of the rename itself needs the directory synced too.
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except (OSError, AttributeError):  # pragma: no cover - not available everywhere
        pass
    return path


def atomic_replace_tree(staging: Path, target: Path, *, backup: Optional[Path] = None) -> None:
    """Swap a directory into place, keeping the previous one if asked."""
    staging, target = Path(staging), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if backup is not None:
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(target, backup)
        else:
            shutil.rmtree(target)
    os.replace(staging, target)


# ── snapshots ───────────────────────────────────────────────────────────────


@dataclass
class Snapshot:
    """What must be restorable if a commit goes wrong."""

    kind: str
    target: Path
    backup: Optional[Path] = None
    existed: bool = True
    sha256: Optional[str] = None
    row_count: Optional[int] = None
    bytes: Optional[int] = None

    def digest(self) -> Optional[str]:
        return self.sha256


def snapshot_file(target: Path, staging_dir: Path) -> Snapshot:
    target = Path(target)
    staging_dir = Path(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        # Recording absence matters: rollback must *delete* a file the run
        # created, not restore a copy that never existed.
        return Snapshot(kind="file", target=target, existed=False)
    backup = staging_dir / f"{target.name}.snapshot"
    shutil.copy2(target, backup)
    return Snapshot(
        kind="file",
        target=target,
        backup=backup,
        existed=True,
        sha256=sha256_file(backup),
        bytes=backup.stat().st_size,
    )


def snapshot_ledger(target: Path, staging_dir: Path) -> Snapshot:
    """Snapshot a JSONL/CSV ledger, recording its row count as well as its hash.

    Row count is what makes "zero unaccounted row loss" checkable; a hash alone
    tells you something changed but not whether rows disappeared.
    """
    snapshot = snapshot_file(target, staging_dir)
    snapshot.kind = "ledger"
    if snapshot.existed and snapshot.backup is not None:
        with snapshot.backup.open("r", encoding="utf-8", errors="replace") as handle:
            snapshot.row_count = sum(1 for line in handle if line.strip())
    return snapshot


def snapshot_sqlite(target: Path, staging_dir: Path) -> Snapshot:
    """Back up a SQLite database with the online backup API.

    A file copy of a live database can capture a torn write; the backup API
    takes a consistent copy even while the database is in use.
    """
    target = Path(target)
    staging_dir = Path(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        return Snapshot(kind="sqlite", target=target, existed=False)

    backup = staging_dir / f"{target.name}.backup"
    source = sqlite3.connect(str(target))
    try:
        source.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        destination = sqlite3.connect(str(backup))
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()

    return Snapshot(
        kind="sqlite",
        target=target,
        backup=backup,
        existed=True,
        sha256=sha256_file(backup),
        bytes=backup.stat().st_size,
    )


def integrity_check(database: Path) -> bool:
    """True when SQLite reports the file is a sound database.

    A file that is not a database at all raises rather than reporting a
    problem, so that is caught here: to a caller deciding whether to promote a
    staged file, "corrupt" and "not a database" are the same answer.
    """
    try:
        connection = sqlite3.connect(str(database))
    except sqlite3.Error:
        return False
    try:
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        result = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError:
        return False
    finally:
        connection.close()
    return bool(result) and result[0] == "ok"


def configure_connection(connection: sqlite3.Connection) -> None:
    """WAL plus a busy timeout.

    The request handlers open a connection per request with no explicit
    transaction, so an operation writing concurrently would otherwise hit
    "database is locked".
    """
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")


def count_rows(database: Path, table: str = "entities") -> int:
    connection = sqlite3.connect(str(database))
    try:
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        cursor = connection.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 - fixed identifier
        return int(cursor.fetchone()[0])
    except sqlite3.Error:
        return 0
    finally:
        connection.close()


# ── restore ─────────────────────────────────────────────────────────────────


def restore(snapshot: Snapshot) -> None:
    """Put the target back exactly as the snapshot found it."""
    target = Path(snapshot.target)
    if not snapshot.existed:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
        return

    if snapshot.backup is None or not Path(snapshot.backup).exists():
        raise RollbackFailed(f"snapshot for {target} is missing its backup copy")

    write_atomic(target, Path(snapshot.backup).read_bytes())

    restored = sha256_file(target)
    if snapshot.sha256 and restored != snapshot.sha256:
        raise RollbackFailed(
            f"restored {target} does not match its snapshot digest "
            f"({restored[:12]} != {snapshot.sha256[:12]})"
        )


# ── versioned install ───────────────────────────────────────────────────────


def install_versioned(apps_root: Path, app_id: str, version: str, payload: Path) -> Path:
    """Stage a version directory and return it, without promoting it."""
    destination = Path(apps_root) / app_id / version
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(payload, destination)
    return destination


def current_pointer(apps_root: Path, app_id: str) -> Path:
    return Path(apps_root) / app_id / "current"


def promote_version(apps_root: Path, app_id: str, version: str) -> Optional[str]:
    """Swap the small ``current`` pointer. Returns the version it replaced.

    The pointer is a tiny file rather than a symlink so the swap is a single
    ``os.replace`` on every platform, including Windows where symlinks need a
    privilege most operators do not have.
    """
    pointer = current_pointer(apps_root, app_id)
    previous = pointer.read_text(encoding="utf-8").strip() if pointer.exists() else None
    write_atomic(pointer, version)
    return previous


def rollback_version(apps_root: Path, app_id: str, previous_version: Optional[str]) -> None:
    pointer = current_pointer(apps_root, app_id)
    if previous_version is None:
        pointer.unlink(missing_ok=True)
        return
    if not (Path(apps_root) / app_id / previous_version).is_dir():
        raise RollbackFailed(
            f"cannot roll back {app_id}: prior version {previous_version} is no longer on disk"
        )
    write_atomic(pointer, previous_version)


def prune_old_versions(apps_root: Path, app_id: str, keep: int = 2) -> List[str]:
    """Drop stale versions, always retaining at least one known-good prior."""
    keep = max(2, keep)
    app_dir = Path(apps_root) / app_id
    if not app_dir.is_dir():
        return []
    pointer = current_pointer(apps_root, app_id)
    active = pointer.read_text(encoding="utf-8").strip() if pointer.exists() else None
    versions = sorted(
        (p for p in app_dir.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed: List[str] = []
    for stale in versions[keep:]:
        if stale.name == active:
            continue
        shutil.rmtree(stale, ignore_errors=True)
        removed.append(stale.name)
    return removed


# ── the transaction ─────────────────────────────────────────────────────────


@dataclass
class TransactionRecord:
    strategy: str
    phase_reached: Phase = Phase.PLAN
    rollback_state: RollbackState = RollbackState.NOT_REQUIRED
    rollback_detail: str = ""
    snapshot_sha256: Optional[str] = None
    unexpected_writes: List[str] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)

    def as_receipt(self) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "strategy": self.strategy,
            "phase_reached": self.phase_reached.value,
            "rollback_state": self.rollback_state.value,
            "snapshot_sha256": self.snapshot_sha256,
        }
        if self.rollback_detail:
            record["rollback_detail"] = self.rollback_detail
        if self.unexpected_writes:
            record["unexpected_writes"] = sorted(self.unexpected_writes)
        return record


class Transaction:
    """Drives one operation through the phases and rolls back on failure.

    Snapshots are registered as the run goes. On failure the transaction
    restores them in reverse order, so a later snapshot never overwrites an
    earlier restore.
    """

    def __init__(self, strategy: str, staging_root: Path, run_id: Optional[str] = None):
        self.strategy = strategy
        self.run_id = run_id or uuid.uuid4().hex
        self.staging_root = Path(staging_root)
        self.staging = self.staging_root / self.run_id
        self.staging.mkdir(parents=True, exist_ok=True)
        self.record = TransactionRecord(strategy=strategy)
        self._snapshots: List[Snapshot] = []
        self._compensations: List[Callable[[], None]] = []
        self._committed = False

    # -- phases ------------------------------------------------------------

    def enter(self, phase: Phase) -> None:
        self.record.phase_reached = phase

    def add_snapshot(self, snapshot: Snapshot) -> Snapshot:
        self._snapshots.append(snapshot)
        if snapshot.digest() and self.record.snapshot_sha256 is None:
            self.record.snapshot_sha256 = snapshot.digest()
        return snapshot

    def add_compensation(self, action: Callable[[], None]) -> None:
        """Register an undo for something a snapshot cannot express."""
        self._compensations.append(action)

    def mark_committed(self) -> None:
        self._committed = True

    # -- outcomes ----------------------------------------------------------

    def discard_staging(self) -> None:
        shutil.rmtree(self.staging, ignore_errors=True)

    def rollback(self, reason: str = "") -> None:
        """Restore every snapshot and run every compensation, newest first."""
        failures: List[str] = []
        for action in reversed(self._compensations):
            try:
                action()
            except Exception as exc:  # noqa: BLE001 - each failure is reported
                failures.append(f"compensation: {exc}")
        for snapshot in reversed(self._snapshots):
            try:
                restore(snapshot)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{snapshot.target}: {exc}")

        if failures:
            self.record.rollback_state = RollbackState.FAILED
            self.record.rollback_detail = "; ".join(failures)
            raise RollbackFailed(self.record.rollback_detail)

        self.record.rollback_state = RollbackState.SUCCEEDED
        self.record.rollback_detail = reason

    def record_write_audit(self, offending: Sequence[str]) -> None:
        self.record.unexpected_writes = list(offending)


@contextmanager
def transaction(strategy: str, staging_root: Path, run_id: Optional[str] = None) -> Iterator[Transaction]:
    """Run a block as a transaction.

    Failure before COMMIT discards staging and leaves nothing visible. Failure
    at or after COMMIT rolls back and re-raises, so the caller cannot mistake a
    rolled-back run for a successful one.
    """
    tx = Transaction(strategy, staging_root, run_id)
    try:
        yield tx
    except BaseException:
        if tx._committed:
            try:
                tx.rollback("failure after commit")
            except RollbackFailed:
                tx.discard_staging()
                raise
        else:
            tx.record.rollback_state = RollbackState.NOT_REQUIRED
        tx.discard_staging()
        raise
    else:
        tx.discard_staging()


# ── strategy helpers ────────────────────────────────────────────────────────


def stage_validate_atomic_promote(
    tx: Transaction,
    *,
    target: Path,
    produce: Callable[[Path], None],
    validate: Optional[Callable[[Path], None]] = None,
) -> Path:
    """Write to staging, validate there, then promote in one rename."""
    target = Path(target)
    tx.enter(Phase.SNAPSHOT)
    snapshot = tx.add_snapshot(snapshot_file(target, tx.staging))

    tx.enter(Phase.EXECUTE_IN_STAGING)
    staged = tx.staging / f"{target.name}.staged"
    produce(staged)

    tx.enter(Phase.VALIDATE)
    if validate is not None:
        validate(staged)

    tx.enter(Phase.COMMIT)
    write_atomic(target, staged.read_bytes())
    tx.mark_committed()
    if not snapshot.existed:
        # Nothing to restore on rollback beyond deleting what we created.
        tx.record.rollback_state = RollbackState.NOT_REQUIRED
    return target


def sqlite_backup_integrity_check_atomic_swap(
    tx: Transaction,
    *,
    database: Path,
    mutate: Callable[[Path], None],
    expected_min_rows: int = 0,
    table: str = "entities",
) -> Path:
    """Back up, mutate a staged copy, verify it, then swap it in.

    The live database is never the thing being mutated, so a crash mid-ingest
    leaves the original untouched rather than half-written.
    """
    database = Path(database)
    tx.enter(Phase.SNAPSHOT)
    snapshot = tx.add_snapshot(snapshot_sqlite(database, tx.staging))

    tx.enter(Phase.EXECUTE_IN_STAGING)
    staged = tx.staging / f"{database.name}.staged"
    if snapshot.existed and snapshot.backup is not None:
        shutil.copy2(snapshot.backup, staged)
    mutate(staged)

    tx.enter(Phase.VALIDATE)
    if not integrity_check(staged):
        raise TransactionError(f"staged database failed PRAGMA integrity_check: {staged}")
    rows = count_rows(staged, table)
    if rows < expected_min_rows:
        raise TransactionError(
            f"staged database has {rows} rows in {table}, expected at least {expected_min_rows}"
        )

    tx.enter(Phase.COMMIT)
    write_atomic(database, staged.read_bytes())
    tx.mark_committed()
    return database


def ledger_snapshot_restore(
    tx: Transaction,
    *,
    ledger: Path,
    produce: Callable[[Path], None],
    allow_row_loss: bool = False,
) -> Path:
    """Rewrite a ledger as a new file, refusing unaccounted row loss."""
    ledger = Path(ledger)
    tx.enter(Phase.SNAPSHOT)
    snapshot = tx.add_snapshot(snapshot_ledger(ledger, tx.staging))

    tx.enter(Phase.EXECUTE_IN_STAGING)
    staged = tx.staging / f"{ledger.name}.staged"
    produce(staged)

    tx.enter(Phase.VALIDATE)
    with staged.open("r", encoding="utf-8", errors="replace") as handle:
        new_rows = sum(1 for line in handle if line.strip())
    if not allow_row_loss and snapshot.row_count is not None and new_rows < snapshot.row_count:
        raise TransactionError(
            f"ledger {ledger.name} would lose rows: {snapshot.row_count} -> {new_rows}. "
            "Pass allow_row_loss when a reduction is the intended result."
        )

    tx.enter(Phase.COMMIT)
    write_atomic(ledger, staged.read_bytes())
    tx.mark_committed()
    return ledger


def file_snapshot_restore(
    tx: Transaction, *, target: Path, produce: Callable[[Path], None]
) -> Path:
    """Snapshot a file, let the operation write it in place, restore on failure.

    For operations that insist on writing their own output path. Weaker than
    staging -- the window between write and validate is visible -- but it is
    what an unmodified producer script requires.
    """
    target = Path(target)
    tx.enter(Phase.SNAPSHOT)
    tx.add_snapshot(snapshot_file(target, tx.staging))
    tx.enter(Phase.EXECUTE_IN_STAGING)
    tx.enter(Phase.COMMIT)
    tx.mark_committed()
    produce(target)
    return target


def versioned_install_pointer_swap(
    tx: Transaction,
    *,
    apps_root: Path,
    app_id: str,
    version: str,
    payload: Path,
    smoke_test: Optional[Callable[[Path], None]] = None,
) -> Path:
    """Install into a version directory and promote by pointer swap."""
    tx.enter(Phase.SNAPSHOT)
    pointer = current_pointer(apps_root, app_id)
    previous = pointer.read_text(encoding="utf-8").strip() if pointer.exists() else None

    tx.enter(Phase.EXECUTE_IN_STAGING)
    installed = install_versioned(apps_root, app_id, version, payload)

    tx.enter(Phase.VALIDATE)
    if smoke_test is not None:
        smoke_test(installed)

    tx.enter(Phase.COMMIT)
    tx.add_compensation(lambda: rollback_version(apps_root, app_id, previous))
    promote_version(apps_root, app_id, version)
    tx.mark_committed()
    prune_old_versions(apps_root, app_id)
    return installed


def run_partition_restore(
    tx: Transaction, *, partition_root: Path, run_id: str, produce: Callable[[Path], None]
) -> Path:
    """Confine a run's writes to its own partition, removable on failure.

    Compensation deletes only this run's partition, so data written by earlier
    runs is never touched.
    """
    partition = Path(partition_root) / run_id
    partition.mkdir(parents=True, exist_ok=True)
    tx.enter(Phase.EXECUTE_IN_STAGING)
    tx.add_compensation(lambda: shutil.rmtree(partition, ignore_errors=True))
    tx.enter(Phase.COMMIT)
    tx.mark_committed()
    produce(partition)
    return partition


def hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


STRATEGIES: Mapping[str, str] = {
    "none": "No write; nothing to roll back.",
    "stage_validate_atomic_promote": "Write to staging, validate, promote with a single rename.",
    "file_snapshot_restore": "Snapshot the target, write in place, restore on failure.",
    "sqlite_backup_integrity_check_atomic_swap": (
        "Back up with the SQLite backup API, mutate a staged copy, integrity-check, swap."
    ),
    "versioned_install_pointer_swap": "Install a version directory, promote by pointer swap.",
    "ledger_snapshot_restore": "Snapshot with row counts, rewrite, refuse unaccounted row loss.",
    "run_partition_restore": "Confine writes to a per-run partition, removable on failure.",
}

#: Declared by producer operations but not built in this vector. Named
#: explicitly so a caller gets a clear error instead of a silent no-op.
UNIMPLEMENTED_STRATEGIES = frozenset(
    {
        "dispatch_receipt_compensating_remove",
        "transactional_run_partition_restore",
        "queue_run_partition_delete",
        "delete_staging_download",
        "transaction_snapshot_and_run_partition_restore",
        "delete staging checkout; preserve prior current pointer",
    }
)


def require_strategy(name: str) -> str:
    if name in UNIMPLEMENTED_STRATEGIES:
        raise TransactionError(
            f"rollback strategy {name!r} is declared by a producer operation but is not "
            "implemented in this vector; the operation is not enabled"
        )
    if name not in STRATEGIES:
        raise TransactionError(f"unknown rollback strategy: {name!r}")
    return name
