from __future__ import annotations

import re
from pathlib import Path

from .classifier import classify_trace
from .models import Evidence, Trace
from .resolver import ResolutionIndex, build_resolution_index, network_intents
from .scanner import scan_repository

CONTROL = re.compile(r"<(button|Button|a|Link)\b([^>]*)>(.*?)</\1>", re.I | re.S)
EVENT = re.compile(r"on(?:Click|Submit|Change|Select)\s*=\s*\{([^}]+)\}")
FUNC_ARROW_BODY = re.compile(
    r"(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{(.*?)\};",
    re.S,
)
FUNC_DECL_BODY = re.compile(
    r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{(.*?)\n\}",
    re.S,
)


def _handler_bodies(source: str) -> dict[str, str]:
    result = {name: body for name, body in FUNC_ARROW_BODY.findall(source)}
    result.update({name: body for name, body in FUNC_DECL_BODY.findall(source)})
    return result


def _control_at_line(source: str, line: int) -> tuple[str | None, str | None]:
    for match in CONTROL.finditer(source):
        match_line = source[: match.start()].count("\n") + 1
        if match_line != line:
            continue
        event = EVENT.search(match.group(2))
        return (event.group(1).strip() if event else None, match.group(0))
    return None, None


def _strictify(trace: Trace) -> Trace:
    for key in ("static_contract_resolved", "target_resolution_evidence", "t2_receipt", "runtime_isolated"):
        trace.observations.pop(key, None)
    return classify_trace(trace)


def _promote_gui_trace(trace: Trace, repo_root: Path, index: ResolutionIndex) -> Trace:
    source_rel = trace.surface.get("source")
    line = trace.surface.get("line")
    if not isinstance(source_rel, str) or not isinstance(line, int):
        return trace
    source_path = repo_root / source_rel
    if not source_path.is_file():
        return trace
    source = source_path.read_text(encoding="utf-8", errors="replace")
    event_expr, _ = _control_at_line(source, line)
    if not event_expr:
        return trace

    handler_match = re.fullmatch(r"([A-Za-z_$][\w$]*)", event_expr)
    handler_name = handler_match.group(1) if handler_match else None
    handler_source = source_rel
    body: str | None = None
    evidence: list[str] = [f"surface:{source_rel}:{line}"]

    if handler_name:
        local_bodies = _handler_bodies(source)
        if handler_name in local_bodies:
            body = local_bodies[handler_name]
            evidence.append(f"local-handler:{handler_name}")
        else:
            target = index.resolve_symbol(source_rel, handler_name)
            if target:
                target_source_path = repo_root / target.source
                target_source = target_source_path.read_text(encoding="utf-8", errors="replace")
                body = _handler_bodies(target_source).get(target.name)
                handler_source = target.source
                evidence.extend(
                    [
                        f"import-binding:{source_rel}:{handler_name}",
                        f"target-symbol:{target.source}:{target.line}:{target.name}",
                    ]
                )
    else:
        body = event_expr
        evidence.append("inline-event-expression")

    if not body:
        return trace

    intents = network_intents(body)
    if len(intents) != 1:
        return trace
    method, target_path = intents[0]
    route = index.route(method, target_path)
    if route is None:
        same_path = [item for item in index.routes if item.path == target_path]
        if same_path:
            trace.observations.pop("target_missing", None)
            trace.observations["handler_resolved"] = True
            trace.observations["contract_mismatch"] = True
            return classify_trace(trace)
        return trace

    receipt = index.receipt(
        "gui-to-api",
        f"{source_rel}:{line}",
        f"{route.method} {route.path}",
        [
            *evidence,
            f"handler-source:{handler_source}",
            *route.evidence,
            f"route:{route.source}:{route.line}",
        ],
    )
    # Strict T1 evidence supersedes provisional legacy observations made before
    # router-prefix/import resolution.
    for stale in ("target_missing", "contract_mismatch", "blocked_precondition", "undeclared_precondition"):
        trace.observations.pop(stale, None)
    trace.observations.update(
        {
            "handler_bound": True,
            "handler_resolved": True,
            "intent_observed": True,
            "boundary_reached": True,
            "contract_matched": True,
            "target_resolution_evidence": True,
            "resolver_receipt_digest": receipt["digest"],
        }
    )
    trace.evidence.append(Evidence("T1", "resolver-receipt", str(receipt["digest"])))
    return classify_trace(trace)


def strict_scan_repository(repo_root: Path, repo: dict) -> tuple[list[Trace], ResolutionIndex]:
    index = build_resolution_index(repo_root)
    traces = [_strictify(trace) for trace in scan_repository(repo_root, repo)]
    promoted: list[Trace] = []
    for trace in traces:
        if trace.surface.get("kind") == "gui-control":
            trace = _promote_gui_trace(trace, repo_root, index)
        promoted.append(trace)
    return promoted, index


def strict_scan_federation(workspace_root: Path, manifest: dict) -> dict:
    traces: list[Trace] = []
    missing: list[str] = []
    resolver_gaps: dict[str, list[str]] = {}
    for repo in manifest["repositories"]:
        repo_root = workspace_root / repo["workspace_directory"]
        if not repo_root.is_dir():
            missing.append(repo["workspace_directory"])
            continue
        repo_traces, index = strict_scan_repository(repo_root, repo)
        traces.extend(repo_traces)
        resolver_gaps[repo["id"]] = index.gaps

    encoded = [trace.to_dict() for trace in traces]
    statuses = sorted({item["classification"] for item in encoded})
    kinds = sorted({item["surface"]["kind"] for item in encoded})
    return {
        "schema_version": "0.2.0",
        "mode": "strict-static",
        "traces": encoded,
        "coverage": {
            "surfaces_discovered": len(encoded),
            "surfaces_classified": sum(item["classification"] != "INDETERMINATE" for item in encoded),
            "t1_or_t2_supported": sum(
                any(e["tier"] in {"T1", "T2"} for e in item["evidence"]) for item in encoded
            ),
            "target_resolved": sum(
                bool(item["observations"].get("target_resolution_evidence")) for item in encoded
            ),
            "by_kind": {kind: sum(item["surface"]["kind"] == kind for item in encoded) for kind in kinds},
            "classification_counts": {
                status: sum(item["classification"] == status for item in encoded) for status in statuses
            },
            "repositories_present": len(manifest["repositories"]) - len(missing),
            "repositories_missing": len(missing),
        },
        "workspace_gaps": missing,
        "resolver_gaps": resolver_gaps,
    }
