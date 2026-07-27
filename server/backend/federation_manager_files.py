"""File-token broker: the browser never submits a filesystem path.

An operator picks a file natively. The manager mints an **opaque token** bound
to that session, copies the selection into a per-run intake staging directory,
and runs preflight over the staged copy. Only the staged managed path ever
reaches argv, and the receipt records a logical name and a digest rather than
wherever the file happened to live on the operator's disk.

Why a copy rather than a reference: between "operator picked it" and "the
operation reads it" there is a window in which the original could be replaced.
Copying first, then hashing the copy, means the digest in the receipt describes
the exact bytes the operation consumed.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import secrets
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

TOKEN_TTL_SECONDS = 1800.0
MAX_INTAKE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB

#: Leading bytes we can positively identify. Used to catch a mismatch between a
#: file's extension and its actual content, not as a security boundary.
FILE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),
    (b"SQLite format 3\x00", "application/vnd.sqlite3"),
    (b"\x1f\x8b", "application/gzip"),
)

#: Sidecars that must travel with a primary file for the set to be usable.
FILE_SET_FAMILIES: Mapping[str, Mapping[str, Sequence[str]]] = {
    "shapefile": {"primary": [".shp"], "required": [".shx", ".dbf"], "optional": [".prj", ".cpg"]},
    "geojson": {"primary": [".geojson", ".json"], "required": [], "optional": []},
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class FileTokenError(ValueError):
    """A token is unknown, expired, not owned by this session, or unusable."""


class PreflightError(ValueError):
    """A staged file failed its declared preflight checks."""


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_component(name: str) -> str:
    """Reduce an operator-supplied filename to a safe single path component.

    The result is used only as a leaf name inside managed staging; directory
    parts are discarded rather than sanitised, because a name that contained
    them was never a plain filename.
    """
    leaf = Path(name).name
    cleaned = _SAFE_NAME.sub("_", leaf).strip("._") or "file"
    return cleaned[:120]


def sniff_signature(path: Path) -> Optional[str]:
    with path.open("rb") as handle:
        head = handle.read(32)
    for magic, media_type in FILE_SIGNATURES:
        if head.startswith(magic):
            return media_type
    return None


@dataclass(frozen=True)
class StagedFile:
    logical_name: str
    path: Path
    sha256: str
    bytes: int
    media_type: Optional[str]
    signature_media_type: Optional[str]
    sidecars: Sequence[str] = field(default_factory=tuple)

    def receipt_artifact(self, managed_root: Optional[Path] = None) -> Dict[str, Any]:
        """Receipt form: logical identity and digest, never the original path."""
        artifact: Dict[str, Any] = {
            "logical_name": self.logical_name,
            "sha256": self.sha256,
            "bytes": self.bytes,
        }
        if self.media_type:
            artifact["media_type"] = self.media_type
        if managed_root is not None:
            try:
                artifact["managed_path"] = str(self.path.resolve().relative_to(managed_root.resolve()))
            except ValueError:
                # relative_to raises when the file is not under the managed
                # root. That is not an error here: the receipt records
                # managed_path only for files inside managed storage, and
                # omitting the key is how a file outside it is represented.
                # Falling back to the absolute path would leak the operator's
                # filesystem layout into a signed, retained artifact.
                pass
        return artifact


@dataclass
class FileToken:
    token: str
    session_token: str
    app_id: str
    source_path: Path
    logical_name: str
    family: Optional[str]
    issued_at: float
    expires_at: float


class FileTokenBroker:
    """Mints opaque file tokens and stages the files they refer to.

    Tokens are held in memory: they are meant to be short-lived and to die with
    the manager process. Persisting them would create a durable
    path-to-capability mapping with no corresponding benefit.
    """

    def __init__(self, intake_root: Path, ttl_seconds: float = TOKEN_TTL_SECONDS):
        self._intake_root = Path(intake_root)
        self._ttl = ttl_seconds
        self._tokens: Dict[str, FileToken] = {}

    @property
    def intake_root(self) -> Path:
        """The managed root every staged file lives under."""
        return self._intake_root

    # ── minting ─────────────────────────────────────────────────────────────

    def mint(
        self,
        *,
        session_token: str,
        app_id: str,
        source_path: Path,
        family: Optional[str] = None,
        now: Optional[float] = None,
    ) -> str:
        """Register a natively-picked file and return an opaque handle.

        Called only by the native picker path. The browser sees the returned
        token and never the path.
        """
        source = Path(source_path)
        if not source.is_file():
            raise FileTokenError("selection is not a readable file")
        if source.is_symlink():
            # Resolve now so the token records the real target rather than a
            # link that could be repointed before staging.
            source = source.resolve()
            if not source.is_file():
                raise FileTokenError("selection resolves to something that is not a file")
        size = source.stat().st_size
        if size > MAX_INTAKE_BYTES:
            raise FileTokenError(f"selection exceeds the {MAX_INTAKE_BYTES} byte intake limit")

        now = time.time() if now is None else now
        token = secrets.token_urlsafe(32)
        self._tokens[token] = FileToken(
            token=token,
            session_token=session_token,
            app_id=app_id,
            source_path=source,
            logical_name=safe_component(source.name),
            family=family,
            issued_at=now,
            expires_at=now + self._ttl,
        )
        return token

    def resolve(
        self, token: str, *, session_token: str, app_id: str, now: Optional[float] = None
    ) -> FileToken:
        now = time.time() if now is None else now
        record = self._tokens.get(token)
        if record is None:
            raise FileTokenError("unknown file token")
        if now >= record.expires_at:
            self._tokens.pop(token, None)
            raise FileTokenError("file token has expired")
        if record.session_token != session_token:
            # Do not distinguish "wrong session" from "unknown" in anything the
            # caller sees beyond this message; both mean the same to a client.
            raise FileTokenError("file token does not belong to this session")
        if record.app_id != app_id:
            raise FileTokenError("file token was issued for a different application")
        return record

    def revoke(self, token: str) -> None:
        self._tokens.pop(token, None)

    def purge_expired(self, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        expired = [t for t, r in self._tokens.items() if now >= r.expires_at]
        for token in expired:
            self._tokens.pop(token, None)
        return len(expired)

    # ── staging ─────────────────────────────────────────────────────────────

    def run_intake_dir(self, run_id: str) -> Path:
        path = self._intake_root / run_id / "intake"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def stage(
        self,
        token: str,
        *,
        session_token: str,
        app_id: str,
        run_id: str,
        now: Optional[float] = None,
    ) -> StagedFile:
        """Copy the token's file into per-run staging and preflight the copy."""
        record = self.resolve(token, session_token=session_token, app_id=app_id, now=now)
        destination_dir = self.run_intake_dir(run_id)
        destination = destination_dir / record.logical_name

        shutil.copy2(record.source_path, destination)
        sidecars = self._copy_sidecars(record, destination_dir)

        digest = sha256_file(destination)
        media_type, _ = mimetypes.guess_type(destination.name)
        return StagedFile(
            logical_name=record.logical_name,
            path=destination,
            sha256=digest,
            bytes=destination.stat().st_size,
            media_type=media_type,
            signature_media_type=sniff_signature(destination),
            sidecars=tuple(sidecars),
        )

    def _copy_sidecars(self, record: FileToken, destination_dir: Path) -> List[str]:
        """Bring a file set's companions along with its primary member."""
        if not record.family:
            return []
        spec = FILE_SET_FAMILIES.get(record.family)
        if not spec:
            raise FileTokenError(f"unknown file set family: {record.family!r}")
        copied: List[str] = []
        stem = record.source_path.with_suffix("")
        for suffix in list(spec["required"]) + list(spec["optional"]):
            candidate = stem.with_suffix(suffix)
            if candidate.is_file():
                target = destination_dir / safe_component(candidate.name)
                shutil.copy2(candidate, target)
                copied.append(suffix)
        return copied


# ── preflight ───────────────────────────────────────────────────────────────


def preflight(
    staged: StagedFile,
    *,
    extensions: Optional[Sequence[str]] = None,
    family: Optional[str] = None,
    schema: Optional[Mapping[str, Any]] = None,
    max_bytes: int = MAX_INTAKE_BYTES,
) -> Dict[str, Any]:
    """Inspect a staged file and return a structured preflight record.

    Raises :class:`PreflightError` on anything that would make the operation
    meaningless. The returned record becomes part of the receipt, so a later
    reader can see what was actually checked rather than trusting that
    something was.
    """
    findings: Dict[str, Any] = {
        "logical_name": staged.logical_name,
        "bytes": staged.bytes,
        "sha256": staged.sha256,
        "media_type": staged.media_type,
        "signature_media_type": staged.signature_media_type,
        "checks": [],
    }

    def record(name: str, status: str, detail: str = "") -> None:
        findings["checks"].append({"name": name, "status": status, "detail": detail})

    if staged.bytes == 0:
        record("non_empty", "failed", "file is empty")
        raise PreflightError(f"{staged.logical_name} is empty")
    record("non_empty", "passed")

    if staged.bytes > max_bytes:
        record("size_limit", "failed", f"{staged.bytes} > {max_bytes}")
        raise PreflightError(f"{staged.logical_name} exceeds the size limit")
    record("size_limit", "passed")

    if extensions:
        if not any(staged.logical_name.endswith(ext) for ext in extensions):
            record("extension", "failed", f"expected one of {sorted(extensions)}")
            raise PreflightError(
                f"{staged.logical_name} must end with one of {sorted(extensions)}"
            )
        record("extension", "passed")

    if staged.signature_media_type and staged.media_type:
        if staged.signature_media_type != staged.media_type:
            # A mismatch is reported, not fatal: a .json file has no magic
            # number, and plenty of legitimate files are mislabelled. The
            # operator sees the discrepancy and decides.
            record(
                "signature_matches_extension",
                "failed",
                f"content looks like {staged.signature_media_type}, name suggests {staged.media_type}",
            )
        else:
            record("signature_matches_extension", "passed")

    if family:
        spec = FILE_SET_FAMILIES.get(family)
        if not spec:
            raise PreflightError(f"unknown file set family: {family!r}")
        missing = [s for s in spec["required"] if s not in staged.sidecars]
        if missing:
            record("sidecar_completeness", "failed", f"missing {missing}")
            raise PreflightError(f"{family} set is missing required sidecars: {missing}")
        record("sidecar_completeness", "passed", f"present: {list(staged.sidecars)}")

    if schema is not None:
        from jsonschema import Draft202012Validator, ValidationError

        try:
            payload = json.loads(staged.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            record("json_parse", "failed", str(exc))
            raise PreflightError(f"{staged.logical_name} is not valid JSON") from exc
        record("json_parse", "passed")
        try:
            Draft202012Validator(schema).validate(payload)
        except ValidationError as exc:
            record("schema", "failed", exc.message)
            raise PreflightError(f"{staged.logical_name} failed schema validation: {exc.message}") from exc
        record("schema", "passed")

    return findings


def stage_operation_inputs(
    broker: FileTokenBroker,
    *,
    session_token: str,
    app_id: str,
    run_id: str,
    token_parameters: Mapping[str, str],
    specs: Mapping[str, Mapping[str, Any]],
) -> tuple[Dict[str, Path], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Stage and preflight every file-token parameter for one run.

    Returns the staged paths for argv construction, the receipt artifacts, and
    the preflight records.
    """
    paths: Dict[str, Path] = {}
    artifacts: List[Dict[str, Any]] = []
    preflights: List[Dict[str, Any]] = []

    for name, token in token_parameters.items():
        spec = specs.get(name, {})
        staged = broker.stage(
            token, session_token=session_token, app_id=app_id, run_id=run_id
        )
        preflights.append(
            preflight(
                staged,
                extensions=spec.get("extensions"),
                family=spec.get("family"),
            )
        )
        paths[name] = staged.path
        artifacts.append(staged.receipt_artifact())

    return paths, artifacts, preflights


def discard_run_intake(intake_root: Path, run_id: str) -> None:
    """Remove a run's intake staging. Safe to call when it was never created."""
    target = Path(intake_root) / run_id
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)


def intake_inventory(intake_root: Path, run_id: str) -> List[str]:
    """List a run's staged files, for the post-run write audit."""
    base = Path(intake_root) / run_id
    if not base.exists():
        return []
    return sorted(
        str(path.relative_to(base)) for path in base.rglob("*") if path.is_file()
    )


def assert_within(root: Path, candidate: Path) -> Path:
    """Belt-and-braces containment check for staged paths."""
    resolved = Path(candidate).resolve()
    root_resolved = Path(root).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise FileTokenError(f"staged path escaped its root: {resolved}") from exc
    return resolved


def observed_paths(root: Path) -> Dict[str, str]:
    """Snapshot path -> digest for a tree, for pre/post write comparison."""
    root = Path(root)
    if not root.exists():
        return {}
    inventory: Dict[str, str] = {}
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            inventory[str(path.relative_to(root))] = sha256_file(path)
    return inventory


def diff_paths(before: Mapping[str, str], after: Mapping[str, str]) -> Dict[str, List[str]]:
    """Classify what changed between two inventories."""
    before_keys, after_keys = set(before), set(after)
    return {
        "created": sorted(after_keys - before_keys),
        "removed": sorted(before_keys - after_keys),
        "modified": sorted(k for k in before_keys & after_keys if before[k] != after[k]),
    }


def unexpected_writes(
    diff: Mapping[str, Iterable[str]], declared_scopes: Sequence[str]
) -> List[str]:
    """Return changed paths that fall outside every declared write scope."""
    changed = [*diff.get("created", []), *diff.get("modified", []), *diff.get("removed", [])]
    if not declared_scopes:
        return sorted(changed)
    offending = []
    for path in changed:
        normalised = path.replace(os.sep, "/")
        if not any(
            normalised == scope or normalised.startswith(scope.rstrip("/") + "/")
            for scope in declared_scopes
        ):
            offending.append(path)
    return sorted(offending)
