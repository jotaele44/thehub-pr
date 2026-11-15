"""Keep large generated files out of the repository.

Eight full aggregates (about 117 MB each) were once committed under ``reports/``,
which made the working tree 986 MB. ``.pre-commit-config.yaml`` already refuses
additions over 5 MB, but pre-commit is opt-in; this is the same limit enforced in CI.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024  # matches check-added-large-files --maxkb=5120

# Files over the limit that are deliberately tracked. Adding to this list is a
# reviewed decision: say why the file cannot be regenerated or stored elsewhere.
ALLOWED = {
    # Saturated PR grid cell index: frozen spatial authority input, hash-pinned.
    "registry/spatial/pr_grid_full_cell_index_saturated.csv",
    # Resolved dependency lock; size follows the dependency set.
    "uv.lock",
}


def _tracked_files() -> list[str] | None:
    """Tracked paths, or None when this is not a git checkout (e.g. an sdist)."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [name for name in out.decode().split("\0") if name]


def test_no_tracked_file_exceeds_the_size_limit() -> None:
    tracked = _tracked_files()
    if tracked is None:
        pytest.skip("not a git checkout")
    oversized = []
    for name in tracked:
        path = ROOT / name
        if name in ALLOWED or not path.is_file():
            continue
        size = path.stat().st_size
        if size > MAX_BYTES:
            oversized.append(f"{name} ({size / 1_048_576:.1f} MB)")
    assert not oversized, (
        "tracked files over 5 MB; commit a manifest (checksums and counts) "
        "instead of the bytes, or add the file to ALLOWED with a reason:\n  "
        + "\n  ".join(oversized)
    )
