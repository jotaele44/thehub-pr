from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .classifier import classify_trace
from .models import Evidence, Trace

IGNORED_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", ".pytest_cache"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue"}
ROUTE_DECORATOR = re.compile(r"(?:app|router)\.(get|post|put|patch|delete|options|head)\(\s*[\"']([^\"']+)")
JSX_CONTROL = re.compile(r"<(button|Button|a|Link)\b([^>]*)>(.*?)</\1>", re.I | re.S)
ON_EVENT = re.compile(r"on(?:Click|Submit|Change|Select)\s*=\s*\{([^}]+)\}")
FUNC_ARROW = re.compile(r"(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{(.*?)\};", re.S)
FUNC_DECL = re.compile(r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{(.*?)\n\}", re.S)
NETWORK_CALL = re.compile(r"(?:(fetch)\s*\(\s*|axios\.(get|post|put|patch|delete)\s*\(\s*)[\"'`]([^\"'`]+)", re.I)
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


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]


def iter_sources(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES and not any(p in IGNORED_DIRS for p in path.parts):
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
            if decorator.func.attr.lower() not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                routes.append(ApiRoute(decorator.func.attr.upper(), decorator.args[0].value, rel, decorator.lineno))
    return routes


def _fallback_routes(source: str, rel: str) -> list[ApiRoute]:
    return [ApiRoute(m.upper(), p, rel, source[:match.start()].count("\n") + 1) for match in ROUTE_DECORATOR.finditer(source) for m, p in [match.groups()]]


def _handlers(source: str) -> dict[str, str]:
    result = {name: body for name, body in FUNC_ARROW.findall(source)}
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
            after = body[match.end(): match.end() + 350]
            method_match = METHOD_OPTION.search(after)
            if method_match:
                method = method_match.group(1).upper()
        intents.append((method, path))
    return intents


def _generic_trace(repo: dict, kind: str, rel: str, line: int, label: str, observations: dict, path_nodes: list[dict]) -> Trace:
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


def _repo_trace(repo: dict, rel: str, line: int, label: str, observations: dict, path_nodes: list[dict]) -> Trace:
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
                    if call and call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
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
            node = {"node_id": stable_id(rel, name, command), "kind": "package-script", "status": "resolved" if command.strip() else "missing", "source": rel}
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
        for job_id, line, steps in jobs:
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
            nodes = [{"node_id": stable_id(rel, job_id), "kind": "workflow-job", "status": "resolved" if steps else "declared", "source": rel}]
            nodes.extend({"node_id": stable_id(rel, job_id, step), "kind": "workflow-step", "status": "declared", "source": rel} for step in steps[:20])
            traces.append(_generic_trace(repo, "workflow-stage", rel, line, job_id, observations, nodes))
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
                symbols.update(n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
            except SyntaxError:
                pass
        else:
            symbols.update(_handlers(source))

    traces: list[Trace] = []
    for route in routes:
        observations = {"handler_bound": True, "handler_resolved": True, "intent_observed": True, "boundary_reached": True, "contract_matched": True, "static_contract_resolved": True}
        nodes = [{"node_id": stable_id(route.method, route.path, route.source), "kind": "api-route", "status": "resolved", "source": route.source}]
        traces.append(_generic_trace(repo, "route", route.source, route.line, f"{route.method} {route.path}", observations, nodes))
    for rel, source in sources.items():
        if Path(rel).suffix == ".py":
            for command, line in _python_cli_commands(source, rel):
                observations = {"handler_bound": True, "handler_resolved": True, "intent_observed": True, "boundary_reached": True, "contract_matched": True, "static_contract_resolved": True}
                nodes = [{"node_id": stable_id(rel, command), "kind": "cli-command", "status": "resolved", "source": rel}]
                traces.append(_generic_trace(repo, "command", rel, line, command, observations, nodes))
    route_keys = {(r.method, r.path) for r in routes}
    all_source = "\n".join(sources.values())
    for rel, source in sources.items():
        if Path(rel).suffix not in {".js", ".jsx", ".ts", ".tsx", ".vue"}:
            continue
        handlers = _handlers(source)
        for control in JSX_CONTROL.finditer(source):
            tag = control.group(1).lower()
            attrs, body = control.group(2), control.group(3)
            event = ON_EVENT.search(attrs)
            label = _label(body, attrs)
            line = source[: control.start()].count("\n") + 1
            obs: dict[str, object] = {"handler_bound": bool(event), "side_effect_intercepted": False}
            nodes = [{"node_id": stable_id(rel, str(line), "control"), "kind": "gui-control", "status": "observed", "source": rel}]
            if not event:
                navigation = re.search(r"(?:href|to)\s*=\s*(?:[\"']([^\"']+)[\"']|\{[\"']([^\"']+)[\"']\})", attrs)
                is_submit = bool(re.search(r"type\s*=\s*[\"']submit[\"']", attrs, re.I))
                if tag in {"a", "link"} and navigation:
                    target = navigation.group(1) or navigation.group(2)
                    obs.update({"handler_bound": True, "handler_resolved": True, "intent_observed": True, "boundary_reached": True, "contract_matched": True, "static_contract_resolved": True})
                    nodes.append({"node_id": stable_id(rel, target, "navigation"), "kind": "navigation-target", "status": "declared", "source": rel})
                elif is_submit:
                    obs.update({"handler_bound": True, "handler_resolved": True, "intent_observed": True})
                    nodes.append({"node_id": stable_id(rel, str(line), "form-submit"), "kind": "form-submit", "status": "declared", "source": rel})
                traces.append(_repo_trace(repo, rel, line, label, obs, nodes))
                continue
            expr = event.group(1).strip()
            handler_name_match = re.match(r"([A-Za-z_$][\w$]*)$", expr)
            handler_name = handler_name_match.group(1) if handler_name_match else None
            body_text = handlers.get(handler_name, expr)
            resolved = handler_name is None or handler_name in handlers
            obs["handler_resolved"] = resolved
            nodes.append({"node_id": stable_id(rel, handler_name or expr, "handler"), "kind": "event-handler", "status": "resolved" if resolved else "missing", "source": rel})
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
                nodes.append({"node_id": stable_id(method, target), "kind": "network-intent", "status": "declared", "source": rel})
                exact = (method, target) in route_keys
                path_exists = any(route_path == target for _, route_path in route_keys)
                if exact:
                    obs.update({"boundary_reached": True, "contract_matched": True, "static_contract_resolved": True})
                    route = next(r for r in routes if (r.method, r.path) == (method, target))
                    nodes.append({"node_id": stable_id(route.method, route.path, route.source), "kind": "api-route", "status": "resolved", "source": route.source})
                elif path_exists:
                    obs["contract_mismatch"] = True
                else:
                    obs["target_missing"] = True
            else:
                calls = [c for c in CALL.findall(body_text) if c not in {"if", "for", "while", "switch", "catch", "setState", "console"}]
                local_targets = [c for c in calls if c in symbols or re.search(rf"\b(?:function|const|let|class)\s+{re.escape(c)}\b", all_source)]
                obs["intent_observed"] = bool(calls)
                if local_targets:
                    obs.update({"boundary_reached": True, "contract_matched": True, "static_contract_resolved": True})
                    for target in local_targets[:3]:
                        nodes.append({"node_id": stable_id(target, "symbol"), "kind": "local-target", "status": "resolved", "source": None})
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
            "by_kind": {kind: sum(t["surface"]["kind"] == kind for t in encoded) for kind in sorted({t["surface"]["kind"] for t in encoded})},
            "classification_counts": {status: sum(t["classification"] == status for t in encoded) for status in sorted({t["classification"] for t in encoded})},
            "repositories_present": len(manifest["repositories"]) - len(missing),
            "repositories_missing": len(missing),
        },
        "workspace_gaps": missing,
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
