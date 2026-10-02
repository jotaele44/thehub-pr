from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .classifier import classify_trace
from .models import Evidence, Trace

IGNORED_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "test",
    "tests",
    "__tests__",
}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue"}
TEST_SOURCE_DIRS = {"test", "tests", "__tests__"}
TEST_SOURCE_NAME = re.compile(r"(?:^test_|_test(?=\.|$)|\.(?:test|spec)\.)", re.I)
ROUTE_DECORATOR = re.compile(r"(?:app|router)\.(get|post|put|patch|delete|options|head)\(\s*[\"']([^\"']+)")
JSX_CONTROL_START = re.compile(r"<(button|Button|a|Link|input|select|textarea)\b", re.I)
JSX_EVENT_NAME = re.compile(r"\bon[A-Z][A-Za-z0-9_$]*\s*=")
FUNC_ARROW = re.compile(
    r"(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{(.*?)\};", re.S
)
FUNC_CALLBACK = re.compile(
    r"(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*useCallback\(\s*"
    r"(?:async\s*)?\([^)]*\)\s*=>\s*\{(.*?)\}\s*,", re.S
)
FUNC_DECL = re.compile(r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{(.*?)\n\}", re.S)
NETWORK_CALL = re.compile(
    r"(?:(fetch)\s*\(\s*|axios\.(get|post|put|patch|delete)\s*\(\s*)[\"'`]([^\"'`]+)", re.I
)
METHOD_OPTION = re.compile(r"method\s*:\s*[\"'](GET|POST|PUT|PATCH|DELETE)[\"']", re.I)
CALL = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")
PLACEHOLDER = re.compile(r"\b(TODO|FIXME|NotImplemented|placeholder|mock[-_ ]only|coming soon)\b", re.I)
TEXT_TAGS = re.compile(r"<[^>]+>")
JSX_EXPRESSION = re.compile(r"\{.*?\}", re.S)
SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class ApiRoute:
    method: str
    path: str
    source: str
    line: int


@dataclass(frozen=True)
class JSXControl:
    tag: str
    attributes: str
    body: str
    start: int


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]


def is_test_source(path: Path) -> bool:
    return (
        any(part.lower() in TEST_SOURCE_DIRS for part in path.parts[:-1])
        or TEST_SOURCE_NAME.search(path.name) is not None
    )


def iter_sources(root: Path) -> Iterable[Path]:
    for current, directories, files in os.walk(root):
        directories[:] = sorted(directory for directory in directories if directory not in IGNORED_DIRS)
        for filename in sorted(files):
            path = Path(current) / filename
            if (
                path.suffix.lower() in SOURCE_SUFFIXES
                and not is_test_source(path.relative_to(root))
            ):
                yield path


def _python_routes(source: str, rel: str) -> list[ApiRoute]:
    routes: list[ApiRoute] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return routes
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
            }:
                continue
            if (
                decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                routes.append(
                    ApiRoute(decorator.func.attr.upper(), decorator.args[0].value, rel, decorator.lineno)
                )
    return routes


def _balanced_brace_end(source: str, start: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    index = start
    while index < len(source):
        char = source[index]
        if quote is None and source[index : index + 2] == "//":
            newline = source.find("\n", index + 2)
            if newline < 0:
                return None
            index = newline + 1
            continue
        if quote is None and source[index : index + 2] == "/*":
            comment_end = source.find("*/", index + 2)
            if comment_end < 0:
                return None
            index = comment_end + 2
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _jsx_open_end(source: str, start: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        elif char == ">" and depth == 0:
            return index
    return None


def iter_jsx_controls(source: str) -> Iterable[JSXControl]:
    for opening in JSX_CONTROL_START.finditer(source):
        tag = opening.group(1)
        tag_end = _jsx_open_end(source, opening.end())
        if tag_end is None:
            continue
        attributes = source[opening.end() : tag_end]
        if source[tag_end - 1 : tag_end] == "/":
            if tag.lower() == "input" and JSX_EVENT_NAME.search(attributes):
                yield JSXControl(tag=tag, attributes=attributes, body="", start=opening.start())
            continue
        closing = re.search(rf"</\s*{re.escape(tag)}\s*>", source[tag_end + 1 :], re.I)
        if closing is None:
            continue
        body_start = tag_end + 1
        body_end = body_start + closing.start()
        yield JSXControl(
            tag=tag,
            attributes=attributes,
            body=source[body_start:body_end],
            start=opening.start(),
        )


def jsx_expression_attribute(attributes: str, name: re.Pattern[str] | str) -> str | None:
    pattern = name if isinstance(name, re.Pattern) else re.compile(rf"\b{re.escape(name)}\s*=")
    match = pattern.search(attributes)
    if match is None:
        return None
    start = match.end()
    while start < len(attributes) and attributes[start].isspace():
        start += 1
    if start >= len(attributes) or attributes[start] != "{":
        return None
    end = _balanced_brace_end(attributes, start)
    return attributes[start + 1 : end].strip() if end is not None else None


def jsx_navigation_attribute(attributes: str) -> tuple[str, bool] | None:
    match = re.search(r"\b(?:to|href)\s*=", attributes)
    if match is None:
        return None
    start = match.end()
    while start < len(attributes) and attributes[start].isspace():
        start += 1
    if start < len(attributes) and attributes[start] in {"'", '"'}:
        quote = attributes[start]
        end = start + 1
        escaped = False
        while end < len(attributes):
            char = attributes[end]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                return attributes[start + 1 : end], False
            end += 1
        return None
    if start < len(attributes) and attributes[start] == "{":
        expression_end = _balanced_brace_end(attributes, start)
        if expression_end is not None:
            expression = attributes[start + 1 : expression_end].strip()
            literal = re.fullmatch(r"""(['"])(.*?)\1""", expression, re.S)
            return (literal.group(2), False) if literal else (expression, True)
    return None


def _fallback_routes(source: str, rel: str) -> list[ApiRoute]:
    return [
        ApiRoute(m.upper(), p, rel, source[: match.start()].count("\n") + 1)
        for match in ROUTE_DECORATOR.finditer(source)
        for m, p in [match.groups()]
    ]


def _handlers(source: str) -> dict[str, str]:
    result = {name: body for name, body in FUNC_ARROW.findall(source)}
    result.update({name: body for name, body in FUNC_CALLBACK.findall(source)})
    result.update({name: body for name, body in FUNC_DECL.findall(source)})
    return result


def _label(body: str, attrs: str) -> str:
    aria = re.search(r"aria-label\s*=\s*[\"']([^\"']+)", attrs, re.I)
    if aria:
        return aria.group(1).strip()
    text = SPACE.sub(" ", JSX_EXPRESSION.sub(" ", TEXT_TAGS.sub(" ", body))).strip()
    return text[:160] or "unlabeled-control"


def _network_intents(body: str) -> list[tuple[str, str]]:
    intents = []
    for match in NETWORK_CALL.finditer(body):
        fetch_token, axios_method, path = match.groups()
        method = (axios_method or "GET").upper()
        if fetch_token:
            after = body[match.end() : match.end() + 350]
            method_match = METHOD_OPTION.search(after)
            if method_match:
                method = method_match.group(1).upper()
        intents.append((method, path))
    return intents


def _generic_trace(
    repo: dict, kind: str, rel: str, line: int, label: str, observations: dict, path_nodes: list[dict]
) -> Trace:
    tid = stable_id(repo["repository"], repo["commit"], kind, rel, str(line), label)
    trace = Trace(
        trace_id=tid,
        repository=repo["repository"],
        commit=repo["commit"],
        surface={"kind": kind, "id": tid, "label": label, "source": rel, "line": line},
        path=path_nodes,
        observations=observations,
        evidence=[Evidence("T1", "source", f"{rel}:{line}")],
    )
    return classify_trace(trace)


def _repo_trace(
    repo: dict, rel: str, line: int, label: str, observations: dict, path_nodes: list[dict]
) -> Trace:
    return _generic_trace(repo, "gui-control", rel, line, label, observations, path_nodes)


def _python_cli_commands(source: str, rel: str) -> list[tuple[str, int]]:
    commands: list[tuple[str, int]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                call = decorator if isinstance(decorator, ast.Call) else None
                target = call.func if call else decorator
                if isinstance(target, ast.Attribute) and target.attr in {"command", "callback"}:
                    name = node.name
                    if (
                        call
                        and call.args
                        and isinstance(call.args[0], ast.Constant)
                        and isinstance(call.args[0].value, str)
                    ):
                        name = call.args[0].value
                    commands.append((name, node.lineno))
    for match in re.finditer(r"\.add_parser\(\s*[\"']([^\"']+)", source):
        commands.append((match.group(1), source[: match.start()].count("\n") + 1))
    return commands


def _scan_package_scripts(root: Path, repo: dict) -> list[Trace]:
    traces: list[Trace] = []
    for path in root.rglob("package.json"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for name, command in (data.get("scripts") or {}).items():
            command = str(command)
            observations: dict[str, object] = {
                "handler_bound": True,
                "handler_resolved": bool(command.strip()),
                "intent_observed": bool(command.strip()),
                "boundary_reached": bool(command.strip()),
                "contract_matched": bool(command.strip()),
                "static_contract_resolved": bool(command.strip()),
            }
            if PLACEHOLDER.search(command):
                observations["placeholder"] = True
            node = {
                "node_id": stable_id(rel, name, command),
                "kind": "package-script",
                "status": "resolved" if command.strip() else "missing",
                "source": rel,
            }
            traces.append(_generic_trace(repo, "command", rel, 1, name, observations, [node]))
    return traces


def _scan_workflows(root: Path, repo: dict) -> list[Trace]:
    traces: list[Trace] = []
    workflow_root = root / ".github" / "workflows"
    if not workflow_root.is_dir():
        return traces
    for path in sorted([*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")]):
        rel = path.relative_to(root).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        in_jobs = False
        jobs: list[tuple[str, int, list[str]]] = []
        current: tuple[str, int, list[str]] | None = None
        for number, line in enumerate(lines, 1):
            if re.match(r"^jobs:\s*$", line):
                in_jobs = True
                continue
            if in_jobs and line and not line.startswith(" "):
                in_jobs = False
                current = None
            if not in_jobs:
                continue
            job = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
            if job:
                current = (job.group(1), number, [])
                jobs.append(current)
                continue
            if current and re.match(r"^\s+(?:run|uses):", line):
                current[2].append(line.strip())
        for job_id, job_line, steps in jobs:
            observations: dict[str, object] = {
                "handler_bound": True,
                "handler_resolved": True,
                "intent_observed": bool(steps),
                "boundary_reached": bool(steps),
                "contract_matched": bool(steps),
                "static_contract_resolved": bool(steps),
            }
            joined = "\n".join(steps)
            if PLACEHOLDER.search(joined):
                observations["placeholder"] = True
            nodes = [
                {
                    "node_id": stable_id(rel, job_id),
                    "kind": "workflow-job",
                    "status": "resolved" if steps else "declared",
                    "source": rel,
                }
            ]
            nodes.extend(
                {
                    "node_id": stable_id(rel, job_id, step),
                    "kind": "workflow-step",
                    "status": "declared",
                    "source": rel,
                }
                for step in steps[:20]
            )
            traces.append(_generic_trace(repo, "workflow-stage", rel, job_line, job_id, observations, nodes))
    return traces


def scan_repository(root: Path, repo: dict) -> list[Trace]:
    routes: list[ApiRoute] = []
    sources: dict[str, str] = {}
    symbols: set[str] = set()
    for path in iter_sources(root):
        rel = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        sources[rel] = source
        if path.suffix == ".py":
            found = _python_routes(source, rel)
            routes.extend(found or _fallback_routes(source, rel))
            try:
                tree = ast.parse(source)
                symbols.update(
                    n.name
                    for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                )
            except SyntaxError:
                # Keep the source inventory entry; syntax-invalid candidates cannot
                # contribute AST symbols but may still have fallback route evidence.
                continue
        else:
            symbols.update(_handlers(source))

    traces: list[Trace] = []
    for route in routes:
        observations = {
            "handler_bound": True,
            "handler_resolved": True,
            "intent_observed": True,
            "boundary_reached": True,
            "contract_matched": True,
            "static_contract_resolved": True,
        }
        nodes: list[dict[str, object]] = [
            {
                "node_id": stable_id(route.method, route.path, route.source),
                "kind": "api-route",
                "status": "resolved",
                "source": route.source,
            }
        ]
        traces.append(
            _generic_trace(
                repo, "route", route.source, route.line, f"{route.method} {route.path}", observations, nodes
            )
        )
    for rel, source in sources.items():
        if Path(rel).suffix == ".py":
            for command, line in _python_cli_commands(source, rel):
                observations = {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "static_contract_resolved": True,
                }
                nodes = [
                    {
                        "node_id": stable_id(rel, command),
                        "kind": "cli-command",
                        "status": "resolved",
                        "source": rel,
                    }
                ]
                traces.append(_generic_trace(repo, "command", rel, line, command, observations, nodes))
    route_keys = {(r.method, r.path) for r in routes}
    all_source = "\n".join(sources.values())
    for rel, source in sources.items():
        if Path(rel).suffix not in {".js", ".jsx", ".ts", ".tsx", ".vue"}:
            continue
        handlers = _handlers(source)
        for control in iter_jsx_controls(source):
            tag = control.tag.lower()
            attrs, body = control.attributes, control.body
            event_expr = jsx_expression_attribute(attrs, JSX_EVENT_NAME)
            label = _label(body, attrs)
            line = source[: control.start].count("\n") + 1
            obs: dict[str, object] = {
                "handler_bound": bool(event_expr),
                "side_effect_intercepted": False,
            }
            nodes = [
                {
                    "node_id": stable_id(rel, str(line), "control"),
                    "kind": "gui-control",
                    "status": "observed",
                    "source": rel,
                }
            ]
            if not event_expr:
                navigation = jsx_navigation_attribute(attrs)
                is_submit = bool(re.search(r"type\s*=\s*[\"']submit[\"']", attrs, re.I))
                if tag in {"a", "link"} and navigation:
                    target, dynamic = navigation
                    obs.update({"handler_bound": True, "handler_resolved": True, "intent_observed": True})
                    if not dynamic:
                        obs.update(
                            {
                                "boundary_reached": True,
                                "contract_matched": True,
                                "static_contract_resolved": True,
                            }
                        )
                    nodes.append(
                        {
                            "node_id": stable_id(rel, target, "navigation"),
                            "kind": "navigation-target",
                            "status": "dynamic" if dynamic else "declared",
                            "source": rel,
                        }
                    )
                elif is_submit:
                    obs.update({"handler_bound": True, "handler_resolved": True, "intent_observed": True})
                    nodes.append(
                        {
                            "node_id": stable_id(rel, str(line), "form-submit"),
                            "kind": "form-submit",
                            "status": "declared",
                            "source": rel,
                        }
                    )
                traces.append(_repo_trace(repo, rel, line, label, obs, nodes))
                continue
            expr = event_expr
            handler_name_match = re.match(r"([A-Za-z_$][\w$]*)$", expr)
            handler_name = handler_name_match.group(1) if handler_name_match else None
            body_text = expr if handler_name is None else handlers.get(handler_name, expr)
            resolved = (
                handler_name is None
                or handler_name in handlers
                or bool(
                    handler_name
                    and (
                        re.fullmatch(
                            r"(?:on|set|toggle|reset|handle|scroll|clear|submit|download|notify|retry)"
                            r"[A-Z]?[A-Za-z0-9_$]*",
                            handler_name,
                        )
                        or handler_name in {"clear", "submit"}
                    )
                )
            )
            obs["handler_resolved"] = resolved
            nodes.append(
                {
                    "node_id": stable_id(rel, handler_name or expr, "handler"),
                    "kind": "event-handler",
                    "status": "resolved" if resolved else "missing",
                    "source": rel,
                }
            )
            if not resolved:
                obs["target_missing"] = True
                traces.append(_repo_trace(repo, rel, line, label, obs, nodes))
                continue
            if PLACEHOLDER.search(body_text):
                obs["placeholder"] = True
            intents = _network_intents(body_text)
            if intents:
                obs["intent_observed"] = True
                method, target = intents[0]
                nodes.append(
                    {
                        "node_id": stable_id(method, target),
                        "kind": "network-intent",
                        "status": "declared",
                        "source": rel,
                    }
                )
                exact = (method, target) in route_keys
                path_exists = any(route_path == target for _, route_path in route_keys)
                if exact:
                    obs.update(
                        {"boundary_reached": True, "contract_matched": True, "static_contract_resolved": True}
                    )
                    route = next(r for r in routes if (r.method, r.path) == (method, target))
                    nodes.append(
                        {
                            "node_id": stable_id(route.method, route.path, route.source),
                            "kind": "api-route",
                            "status": "resolved",
                            "source": route.source,
                        }
                    )
                elif path_exists:
                    obs["contract_mismatch"] = True
                else:
                    obs["target_missing"] = True
            else:
                calls = [
                    c
                    for c in CALL.findall(body_text)
                    if c not in {"if", "for", "while", "switch", "catch", "setState", "console"}
                ]
                local_targets = [
                    c
                    for c in calls
                    if c in symbols
                    or re.fullmatch(r"set[A-Z][A-Za-z0-9_$]*", c)
                    or re.fullmatch(r"on[A-Z][A-Za-z0-9_$]*", c)
                    or re.search(rf"\b(?:function|const|let|class)\s+{re.escape(c)}\b", all_source)
                ]
                obs["intent_observed"] = bool(calls)
                if local_targets:
                    obs.update(
                        {"boundary_reached": True, "contract_matched": True, "static_contract_resolved": True}
                    )
                    for target in local_targets[:3]:
                        nodes.append(
                            {
                                "node_id": stable_id(target, "symbol"),
                                "kind": "local-target",
                                "status": "resolved",
                                "source": None,
                            }
                        )
            traces.append(_repo_trace(repo, rel, line, label, obs, nodes))
    traces.extend(_scan_package_scripts(root, repo))
    traces.extend(_scan_workflows(root, repo))
    return traces


def scan_federation(workspace_root: Path, manifest: dict) -> dict:
    traces: list[Trace] = []
    missing: list[str] = []
    for repo in manifest["repositories"]:
        repo_root = workspace_root / repo["workspace_directory"]
        if not repo_root.is_dir():
            missing.append(repo["workspace_directory"])
            continue
        traces.extend(scan_repository(repo_root, repo))
    encoded = [trace.to_dict() for trace in traces]
    return {
        "schema_version": "0.1.0",
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "traces": encoded,
        "coverage": {
            "surfaces_discovered": len(encoded),
            "surfaces_classified": sum(t["classification"] != "INDETERMINATE" for t in encoded),
            "t1_or_t2_supported": sum(any(e["tier"] in {"T1", "T2"} for e in t["evidence"]) for t in encoded),
            "by_kind": {
                kind: sum(t["surface"]["kind"] == kind for t in encoded)
                for kind in sorted({t["surface"]["kind"] for t in encoded})
            },
            "classification_counts": {
                status: sum(t["classification"] == status for t in encoded)
                for status in sorted({t["classification"] for t in encoded})
            },
            "repositories_present": len(manifest["repositories"]) - len(missing),
            "repositories_missing": len(missing),
        },
        "workspace_gaps": missing,
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
