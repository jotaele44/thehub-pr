#!/usr/bin/env python3
"""Structured B.3 identifier-family census for the frozen seven-repository tree.

The original authority-boundary scanner intentionally looked only for a few
``*_id_prefix`` assignments. That can silently return an empty census while
producers still mint IDs in f-strings, tuple-driven layer maps, JSON/JSONL rows,
or workflow records. This module closes that failure mode without treating
names, taxonomy labels, or arbitrary scalar fields as identity.

The census denominator is *identifier construction or emitted identifier fields*:
  * explicit variables/defaults whose names end in ID_PREFIX / UID_PREFIX;
  * literal values emitted under keys ending in ``_id``;
  * Python assignments/dict values to ``*_id`` fields, including leading
    f-string / concatenation prefixes;
  * deterministic ID-constructor calls (``*_id(...)``, ``fid(...)``, ``_fid``);
  * tuple/map prefix families when a module uses a leading ``prefix`` variable
    to construct an ``*_id`` value.

Every surfaced signal must resolve to exactly one registered namespace for its
producer, except SHARED_* federation namespaces which are intentionally emitted
by multiple producers. Unresolved expressions are blockers rather than being
silently ignored.
"""
from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

TEXT_EXTS = {".js", ".json", ".jsonl", ".jsx", ".py", ".toml", ".ts", ".tsx", ".yaml", ".yml"}
SKIP_PARTS = {".git", ".github", ".venv", "__pycache__", "artifacts", "build", "dist", "docs", "fixtures", "node_modules", "reports", "test", "tests", "venv"}

# Constructor declarations: SW_RECORD_ID_PREFIX, visual_id_prefix, uid_prefix, etc.
PREFIX_ASSIGNMENT_RE = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*(?:ID_PREFIX|UID_PREFIX|VISUAL_ID_PREFIX)\s*[:=]\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
# Literal structured fields. Deliberately excludes bare ``id`` taxonomy/config keys.
STRUCTURED_ID_LITERAL_RE = re.compile(
    r"[\"']([A-Za-z][A-Za-z0-9_]*_id)[\"']\s*:\s*[\"']([^\"']+)[\"']"
)
YAML_ID_LITERAL_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9_]*_id)\s*:\s*[\"']?([^\s#\"']+)", re.MULTILINE
)
PREFIX_TOKEN_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:[_-][A-Z0-9]+)*[_-]?$")


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTS:
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        try:
            yield path, path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue


def _interesting(value: str) -> bool:
    value = value.strip()
    if not (1 <= len(value) <= 128) or "{" in value or "}" in value:
        return False
    # Require an identifier-like separator or a known shared stream stem. This
    # excludes ordinary words such as schema/taxonomy labels.
    return any(ch in value for ch in "_-:") or value.startswith(("ent", "src", "rel", "obs", "alrt", "fed", "frel"))


def _leading_static(expr: ast.AST) -> str | None:
    """Return a deterministic leading literal/prefix for an ID expression."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.JoinedStr):
        if expr.values and isinstance(expr.values[0], ast.Constant) and isinstance(expr.values[0].value, str):
            return expr.values[0].value
        return None
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        return _leading_static(expr.left)
    return None


def _target_names(target: ast.AST) -> Iterable[str]:
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            yield from _target_names(item)


def _dict_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def extract_python(text: str) -> tuple[set[str], list[dict[str, Any]]]:
    tree = ast.parse(text)
    signals: set[str] = set()
    unresolved: list[dict[str, Any]] = []

    # Literal prefix declarations and parameter defaults.
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            for target in targets:
                for name in _target_names(target):
                    if ("ID_PREFIX" in name.upper() or name.lower() in {"uid_prefix", "visual_id_prefix"}):
                        literal = _leading_static(value)
                        if literal and _interesting(literal):
                            signals.add(literal)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [*node.args.posonlyargs, *node.args.args]
            defaults = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)
            for arg, default in zip(args, defaults):
                if default is None:
                    continue
                if "id_prefix" in arg.arg.lower() or arg.arg.lower() == "uid_prefix":
                    literal = _leading_static(default)
                    if literal and _interesting(literal):
                        signals.add(literal)

    # Explicit *_id outputs and assignments.
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key_node, value_node in zip(node.keys, node.values):
                key = _dict_key(key_node) if key_node is not None else None
                if key and key.lower().endswith("_id"):
                    literal = _leading_static(value_node)
                    if literal and _interesting(literal):
                        signals.add(literal)
                    elif isinstance(value_node, (ast.JoinedStr, ast.BinOp)):
                        unresolved.append({"kind": "UNRESOLVED_ID_EXPRESSION", "field": key, "line": getattr(value_node, "lineno", None)})
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            for target in targets:
                for name in _target_names(target):
                    if not name.lower().endswith("_id"):
                        continue
                    literal = _leading_static(value)
                    if literal and _interesting(literal):
                        signals.add(literal)
                    elif isinstance(value, (ast.JoinedStr, ast.BinOp)):
                        unresolved.append({"kind": "UNRESOLVED_ID_EXPRESSION", "field": name, "line": getattr(value, "lineno", None)})

        if isinstance(node, ast.Call):
            name = _call_name(node).lower()
            if name in {"fid", "_fid", "stable_id"} or name.endswith("_id") or "sequence_id" in name:
                for arg in node.args[:4]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _interesting(arg.value):
                        # _fid('ent', ...) semantically yields ent_; sequence helpers
                        # often receive the already-delimited prefix (PRUAP-).
                        value = arg.value
                        if name in {"fid", "_fid"} and re.fullmatch(r"[A-Za-z]{2,8}", value):
                            value += "_"
                        signals.add(value)

    # Tuple/map-driven prefix families. Only activate this inference when the
    # module actually constructs an ID from a leading ``prefix`` formatted value.
    uses_dynamic_prefix = bool(re.search(r"f[\"']\{prefix\}[_-]", text))
    if uses_dynamic_prefix:
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            names = [name for target in node.targets for name in _target_names(target)]
            if not any(name.isupper() and ("LAYER" in name or "PREFIX" in name) for name in names):
                continue
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    token = sub.value.strip()
                    if PREFIX_TOKEN_RE.fullmatch(token) and 2 <= len(token) <= 20:
                        signals.add(token + ("" if token.endswith(("_", "-")) else "_"))

    return {s for s in signals if _interesting(s)}, unresolved


def extract_text(path: Path, text: str) -> tuple[set[str], list[dict[str, Any]]]:
    signals = {v for v in PREFIX_ASSIGNMENT_RE.findall(text) if _interesting(v)}
    for _key, value in STRUCTURED_ID_LITERAL_RE.findall(text):
        if _interesting(value):
            signals.add(value)
    if path.suffix.lower() in {".yaml", ".yml"}:
        for _key, value in YAML_ID_LITERAL_RE.findall(text):
            if _interesting(value):
                signals.add(value)
    unresolved: list[dict[str, Any]] = []
    if path.suffix.lower() == ".py":
        try:
            py_signals, unresolved = extract_python(text)
            signals.update(py_signals)
        except SyntaxError as exc:
            unresolved.append({"kind": "PYTHON_PARSE_ERROR", "line": exc.lineno, "offset": exc.offset, "error": str(exc)})
    return signals, unresolved


def _regex_literal_prefix(pattern: str) -> str:
    if not pattern.startswith("^"):
        return ""
    out: list[str] = []
    i = 1
    meta = set(".[$(){}*+?|")
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\":
            i += 1
            if i >= len(pattern) or pattern[i].isalnum():
                break
            out.append(pattern[i])
        elif ch in meta:
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def namespace_matches(namespace: dict[str, Any], signal: str) -> bool:
    pattern = str(namespace.get("pattern", ""))
    try:
        if re.fullmatch(pattern, signal):
            return True
    except re.error:
        return False
    prefix = _regex_literal_prefix(pattern)
    if not prefix:
        return False
    return signal.rstrip("-_.:") == prefix.rstrip("-_.:")


def crawl(paths: dict[str, Path]) -> tuple[dict[str, dict[str, set[str]]], list[dict[str, Any]]]:
    census: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    unresolved: list[dict[str, Any]] = []
    for program_id, root in paths.items():
        census[program_id]
        if not root.exists():
            continue
        for path, text in iter_files(root):
            relative = str(path.relative_to(root))
            signals, errors = extract_text(path, text)
            for signal in signals:
                census[program_id][signal].add(relative)
            for error in errors:
                unresolved.append({"repo": program_id, "path": relative, **error})
    return census, unresolved


def validate(paths: dict[str, Path], registry: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    namespaces = registry.get("namespaces", [])
    census, unresolved = crawl(paths)
    blockers: list[dict[str, Any]] = []
    resolutions: dict[str, Any] = {}
    for item in unresolved:
        blockers.append({"id": "AB-003-UNRESOLVED-ID-EXPRESSION", "detail": item})

    for program_id, signals in sorted(census.items()):
        resolutions[program_id] = {}
        for signal, sources in sorted(signals.items()):
            candidates = [row for row in namespaces if namespace_matches(row, signal)]
            summaries = [{"namespace": r.get("namespace"), "owner": r.get("owner"), "repository": r.get("repository"), "scope": r.get("scope")} for r in candidates]
            detail = {"sources": sorted(sources), "candidates": summaries}
            resolutions[program_id][signal] = detail
            if not candidates:
                blockers.append({"id": "AB-003-UNKNOWN-ID-FAMILY", "detail": {"repo": program_id, "signal": signal, **detail}})
                continue
            if len(candidates) != 1:
                blockers.append({"id": "AB-003-AMBIGUOUS-ID-FAMILY", "detail": {"repo": program_id, "signal": signal, **detail}})
                continue
            row = candidates[0]
            registered_program = str(row.get("repository", "")).rsplit("/", 1)[-1]
            shared = str(row.get("scope", "")).startswith("SHARED_") and row.get("owner") == "prii-federation-spatial-identity"
            if not shared and registered_program != program_id:
                blockers.append({"id": "AB-003-ID-FAMILY-OWNER-MISMATCH", "detail": {"repo": program_id, "signal": signal, **detail}})

    # A reconciled registry is meaningful only when every frozen repo was actually
    # traversed and at least one identifier family was observed federation-wide.
    if set(census) != set(paths) or not any(census.values()):
        blockers.append({"id": "AB-003-CENSUS-DENOMINATOR", "detail": {"expected": sorted(paths), "observed": sorted(census), "nonempty_repositories": sorted(k for k, v in census.items() if v)}})
    return blockers, {"census": {repo: {sig: sorted(srcs) for sig, srcs in sorted(signals.items())} for repo, signals in sorted(census.items())}, "resolutions": resolutions, "unresolved": unresolved}
