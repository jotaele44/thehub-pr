from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue"}
IGNORED_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", ".pytest_cache"}
JS_IMPORT = re.compile(
    r"import\s+(?:\{(?P<named>[^}]+)\}|(?P<default>[A-Za-z_$][\w$]*))\s+from\s+[\"'](?P<module>[^\"']+)[\"']"
)
JS_FUNCTION = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{",
    re.M,
)
JS_ARROW = re.compile(
    r"(?:export\s+)?(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>",
    re.M,
)
FETCH_LITERAL = re.compile(
    r"(?:(fetch)\s*\(\s*|axios\.(get|post|put|patch|delete)\s*\(\s*)[\"'`]([^\"'`]+)",
    re.I,
)
METHOD_OPTION = re.compile(r"method\s*:\s*[\"'](GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)[\"']", re.I)


def stable_digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def join_route(*parts: str) -> str:
    useful = [part.strip("/") for part in parts if part and part != "/"]
    return "/" + "/".join(useful) if useful else "/"


@dataclass(frozen=True)
class ResolvedRoute:
    method: str
    path: str
    source: str
    line: int
    handler: str
    router_symbol: str
    evidence: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, str]:
        return (self.method.upper(), self.path)


@dataclass(frozen=True)
class SymbolLocation:
    name: str
    source: str
    line: int
    exported: bool


@dataclass
class ResolutionIndex:
    root: Path
    routes: list[ResolvedRoute] = field(default_factory=list)
    symbols: dict[str, list[SymbolLocation]] = field(default_factory=dict)
    imports: dict[str, dict[str, tuple[str, str]]] = field(default_factory=dict)
    package_scripts: dict[str, dict[str, str]] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)

    def route(self, method: str, path: str) -> ResolvedRoute | None:
        method = method.upper()
        exact = [route for route in self.routes if route.method == method and route.path == path]
        return exact[0] if len(exact) == 1 else None

    def resolve_symbol(self, source: str, name: str) -> SymbolLocation | None:
        # A same-file symbol is strongest evidence.
        local = [item for item in self.symbols.get(name, []) if item.source == source]
        if len(local) == 1:
            return local[0]

        binding = self.imports.get(source, {}).get(name)
        if binding:
            module_path, original = binding
            candidates = [item for item in self.symbols.get(original, []) if item.source == module_path]
            if len(candidates) == 1:
                return candidates[0]
        return None

    def receipt(self, kind: str, source: str, target: str, evidence: Iterable[str]) -> dict[str, object]:
        evidence_items = tuple(evidence)
        return {
            "resolver": "federation-audit-v0.2",
            "kind": kind,
            "source": source,
            "target": target,
            "evidence": list(evidence_items),
            "digest": stable_digest(kind, source, target, *evidence_items),
        }


def iter_sources(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES and not any(part in IGNORED_DIRS for part in path.parts):
            yield path


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _router_prefixes(tree: ast.AST) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        func_name = ""
        if isinstance(value.func, ast.Name):
            func_name = value.func.id
        elif isinstance(value.func, ast.Attribute):
            func_name = value.func.attr
        if func_name != "APIRouter":
            continue
        prefix = ""
        for kw in value.keywords:
            if kw.arg == "prefix":
                prefix = _literal_string(kw.value) or ""
        targets: list[ast.AST] = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                prefixes[target.id] = prefix
    return prefixes


def _include_prefixes(tree: ast.AST) -> dict[str, list[str]]:
    """Return include_router target symbol -> literal include prefixes in this module."""
    result: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "include_router":
            continue
        if not node.args:
            continue
        arg = node.args[0]
        symbol: str | None = None
        if isinstance(arg, ast.Name):
            symbol = arg.id
        elif isinstance(arg, ast.Attribute):
            symbol = arg.attr
        if not symbol:
            continue
        prefix = ""
        for kw in node.keywords:
            if kw.arg == "prefix":
                prefix = _literal_string(kw.value) or ""
        result.setdefault(symbol, []).append(prefix)
    return result


def _python_routes(root: Path) -> tuple[list[ResolvedRoute], list[str]]:
    raw: list[tuple[str, str, str, int, str, str, str]] = []
    include_prefixes: dict[str, list[str]] = {}
    gaps: list[str] = []

    for path in iter_sources(root):
        if path.suffix != ".py":
            continue
        rel = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (OSError, SyntaxError) as exc:
            gaps.append(f"python-parse:{rel}:{type(exc).__name__}")
            continue
        local_prefix = _router_prefixes(tree)
        for symbol, prefixes in _include_prefixes(tree).items():
            include_prefixes.setdefault(symbol, []).extend(prefixes)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                method = decorator.func.attr.upper()
                if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
                    continue
                route_path = _literal_string(decorator.args[0]) if decorator.args else None
                if route_path is None:
                    gaps.append(f"dynamic-route:{rel}:{getattr(decorator, 'lineno', node.lineno)}")
                    continue
                router = decorator.func.value.id if isinstance(decorator.func.value, ast.Name) else "router"
                raw.append((method, route_path, rel, decorator.lineno, node.name, router, local_prefix.get(router, "")))

    resolved: list[ResolvedRoute] = []
    for method, route_path, rel, line, handler, router, router_prefix in raw:
        prefixes = include_prefixes.get(router) or [""]
        # Multiple literal includes are represented as multiple concrete routes rather than guessed.
        for include_prefix in prefixes:
            full = join_route(include_prefix, router_prefix, route_path)
            resolved.append(
                ResolvedRoute(
                    method,
                    full,
                    rel,
                    line,
                    handler,
                    router,
                    (f"decorator:{route_path}", f"router-prefix:{router_prefix}", f"include-prefix:{include_prefix}"),
                )
            )
    return resolved, gaps


def _resolve_module(source_rel: str, module: str, root: Path) -> str | None:
    if not module.startswith("."):
        return None
    base = (root / source_rel).parent
    candidate = (base / module).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    possibilities = [
        candidate,
        candidate.with_suffix(".ts"),
        candidate.with_suffix(".tsx"),
        candidate.with_suffix(".js"),
        candidate.with_suffix(".jsx"),
        candidate / "index.ts",
        candidate / "index.tsx",
        candidate / "index.js",
        candidate / "index.jsx",
    ]
    for item in possibilities:
        if item.is_file():
            return item.relative_to(root).as_posix()
    return None


def _frontend_index(root: Path) -> tuple[dict[str, list[SymbolLocation]], dict[str, dict[str, tuple[str, str]]], list[str]]:
    symbols: dict[str, list[SymbolLocation]] = {}
    imports: dict[str, dict[str, tuple[str, str]]] = {}
    gaps: list[str] = []
    for path in iter_sources(root):
        if path.suffix.lower() not in {".js", ".jsx", ".ts", ".tsx", ".vue"}:
            continue
        rel = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for regex in (JS_FUNCTION, JS_ARROW):
            for match in regex.finditer(source):
                name = match.group(1)
                exported = bool(re.match(r"\s*export\b", source[max(0, match.start() - 12):match.start() + 7]))
                symbols.setdefault(name, []).append(
                    SymbolLocation(name, rel, source[: match.start()].count("\n") + 1, exported)
                )
        for match in JS_IMPORT.finditer(source):
            module = match.group("module")
            module_path = _resolve_module(rel, module, root)
            if not module_path:
                if module.startswith("."):
                    gaps.append(f"unresolved-import:{rel}:{module}")
                continue
            bindings = imports.setdefault(rel, {})
            if match.group("default"):
                bindings[match.group("default")] = (module_path, "default")
            if match.group("named"):
                for token in match.group("named").split(","):
                    token = token.strip()
                    if not token:
                        continue
                    pieces = [piece.strip() for piece in re.split(r"\s+as\s+", token)]
                    original = pieces[0]
                    local = pieces[-1]
                    bindings[local] = (module_path, original)
    return symbols, imports, gaps


def _package_scripts(root: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for path in root.rglob("package.json"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        scripts = data.get("scripts") or {}
        result[path.relative_to(root).as_posix()] = {str(k): str(v) for k, v in scripts.items()}
    return result


def build_resolution_index(root: Path) -> ResolutionIndex:
    routes, route_gaps = _python_routes(root)
    symbols, imports, frontend_gaps = _frontend_index(root)
    return ResolutionIndex(
        root=root,
        routes=routes,
        symbols=symbols,
        imports=imports,
        package_scripts=_package_scripts(root),
        gaps=route_gaps + frontend_gaps,
    )


def network_intents(body: str) -> list[tuple[str, str]]:
    intents: list[tuple[str, str]] = []
    for match in FETCH_LITERAL.finditer(body):
        fetch_token, axios_method, target = match.groups()
        method = (axios_method or "GET").upper()
        if fetch_token:
            after = body[match.end():match.end() + 500]
            method_match = METHOD_OPTION.search(after)
            if method_match:
                method = method_match.group(1).upper()
        intents.append((method, target))
    return intents
