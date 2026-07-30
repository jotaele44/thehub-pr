"""Schema-freeze gate for ADR 0001, Phase 1, and ADR 0006 contracts.

The frozen contract boundary has three logical zones:

- ``schemas/*.json`` — ADR 0001 producer/Hub contracts.
- ``schemas/contracts/*.json`` — authoritative Phase 1 Evidence Engine,
  Intelligence Engine, and Control Plane contracts.
- ``schemas/contracts/**/*.json`` — additive child namespaces, including the
  ADR 0006 Skywatcher AI/imagery receipts and provisional-output contracts.

Every JSON schema is pinned to ``schemas/FROZEN.sha256`` using its path relative
to ``schemas/``. A drive-by edit, addition, or removal fails CI. Regenerate only
for a deliberate reviewed contract change:

    python tests/test_schema_freeze.py --update
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
CONTRACTS_DIR = SCHEMA_DIR / "contracts"
MANIFEST = SCHEMA_DIR / "FROZEN.sha256"


def _current_hashes() -> dict[str, str]:
    hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(SCHEMA_DIR.glob("*.json"))
    }
    hashes.update(
        {
            path.relative_to(SCHEMA_DIR).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(CONTRACTS_DIR.rglob("*.json"))
        }
    )
    return hashes


def _recorded_hashes() -> dict[str, str]:
    recorded: dict[str, str] = {}
    for line in MANIFEST.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, name = line.split(None, 1)
        recorded[name.strip()] = digest
    return recorded


def test_schemas_match_freeze_manifest() -> None:
    assert MANIFEST.exists(), (
        "schemas/FROZEN.sha256 is missing — regenerate it with "
        "`python tests/test_schema_freeze.py --update`"
    )
    current = _current_hashes()
    recorded = _recorded_hashes()

    added = sorted(set(current) - set(recorded))
    removed = sorted(set(recorded) - set(current))
    changed = sorted(
        name for name in set(current) & set(recorded) if current[name] != recorded[name]
    )

    problems = []
    if added:
        problems.append(f"schemas added without freeze-manifest update: {added}")
    if removed:
        problems.append(f"schemas removed without freeze-manifest update: {removed}")
    if changed:
        problems.append(f"frozen schemas changed: {changed}")
    assert not problems, (
        "; ".join(problems)
        + " — if this contract change is deliberate, regenerate the manifest with "
        "`python tests/test_schema_freeze.py --update` and explain it in the PR"
    )


def _update() -> None:
    lines = [
        "# SHA-256 freeze manifest for ADR 0001 and recursive schemas/contracts/ contracts.",
        "# Includes the Phase 1 flat namespace and ADR 0006 child namespaces.",
        "# Regenerate with: python tests/test_schema_freeze.py --update",
    ]
    lines += [f"{digest}  {name}" for name, digest in _current_hashes().items()]
    MANIFEST.write_text("\n".join(lines) + "\n")
    print(f"wrote {MANIFEST} ({len(_current_hashes())} schemas)")


if __name__ == "__main__":
    if "--update" in sys.argv:
        _update()
    else:
        print(__doc__)
