"""Offline integrity verification of the scoped USGS integration build."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "registry/usgs/SHA256SUMS.json").read_text())
    if not manifest or not isinstance(manifest, dict):
        raise ValueError("Empty or invalid build manifest")
    for name, expected in manifest.items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT.resolve())
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Build hash mismatch: " + name)
    print("PASS: %d scoped build files match SHA-256 manifest; payload activation remains BLOCKED" % len(manifest))


if __name__ == "__main__":
    main()
