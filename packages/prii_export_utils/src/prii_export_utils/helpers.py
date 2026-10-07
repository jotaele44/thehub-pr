import hashlib
from pathlib import Path
from typing import Any


def fid(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:32]
    return f"{prefix}_{digest}"


def norm(name: str) -> str:
    return " ".join(str(name).strip().upper().split())


def sha256(path: Path) -> str:
    """Hash an artifact with bounded memory, including large federation exports."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
