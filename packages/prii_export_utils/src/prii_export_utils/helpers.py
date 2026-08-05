import hashlib
from pathlib import Path
from typing import Any


def fid(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:32]
    return f"{prefix}_{digest}"


def norm(name: str) -> str:
    return " ".join(str(name).strip().upper().split())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
