#!/usr/bin/env python3
"""RC0 baseline preservation for the Federation Experience & Modernization Program.

Read-only against the eight repositories. For each one it records the Git
identity of the audited ref and builds a deterministic SHA-256 manifest of every
tracked file at that ref, read from Git objects. With ``--verify-recovery`` it
then fetches that exact commit into a disposable directory, checks it out, hashes
the files on disk and compares the two listings.

SHA-256 file hashes and Git object ids are different things and are kept in
separate fields. A successful recovery check shows the remote can reproduce the
tree; it is not evidence of an off-device backup.

Usage:
  rc0_baseline.py --root <dir holding the 8 checkouts> --out <dir> [--verify-recovery]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPOS = (
    "aguayluz-pr", "centinelas-pr", "moneysweep-pr", "mucaro-ai",
    "ovnis-pr", "skywatcher-pr", "spiderweb-pr", "thehub-pr",
)
OWNER = "jotaele44"
# Identities stated in the program brief ("previously observed", 2026-11-17).
BRIEF = {
    "aguayluz-pr": "74fcffadd285d508381ae2762377a0f7c60463d9",
    "centinelas-pr": "f8fe6aed9322207b059ab881bb4967010082b038",
    "moneysweep-pr": "c26b5028fd42a653eacb2bca48fd3ec8589d2a0f",
    "mucaro-ai": "0da925cf2c1059060fbd5f69ab2358d08e6808aa",
    "ovnis-pr": "a8225db5d226232037c455daf6e941e50d86d136",
    "skywatcher-pr": "a2176990606048a6b918daacdb8bce027e58a903",
    "spiderweb-pr": "9d6af728b48b7bbde5167d8abaacf51f34a0acaa",
    "thehub-pr": "dc79dc003815432b3f8bfc8f9bff532f6c47e622",
}
# Remote main as fetched earlier in the same working session (03:20Z), before
# the brief was received. Kept so the three observations can be compared.
SESSION_LEDGER = {
    "aguayluz-pr": "6046bda762107dacfab6a0d195a1b9cef196b7ed",
    "centinelas-pr": "3b80bb5e5bae3df1d1a358ffc250d42887132991",
    "moneysweep-pr": "b0dc1737fb58b4c544c1189a8db7e43338b70188",
    "mucaro-ai": "cf0c9901411fd07656b91f267cc0a274c58d460b",
    "ovnis-pr": "a8225db5d226232037c455daf6e941e50d86d136",
    "skywatcher-pr": "a2176990606048a6b918daacdb8bce027e58a903",
    "spiderweb-pr": "451535d7d19e1886dd0c478e1455d53625b85cab",
    "thehub-pr": "dc79dc003815432b3f8bfc8f9bff532f6c47e622",
}
LOCKFILES = (
    "uv.lock", "package-lock.json", "requirements.lock", "poetry.lock",
    "yarn.lock", "pnpm-lock.yaml", "Cargo.lock",
)
REF = "origin/main"


def git(repo: Path, *args: str, binary: bool = False):
    out = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    ).stdout
    return out if binary else out.decode("utf-8", "surrogateescape").strip()


def relation(repo: Path, earlier: str, current: str) -> str:
    """How a previously recorded commit relates to the current one."""
    if earlier == current:
        return "SAME"
    known = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", earlier + "^{commit}"],
                           capture_output=True).returncode == 0
    if not known:
        return "UNKNOWN_NOT_IN_LOCAL_HISTORY"

    def ancestor(a: str, b: str) -> bool:
        return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", a, b],
                              capture_output=True).returncode == 0

    if ancestor(earlier, current):
        return "SUPERSEDED_ANCESTOR_OF_CURRENT"
    if ancestor(current, earlier):
        return "AHEAD_OF_CURRENT"
    return "UNRESOLVED_NOT_AN_ANCESTOR_IN_LOCAL_HISTORY"


def tree_entries(repo: Path, ref: str) -> list[tuple[str, str, str, str]]:
    """(mode, type, git object id, path) for every entry, sorted by path bytes."""
    raw = git(repo, "ls-tree", "-r", "-z", "--full-tree", ref, binary=True)
    entries = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, kind, oid = meta.decode().split(" ")
        entries.append((mode, kind, oid, path.decode("utf-8", "surrogateescape")))
    return sorted(entries, key=lambda e: e[3].encode("utf-8", "surrogateescape"))


def hash_objects(repo: Path, oids: list[str]) -> dict[str, tuple[str, int]]:
    """sha256 and size of each blob's content, streamed through cat-file --batch."""
    unique = sorted(set(oids))
    proc = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    assert proc.stdin and proc.stdout
    result: dict[str, tuple[str, int]] = {}

    def feed() -> None:
        proc.stdin.write(("\n".join(unique) + "\n").encode())
        proc.stdin.close()

    import threading

    threading.Thread(target=feed, daemon=True).start()
    for oid in unique:
        header = proc.stdout.readline().decode().split()
        if len(header) != 3 or header[0] != oid:
            raise RuntimeError(f"{repo.name}: cannot read object {oid}: {header}")
        size, digest, left = int(header[2]), hashlib.sha256(), int(header[2])
        while left:
            chunk = proc.stdout.read(min(left, 1 << 20))
            if not chunk:
                raise RuntimeError(f"{repo.name}: short read on {oid}")
            digest.update(chunk)
            left -= len(chunk)
        proc.stdout.read(1)  # trailing newline
        result[oid] = (digest.hexdigest(), size)
    proc.wait()
    return result


def manifest_lines(entries, hashes) -> list[str]:
    """One line per tracked path. Submodule gitlinks have no file content."""
    lines = []
    for mode, kind, oid, path in entries:
        if kind == "blob":
            lines.append(f"{hashes[oid][0]}  {mode}  {path}")
        else:
            lines.append(f"gitlink:{oid}  {mode}  {path}")
    return lines


def listing_digest(lines: list[str]) -> str:
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8", "surrogateescape")).hexdigest()


def baseline(repo: Path) -> tuple[dict, list[str]]:
    commit = git(repo, "rev-parse", REF)
    entries = tree_entries(repo, REF)
    blobs = [e for e in entries if e[1] == "blob"]
    hashes = hash_objects(repo, [e[2] for e in blobs])
    lines = manifest_lines(entries, hashes)
    listed = [p for p in git(repo, "ls-tree", "-r", "--name-only", "-z", "--full-tree", REF,
                             binary=True).split(b"\0") if p]
    status = git(repo, "status", "--porcelain=v1")
    branch = git(repo, "branch", "--show-current")
    upstream = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "@{upstream}"],
        capture_output=True, text=True,
    )
    name = repo.name
    record = {
        "repository": f"{OWNER}/{name}",
        "audited_ref": REF,
        "identities": {
            "brief_recorded_remote_head": BRIEF[name],
            "session_ledger_remote_head": SESSION_LEDGER[name],
            "current_remote_head": commit,
            "current_remote_tree": git(repo, "rev-parse", f"{REF}^{{tree}}"),
            "current_local_head": git(repo, "rev-parse", "HEAD"),
            "current_local_branch": branch,
            "upstream": upstream.stdout.strip() if upstream.returncode == 0 else None,
            "local_is_ancestor_of_remote_main": subprocess.run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", "HEAD", REF]
            ).returncode == 0,
        },
        "identity_agreement": {
            "brief_equals_current": BRIEF[name] == commit,
            "session_ledger_equals_current": SESSION_LEDGER[name] == commit,
            "brief_equals_session_ledger": BRIEF[name] == SESSION_LEDGER[name],
            "brief_relation_to_current": relation(repo, BRIEF[name], commit),
            "session_ledger_relation_to_current": relation(repo, SESSION_LEDGER[name], commit),
        },
        "commit_date": git(repo, "show", "-s", "--format=%cI", REF),
        "dirty_paths": [line for line in status.splitlines() if line],
        "shallow_clone": git(repo, "rev-parse", "--is-shallow-repository") == "true",
        "tracked_paths": len(entries),
        "tracked_files": len(blobs),
        "gitlinks": len(entries) - len(blobs),
        "symlinks": sum(1 for e in blobs if e[0] == "120000"),
        "executables": sum(1 for e in blobs if e[0] == "100755"),
        "total_bytes": sum(hashes[e[2]][1] for e in blobs),
        "path_conservation": {
            "ls_tree_name_count": len(listed),
            "manifest_line_count": len(lines),
            "conserved": len(listed) == len(lines) == len(entries),
        },
        "lockfiles": [
            {"path": e[3], "sha256": hashes[e[2]][0]}
            for e in blobs if e[3].rsplit("/", 1)[-1] in LOCKFILES
        ],
        "manifest_file": f"manifests/{name}.sha256",
        "manifest_sha256": listing_digest(lines),
    }
    return record, lines


def disk_lines(checkout: Path, entries) -> list[str]:
    """Rebuild the listing from files on disk, independently of Git objects."""
    lines = []
    for mode, kind, oid, path in entries:
        if kind != "blob":
            lines.append(f"gitlink:{oid}  {mode}  {path}")
            continue
        target = checkout / path
        if mode == "120000":
            data = os.readlink(target).encode("utf-8", "surrogateescape")
            lines.append(f"{hashlib.sha256(data).hexdigest()}  {mode}  {path}")
            continue
        digest = hashlib.sha256()
        with open(target, "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
        lines.append(f"{digest.hexdigest()}  {mode}  {path}")
    return lines


def verify_recovery(repo: Path, record: dict, lines: list[str], scratch: Path) -> dict:
    commit = record["identities"]["current_remote_head"]
    url = git(repo, "remote", "get-url", "origin")
    target = scratch / repo.name
    target.mkdir(parents=True)
    result = {
        "repository": record["repository"],
        "commit": commit,
        "source": "fresh fetch of the exact commit from the Git remote",
        "target": "disposable temporary directory, deleted after the check",
    }
    try:
        git(target, "init", "-q")
        # Content must come out byte-for-byte: no line-ending or filter rewriting.
        git(target, "config", "core.autocrlf", "false")
        git(target, "remote", "add", "origin", url)
        git(target, "fetch", "-q", "--depth", "1", "origin", commit)
        git(target, "checkout", "-q", "--detach", "FETCH_HEAD")
        fetched = git(target, "rev-parse", "HEAD")
        rebuilt = disk_lines(target, tree_entries(target, "HEAD"))
        differing = sorted(set(lines) ^ set(rebuilt))
        # A path whose .gitattributes declares a line-ending conversion is not
        # byte-identical on disk by design. Accept it only if undoing exactly
        # that conversion reproduces the committed content hash.
        committed = {line.split("  ", 2)[2]: line.split("  ", 2)[0] for line in lines}
        explained, unexplained = [], []
        for path in sorted({line.split("  ", 2)[2] for line in differing}):
            attr = git(target, "check-attr", "eol", "--", path).rsplit(": ", 1)[-1]
            data = (target / path).read_bytes() if (target / path).is_file() else b""
            normalised = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
            if attr == "crlf" and normalised == committed.get(path):
                explained.append({"path": path, "declared_eol": attr,
                                  "normalised_sha256_matches_committed": True})
            else:
                unexplained.append(path)
        result.update(
            fetched_commit=fetched,
            commit_matches=fetched == commit,
            tree_matches=git(target, "rev-parse", "HEAD^{tree}")
            == record["identities"]["current_remote_tree"],
            rebuilt_file_count=len(rebuilt),
            rebuilt_manifest_sha256=listing_digest(rebuilt),
            manifest_matches=listing_digest(rebuilt) == record["manifest_sha256"],
            working_tree_paths_differing=len(explained) + len(unexplained),
            explained_by_declared_eol_conversion=explained,
            unexplained_differences=unexplained[:20],
        )
        result["status"] = (
            "PASS" if result["commit_matches"] and result["tree_matches"]
            and not unexplained else "FAIL"
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        detail = getattr(exc, "stderr", b"") or b""
        result.update(status="FAIL", error=f"{type(exc).__name__}: {exc}",
                      stderr=detail.decode("utf-8", "replace")[-400:])
    finally:
        shutil.rmtree(target, ignore_errors=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify-recovery", action="store_true")
    parser.add_argument(
        "--ignore-dirty-under", default="federation-audit/experience-program/",
        help="Path prefix in thehub-pr that holds this program's own artifacts; "
             "uncommitted files there are not counted as pre-existing local work.",
    )
    args = parser.parse_args()
    out = args.out.resolve()
    (out / "manifests").mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    records, all_lines = [], {}
    for name in REPOS:
        record, lines = baseline(args.root / name)
        (out / record["manifest_file"]).write_text(
            "\n".join(lines) + "\n", encoding="utf-8", errors="surrogateescape"
        )
        records.append(record)
        all_lines[name] = lines
        print(f"{name}: {record['tracked_files']} files, {record['total_bytes']:,} bytes",
              file=sys.stderr)

    def dump(name: str, payload: dict) -> None:
        (out / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    dump("repository_baselines.json", {
        "schema": "federation.experience-program.repository-baselines/1",
        "generated_at": generated,
        "claim_class": "FACT",
        "note": "Git commit and tree ids are Git object hashes. They are not SHA-256 "
                "file hashes; those are in source_manifest.json.",
        "repository_count": len(records),
        "repositories": [
            {k: r[k] for k in ("repository", "audited_ref", "identities",
                               "identity_agreement", "commit_date", "dirty_paths",
                               "shallow_clone")}
            for r in records
        ],
    })
    dump("source_manifest.json", {
        "schema": "federation.experience-program.source-manifest/1",
        "generated_at": generated,
        "claim_class": "COMPUTED",
        "method": "SHA-256 of each tracked blob's content read from Git objects at "
                  "audited_ref. Line format: '<sha256>  <git mode>  <path>', sorted "
                  "by path bytes. manifest_sha256 is the SHA-256 of that listing.",
        "repositories": [
            {k: r[k] for k in ("repository", "audited_ref", "tracked_paths",
                               "tracked_files", "gitlinks", "symlinks", "executables",
                               "total_bytes", "path_conservation", "lockfiles",
                               "manifest_file", "manifest_sha256")}
            | {"commit": r["identities"]["current_remote_head"]}
            for r in records
        ],
    })
    dump("worktree_inventory.json", {
        "schema": "federation.experience-program.worktree-inventory/1",
        "generated_at": generated,
        "claim_class": "FACT",
        "worktrees": [
            {
                "repository": f"{OWNER}/{name}",
                "worktrees": git(args.root / name, "worktree", "list", "--porcelain").split("\n\n"),
                "local_branches": git(args.root / name, "for-each-ref",
                                      "--format=%(refname:short) %(objectname)",
                                      "refs/heads").splitlines(),
                "uncommitted": git(args.root / name, "status", "--porcelain=v1").splitlines(),
                "stashes": len(git(args.root / name, "stash", "list").splitlines()),
            }
            for name in REPOS
        ],
    })

    recovery = None
    if args.verify_recovery:
        scratch = Path(tempfile.mkdtemp(prefix="rc0-recovery-"))
        try:
            checks = [
                verify_recovery(args.root / r["repository"].split("/")[1], r,
                                all_lines[r["repository"].split("/")[1]], scratch)
                for r in records
            ]
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        recovery = {
            "schema": "federation.experience-program.recovery-verification/1",
            "generated_at": generated,
            "claim_class": "COMPUTED",
            "what_this_shows": "The Git remote reproduces each audited tree byte for "
                               "byte into an empty directory.",
            "what_this_does_not_show": "That any backup exists outside the Git host. No "
                                       "off-device backup target was identified, so "
                                       "off-device recovery is OPEN, not PASS.",
            "remote_reproduction": checks,
            "off_device_backup": {"status": "OPEN", "evidence": None},
        }
        dump("recovery_verification.json", recovery)

    digest_lines = []
    for path in sorted(p for p in out.rglob("*") if p.is_file() and p.name != "source_manifest.sha256"
                       and p.name != "RC0_GATE.json"):
        digest_lines.append(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(out).as_posix()}"
        )
    (out / "source_manifest.sha256").write_text("\n".join(digest_lines) + "\n", encoding="utf-8")

    conserved = all(r["path_conservation"]["conserved"] for r in records)
    foreign_dirty = {
        r["repository"]: [
            line for line in r["dirty_paths"]
            if not (r["repository"].endswith("/thehub-pr")
                    and line[3:].strip('"').startswith(args.ignore_dirty_under))
        ]
        for r in records
    }
    clean = all(not paths for paths in foreign_dirty.values())
    reproduced = recovery is not None and all(
        c["status"] == "PASS" for c in recovery["remote_reproduction"]
    )
    dump("RC0_GATE.json", {
        "schema": "federation.experience-program.gate/1",
        "gate": "RC0",
        "generated_at": generated,
        "state": "PROVISIONAL" if (conserved and clean and reproduced) else "FAIL",
        "why_not_pass": "Off-device recovery is OPEN: only the Git remote was shown to "
                        "reproduce the trees.",
        "checks": {
            "eight_repositories_identified": {
                "state": "PASS" if len(records) == 8 else "FAIL", "count": len(records)},
            "no_uncommitted_local_changes": {
                "state": "PASS" if clean else "FAIL",
                "found": {k: v for k, v in foreign_dirty.items() if v},
                "excluded": f"thehub-pr paths under {args.ignore_dirty_under} "
                            "(this program's own artifacts)",
            },
            "path_conservation": {"state": "PASS" if conserved else "FAIL"},
            "sha256_manifests_built": {"state": "PASS", "files": sum(r["tracked_files"] for r in records)},
            "remote_reproduces_trees": {
                "state": "PASS" if reproduced else ("FAIL" if recovery else "OPEN")},
            "off_device_backup_verified": {"state": "OPEN"},
            "brief_identities_current": {
                # Not a pass/fail condition: the brief calls its SHAs starting
                # references. What matters is that every difference is explained.
                "state": "UNRESOLVED" if any(
                    r["identity_agreement"]["brief_relation_to_current"].startswith(
                        ("UNRESOLVED", "UNKNOWN", "AHEAD"))
                    for r in records) else "SUPERSEDED",
                "relations": {
                    r["repository"]: r["identity_agreement"]["brief_relation_to_current"]
                    for r in records},
                "note": "current_remote_head is the audited identity. A brief SHA that "
                        "is an ancestor of it was simply recorded earlier.",
            },
        },
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
