from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

SUPPORTED_SUFFIXES = {
    ".py", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".md", ".rst", ".txt", ".csv", ".ts", ".tsx", ".js", ".jsx",
}
EXCLUDED_DIR_NAMES = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", ".next",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__", "coverage",
    ".tox", ".nox", "vendor", "third_party", "site-packages",
}
EXCLUDED_FILE_NAMES = {
    "uv.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "FROZEN.sha256", "SHA256SUMS", "SHA256SUMS.txt",
}
MAX_TEXT_BYTES = 2_000_000
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")
CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def normalize_label(value: str) -> str:
    value = CAMEL_BOUNDARY_RE.sub(" ", value.strip())
    value = value.replace("::", " ").replace(".", " ").replace("-", "_")
    value = NON_ALNUM_RE.sub("_", value.lower()).strip("_")
    return value


def stable_observation_id(parts: Sequence[str]) -> str:
    return "term_" + sha256_text("\x1f".join(parts))[:32]


def git_head(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip().lower()
    return value if re.fullmatch(r"[a-f0-9]{40}", value) else None


def tracked_files(repo_root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z"],
            check=True,
            capture_output=True,
            timeout=60,
        )
        raw = result.stdout.decode("utf-8", errors="surrogateescape")
        paths = [repo_root / p for p in raw.split("\0") if p]
        if paths:
            return sorted(paths)
    except (OSError, subprocess.SubprocessError):
        pass
    return sorted(p for p in repo_root.rglob("*") if p.is_file())


def exclusion_reason(path: Path, repo_root: Path) -> str | None:
    rel = path.relative_to(repo_root)
    if any(part in EXCLUDED_DIR_NAMES for part in rel.parts[:-1]):
        return "excluded_directory"
    if path.name in EXCLUDED_FILE_NAMES:
        return "generated_or_lock_file"
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return "unsupported_suffix"
    try:
        size = path.stat().st_size
    except OSError:
        return "stat_failure"
    if size > MAX_TEXT_BYTES:
        return "oversize_text_file"
    return None


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" in data[:8192]:
        raise ValueError("binary_nul_detected")
    return data.decode("utf-8", errors="replace")


def scalar_to_text(value: Any) -> str | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return None


def iter_mapping_paths(value: Any, prefix: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            path = prefix + (key_text,)
            yield path, child
            yield from iter_mapping_paths(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_mapping_paths(child, prefix + (f"[{index}]",))


def context_line(lines: Sequence[str], line_number: int, radius: int = 1) -> str:
    start = max(0, line_number - 1 - radius)
    end = min(len(lines), line_number + radius)
    return "\n".join(lines[start:end]).strip()[:1000]


def detect_unit(term: str) -> str | None:
    normalized = normalize_label(term)
    suffix_map = {
        "_usd": "USD", "_dollars": "USD", "_amount": "currency_unspecified",
        "_ft": "feet", "_feet": "feet", "_km": "kilometres", "_miles": "miles",
        "_meters": "metres", "_metres": "metres", "_lat": "decimal_degrees",
        "_lon": "decimal_degrees", "_latitude": "decimal_degrees", "_longitude": "decimal_degrees",
        "_pct": "percent", "_percent": "percent", "_ratio": "ratio",
        "_seconds": "seconds", "_minutes": "minutes", "_hours": "hours",
        "_days": "days", "_bytes": "bytes", "_count": "count",
    }
    for suffix, unit in suffix_map.items():
        if normalized.endswith(suffix):
            return unit
    return None


def detect_scale_from_context(context: str) -> str | None:
    compact = context.lower().replace("–", "-").replace("—", "-")
    patterns = [
        (r"(?:0(?:\.0)?\s*(?:to|-|\.\.)\s*1(?:\.0)?)", "0..1"),
        (r"(?:0\s*(?:to|-|\.\.)\s*100)", "0..100"),
        (r"minimum\W*[-]?90.*maximum\W*90", "-90..90"),
        (r"minimum\W*[-]?180.*maximum\W*180", "-180..180"),
    ]
    for pattern, label in patterns:
        if re.search(pattern, compact, re.S):
            return label
    return None


def looks_like_lifecycle(term: str) -> bool:
    normalized = normalize_label(term)
    return any(token in normalized.split("_") for token in ("status", "state", "stage", "phase", "lifecycle"))


def unique_preserve(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
