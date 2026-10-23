from __future__ import annotations

import os
import re
from pathlib import Path

from .classifier import classify_trace
from .models import Evidence, Trace
from .resolver import ResolutionIndex, ResolvedRoute, build_resolution_index, network_intents
from .scanner import (
    _balanced_brace_end,
    _jsx_open_end,
    iter_jsx_controls,
    iter_sources,
    jsx_expression_attribute,
    jsx_navigation_attribute,
    scan_repository,
)

FUNC_ARROW_HEADER = re.compile(
    r"(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?"
    r"(?:\([^)\n]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{",
)
FUNC_DECL_HEADER = re.compile(
    r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*"
    r"(?::[^{\n]+)?\{",
)
FUNC_ARROW_EXPRESSION = re.compile(
    r"(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?"
    r"(?:\([^)\n]*\)|[A-Za-z_$][\w$]*)\s*=>",
)
USE_CALLBACK_BINDING = re.compile(
    r"(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:React\.)?useCallback\s*\("
)
FUNCTION_CALL = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")
MUTATION_CALL = re.compile(r"\b([A-Za-z_$][\w$]*)\.(?:mutate|mutateAsync)\s*\(")
FUNCTION_DECLARATION = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")
COMPONENT_ARROW_DECLARATION = re.compile(
    r"\b(?:const|let)\s+([A-Z][\w$]*)\s*=\s*\(\s*\{"
)
STATE_PAIR = re.compile(
    r"\[\s*([A-Za-z_$][\w$]*)\s*,\s*([A-Za-z_$][\w$]*)\s*\]\s*=\s*"
    r"(?:React\.)?use(?:State|Reducer)(?:\s*<[^()\n]+>)?\s*\("
)
SEARCH_PARAMS_PAIR = re.compile(
    r"\[\s*([A-Za-z_$][\w$]*)\s*,\s*([A-Za-z_$][\w$]*)\s*\]\s*=\s*useSearchParams\s*\("
)
ROUTE_PATH = re.compile(r"<Route\b[^>]*\bpath\s*=\s*[\"']([^\"']+)[\"']", re.S)
PROGRAM_ROUTE_SET = re.compile(
    r"PROGRAM_ACTIVITY_ROUTE_PATHS\s*=\s*new Set\(\s*\[([^\]]*)\]\s*\)", re.S
)
QUOTED_ROUTE = re.compile(r"""["'](/[^"']*)["']""")


def _handler_bodies(source: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for match in FUNC_ARROW_HEADER.finditer(source):
        body_end = _balanced_brace_end(source, match.end() - 1)
        if body_end is not None:
            result[match.group(1)] = source[match.end() : body_end]
    for match in FUNC_DECL_HEADER.finditer(source):
        body_end = _balanced_brace_end(source, match.end() - 1)
        if body_end is not None:
            result[match.group(1)] = source[match.end() : body_end]
    return result


def _expression_end(source: str, start: int, *, stop_at_comma: bool = False) -> int:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char in {"(", "[", "{"}:
            stack.append(char)
        elif char in pairs and stack and stack[-1] == pairs[char]:
            stack.pop()
        elif (char in {";", "\n"} or stop_at_comma and char == ",") and not stack:
            return index
    return len(source)


def _single_string_call_argument(expression: str, call: re.Match[str]) -> str | None:
    start = call.end() - 1
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(start, len(expression)):
        char = expression[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                argument = expression[start + 1 : index].strip()
                return argument if re.fullmatch(r"""(['"])([^'"]*)\1""", argument) else None
    return None


def _specialize_string_parameter(
    source: str, name: str, argument: str | None, body: str
) -> str:
    if argument is None:
        return body
    signature = re.search(
        rf"(?:async\s+)?function\s+{re.escape(name)}\s*\(\s*"
        r"([A-Za-z_$][\w$]*)\s*(?:=[^)]*)?\)",
        source,
    )
    if signature is None:
        return body
    parameter = signature.group(1)
    result: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(body):
        char = body[index]
        if quote is not None:
            result.append(char)
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
            result.append(char)
            index += 1
            continue
        match = re.match(r"[A-Za-z_$][\w$]*", body[index:])
        if match is not None:
            token = match.group()
            replacement = token
            if token == parameter:
                previous = body[:index].rstrip()
                following = body[index + len(token) :].lstrip()
                if previous.endswith(("{", ",")) and following.startswith(("}", ",")):
                    replacement = f"{parameter}: {argument}"
                else:
                    replacement = argument
            result.append(replacement)
            index += len(token)
            continue
        result.append(char)
        index += 1
    return "".join(result)


def _mutation_callback_body(source: str, name: str, line: int) -> str | None:
    binding = re.compile(
        rf"(?:const|let)\s+{re.escape(name)}\s*=\s*useMutation\s*\(\s*\{{"
    )
    for match in binding.finditer(source):
        if source[: match.start()].count("\n") + 1 > line:
            continue
        object_start = match.end() - 1
        object_end = _balanced_brace_end(source, object_start)
        if object_end is None:
            continue
        options = source[object_start + 1 : object_end]
        callback = re.search(
            r"\bmutationFn\s*:\s*(?:async\s*)?(?:\([^)\n]*\)|[A-Za-z_$][\w$]*)\s*=>",
            options,
        )
        if callback is None:
            reference = re.search(
                r"\bmutationFn\s*:\s*([A-Za-z_$][\w$]*)\b", options
            )
            if reference is not None:
                return f"{reference.group(1)}()"
            continue
        body_start = callback.end()
        while body_start < len(options) and options[body_start].isspace():
            body_start += 1
        if body_start < len(options) and options[body_start] == "{":
            body_end = _balanced_brace_end(options, body_start)
            if body_end is not None:
                return options[body_start + 1 : body_end]
        else:
            body_end = _expression_end(options, body_start, stop_at_comma=True)
            return options[body_start:body_end].strip()
    return None


def _mutation_hook_body(
    repo_root: Path,
    source_rel: str,
    source: str,
    alias: str,
    line: int,
    index: ResolutionIndex,
) -> tuple[str, str, str, int] | None:
    hook_name = None
    binding = re.compile(
        r"(?:const|let)\s*\{([^}]*)\}\s*=\s*([A-Za-z_$][\w$]*)\s*\("
    )
    for match in binding.finditer(source):
        if source[: match.start()].count("\n") + 1 > line:
            continue
        properties, candidate_hook = match.groups()
        if re.search(
            rf"(?:^|,)\s*mutate(?:Async)?\s*:\s*{re.escape(alias)}\b",
            properties,
        ):
            hook_name = candidate_hook
            break
    if hook_name is None:
        return None

    target = index.resolve_symbol(source_rel, hook_name)
    if target is None:
        return None
    target_path = repo_root / target.source
    if not target_path.is_file():
        return None
    target_source = target_path.read_text(encoding="utf-8", errors="replace")
    hook_body = _handler_body_for_line(target_source, target.name, target.line)
    if hook_body is None:
        return None

    mutation = re.search(r"\buseMutation\s*\(\s*\{", hook_body)
    if mutation is None:
        return None
    options_start = mutation.end() - 1
    options_end = _balanced_brace_end(hook_body, options_start)
    if options_end is None:
        return None
    options = hook_body[options_start + 1 : options_end]
    callback = re.search(
        r"\bmutationFn\s*:\s*(?:async\s*)?(?:\([^)\n]*\)|[A-Za-z_$][\w$]*)\s*=>",
        options,
    )
    if callback is None:
        reference = re.search(r"\bmutationFn\s*:\s*([A-Za-z_$][\w$]*)\b", options)
        if reference is None:
            return None
        return target.source, target_source, f"{reference.group(1)}()", target.line
    body_start = callback.end()
    while body_start < len(options) and options[body_start].isspace():
        body_start += 1
    if body_start < len(options) and options[body_start] == "{":
        body_end = _balanced_brace_end(options, body_start)
        if body_end is not None:
            return (
                target.source,
                target_source,
                options[body_start + 1 : body_end],
                target.line,
            )
        return None
    body_end = _expression_end(options, body_start, stop_at_comma=True)
    return (
        target.source,
        target_source,
        options[body_start:body_end].strip(),
        target.line,
    )


def _query_refetch_hook_body(
    repo_root: Path,
    source_rel: str,
    source: str,
    alias: str,
    line: int,
    index: ResolutionIndex,
) -> tuple[str, str, str, int] | None:
    hook_name = None
    binding = re.compile(
        r"(?:const|let)\s*\{([^}]*)\}\s*=\s*([A-Za-z_$][\w$]*)\s*\("
    )
    for match in binding.finditer(source):
        if source[: match.start()].count("\n") + 1 > line:
            continue
        properties, candidate_hook = match.groups()
        if re.search(rf"(?:^|,)\s*refetch\s*:\s*{re.escape(alias)}\b", properties):
            hook_name = candidate_hook
            break
    if hook_name is None and re.search(
        r"\b[A-Za-z_$][\w$]*\s*\.\s*refetch\s*(?:\?\.)?\s*\(", source
    ):
        result_binding = re.compile(
            r"(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*"
            r"([A-Za-z_$][\w$]*)\s*\("
        )
        for match in result_binding.finditer(source):
            if source[: match.start()].count("\n") + 1 > line:
                continue
            result_name, candidate_hook = match.groups()
            if re.search(
                rf"\b{re.escape(result_name)}\s*\.\s*refetch\s*(?:\?\.)?\s*\(",
                source,
            ):
                hook_name = candidate_hook
                break
    if hook_name is None:
        return None

    target = index.resolve_symbol(source_rel, hook_name)
    if target is None:
        return None
    target_path = repo_root / target.source
    if not target_path.is_file():
        return None
    target_source = target_path.read_text(encoding="utf-8", errors="replace")
    hook_body = _handler_body_for_line(target_source, target.name, target.line)
    if hook_body is None:
        return None

    query = re.search(r"\buseQuery\s*\(\s*\{", hook_body)
    if query is None:
        return None
    options_start = query.end() - 1
    options_end = _balanced_brace_end(hook_body, options_start)
    if options_end is None:
        return None
    options = hook_body[options_start + 1 : options_end]
    query_fn = re.search(
        r"\bqueryFn\s*:\s*(?:async\s*)?(?:\([^)\n]*\)|[A-Za-z_$][\w$]*)\s*=>",
        options,
    )
    if query_fn is None:
        reference = re.search(r"\bqueryFn\s*:\s*([A-Za-z_$][\w$]*)\b", options)
        if reference is None:
            return None
        return target.source, target_source, f"{reference.group(1)}()", target.line
    body_start = query_fn.end()
    while body_start < len(options) and options[body_start].isspace():
        body_start += 1
    if body_start < len(options) and options[body_start] == "{":
        body_end = _balanced_brace_end(options, body_start)
        if body_end is None:
            return None
        query_body = options[body_start + 1 : body_end]
    else:
        body_end = _expression_end(options, body_start, stop_at_comma=True)
        query_body = options[body_start:body_end].strip()
    return target.source, target_source, query_body, target.line


def _handler_body_for_line(source: str, name: str, line: int) -> str | None:
    candidates: list[tuple[int, str]] = []
    for match in FUNC_ARROW_HEADER.finditer(source):
        if match.group(1) != name or source[: match.start()].count("\n") + 1 > line:
            continue
        body_end = _balanced_brace_end(source, match.end() - 1)
        if body_end is not None:
            candidates.append((match.start(), source[match.end() : body_end]))
    for match in FUNC_DECL_HEADER.finditer(source):
        if match.group(1) != name or source[: match.start()].count("\n") + 1 > line:
            continue
        body_end = _balanced_brace_end(source, match.end() - 1)
        if body_end is not None:
            candidates.append((match.start(), source[match.end() : body_end]))
    for match in FUNC_ARROW_EXPRESSION.finditer(source):
        if match.group(1) != name or source[: match.start()].count("\n") + 1 > line:
            continue
        expression_start = match.end()
        while expression_start < len(source) and source[expression_start].isspace():
            expression_start += 1
        if expression_start < len(source) and source[expression_start] == "{":
            continue
        expression_end = _expression_end(source, expression_start)
        candidates.append((match.start(), source[expression_start:expression_end]))
    for match in USE_CALLBACK_BINDING.finditer(source):
        if match.group(1) != name or source[: match.start()].count("\n") + 1 > line:
            continue
        arrow = source.find("=>", match.end())
        body_start = arrow + 2 if arrow >= 0 else -1
        while body_start >= 0 and source[body_start].isspace():
            body_start += 1
        if body_start < 0 or body_start >= len(source):
            continue
        if source[body_start] == "{":
            body_end = _balanced_brace_end(source, body_start)
            body = source[body_start + 1 : body_end] if body_end is not None else None
        else:
            body_end = _expression_end(source, body_start, stop_at_comma=True)
            body = source[body_start:body_end].strip()
        if body is not None:
            candidates.append((match.start(), body))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _expand_local_calls(
    repo_root: Path,
    source_rel: str,
    source: str,
    body: str,
    line: int,
    index: ResolutionIndex,
) -> str:
    resolved = [body]
    pending = [(source_rel, source, body, line)]
    visited: set[tuple[str, str, str]] = set()
    ignored = {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "setState",
        "console",
        "mutate",
        "mutateAsync",
    }
    for _ in range(4):
        next_pending: list[tuple[str, str, str, int]] = []
        for current_rel, current_source, expression, current_line in pending:
            for mutation in MUTATION_CALL.finditer(expression):
                name = mutation.group(1)
                key = (current_rel, name, "mutationFn")
                if key in visited:
                    continue
                visited.add(key)
                helper = _mutation_callback_body(current_source, name, current_line)
                if helper is not None:
                    resolved.append(helper)
                    next_pending.append((current_rel, current_source, helper, current_line))
            for call in FUNCTION_CALL.finditer(expression):
                name = call.group(1)
                argument = _single_string_call_argument(expression, call)
                key = (current_rel, name, argument or "")
                if name in ignored or key in visited:
                    continue
                visited.add(key)
                helper = _handler_body_for_line(current_source, name, current_line)
                if helper is not None:
                    helper = _specialize_string_parameter(
                        current_source, name, argument, helper
                    )
                    resolved.append(helper)
                    next_pending.append((current_rel, current_source, helper, current_line))
                    continue
                target = index.resolve_symbol(current_rel, name)
                if target is None:
                    hook_callback = _custom_hook_callback_body(
                        repo_root,
                        current_rel,
                        current_source,
                        name,
                        current_line,
                        index,
                    )
                    if hook_callback is not None:
                        hook_source_rel, hook_source, callback_body, hook_line = hook_callback
                        resolved.append(callback_body)
                        next_pending.append(
                            (
                                hook_source_rel,
                                hook_source,
                                callback_body,
                                hook_line,
                            )
                        )
                        continue
                    mutation_hook = _mutation_hook_body(
                        repo_root, current_rel, current_source, name, current_line, index
                    )
                    if mutation_hook is not None:
                        hook_source_rel, hook_source, mutation_body, hook_line = mutation_hook
                        resolved.append(mutation_body)
                        next_pending.append(
                            (hook_source_rel, hook_source, mutation_body, hook_line)
                        )
                        continue
                    query_hook = _query_refetch_hook_body(
                        repo_root, current_rel, current_source, name, current_line, index
                    )
                    if query_hook is not None:
                        hook_source_rel, hook_source, query_body, hook_line = query_hook
                        resolved.append(query_body)
                        next_pending.append(
                            (hook_source_rel, hook_source, query_body, hook_line)
                        )
                        continue
                    context_method = _context_method_body(
                        repo_root,
                        current_rel,
                        current_source,
                        name,
                        expression,
                        current_line,
                        index,
                    )
                    if context_method is not None:
                        method_source_rel, method_source, method_body, method_line = context_method
                        resolved.append(method_body)
                        next_pending.append(
                            (method_source_rel, method_source, method_body, method_line)
                        )
                    continue
                target_path = repo_root / target.source
                if not target_path.is_file():
                    continue
                target_source = target_path.read_text(encoding="utf-8", errors="replace")
                helper = _handler_body_for_line(target_source, target.name, target.line)
                if helper is not None:
                    helper = _specialize_string_parameter(
                        target_source, target.name, argument, helper
                    )
                    resolved.append(helper)
                    next_pending.append((target.source, target_source, helper, target.line))
        pending = next_pending
        if not pending:
            break
    return "\n".join(resolved)


def _component_props(source: str, component: str) -> str | None:
    opening = re.search(
        rf"\bfunction\s+{re.escape(component)}\s*\(\s*\{{",
        source,
    )
    if opening is None:
        opening = next(
            (
                match
                for match in COMPONENT_ARROW_DECLARATION.finditer(source)
                if match.group(1) == component
            ),
            None,
        )
    if opening is None:
        return None
    props_start = opening.end() - 1
    props_end = _balanced_brace_end(source, props_start)
    if props_end is None:
        return None
    return source[props_start + 1 : props_end]


def _object_property_reference(
    source: str, object_name: str, property_name: str
) -> str | None:
    declaration = re.search(
        rf"\b(?:const|let)\s+{re.escape(object_name)}\s*=\s*\{{", source
    )
    if declaration is None:
        return None
    object_start = declaration.end() - 1
    object_end = _balanced_brace_end(source, object_start)
    if object_end is None:
        return None
    body = source[object_start + 1 : object_end]
    member = re.search(
        rf"(?:^|,)\s*{re.escape(property_name)}\s*"
        rf"(?::\s*([A-Za-z_$][\w$]*))?\s*(?=,|$)",
        body,
        re.M,
    )
    if member is None:
        return None
    return member.group(1) or property_name


def _component_callsite_prop_value(
    attributes: str,
    prop_name: str,
    caller_rel: str,
    caller_source: str,
    caller_line: int,
    repo_root: Path,
    index: ResolutionIndex,
) -> tuple[str, str, str, int] | None:
    direct = jsx_expression_attribute(
        attributes, re.compile(rf"\b{re.escape(prop_name)}\s*=")
    )
    if direct is not None:
        return direct, caller_rel, caller_source, caller_line

    for spread in re.findall(r"\{\s*\.\.\.\s*([A-Za-z_$][\w$]*)\s*\}", attributes):
        value = _object_property_reference(caller_source, spread, prop_name)
        if value is not None:
            return value, caller_rel, caller_source, caller_line
        for binding in re.finditer(
            r"\b(?:const|let)\s*\{([^{}]*)\}\s*=\s*([A-Za-z_$][\w$]*)\s*\(",
            caller_source,
        ):
            if caller_source[: binding.start()].count("\n") + 1 > caller_line:
                continue
            properties = {
                alias or key
                for key, alias in re.findall(
                    r"(?:^|,)\s*([A-Za-z_$][\w$]*)"
                    r"(?:\s*:\s*([A-Za-z_$][\w$]*))?",
                    binding.group(1),
                )
            }
            if spread not in properties:
                continue
            hook_name = binding.group(2)
            target = index.resolve_symbol(caller_rel, hook_name)
            if target is None:
                continue
            hook_path = repo_root / target.source
            if not hook_path.is_file():
                continue
            hook_source = hook_path.read_text(encoding="utf-8", errors="replace")
            hook_body = _handler_body_for_line(
                hook_source, target.name, hook_source.count("\n") + 1
            )
            if hook_body is None or not re.search(
                rf"\breturn\s*\{{[^}}]*\b{re.escape(spread)}\b",
                hook_body,
                re.S,
            ):
                continue
            value = _object_property_reference(hook_source, spread, prop_name)
            if value is not None:
                return (
                    value,
                    target.source,
                    hook_source,
                    hook_source.count("\n") + 1,
                )
    return None


def _invokes_callback(source: str, name: str) -> bool:
    return re.search(
        rf"\b{re.escape(name)}\s*(?:\?\.)?\s*\(", source
    ) is not None


def _component_declaration_before_line(source: str, line: int) -> str | None:
    declarations = [
        (match.start(), match.group(1))
        for pattern in (FUNCTION_DECLARATION, COMPONENT_ARROW_DECLARATION)
        for match in pattern.finditer(source)
        if match.group(1)[0].isupper()
        and source[: match.start()].count("\n") + 1 <= line
    ]
    return max(declarations)[1] if declarations else None


def _custom_hook_state_target(
    source_rel: str,
    source: str,
    handler_body: str,
    repo_root: Path,
    index: ResolutionIndex,
) -> tuple[str, list[str]] | None:
    setter_names = set(re.findall(r"\bset[A-Z][\w$]*\b", handler_body))
    if not setter_names:
        return None

    hook_bindings = [
        (binding.group(1), binding.group(2))
        for binding in re.finditer(
            r"\b(?:const|let)\s*\{([^{}]*)\}\s*=\s*([A-Za-z_$][\w$]*)\s*\(",
            source,
        )
    ]
    hook_aliases = {
        alias.group(1): alias.group(2)
        for alias in re.finditer(
            r"\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\s*\(",
            source,
        )
    }
    for binding in re.finditer(
        r"\b(?:const|let)\s*\{([^{}]*)\}\s*=\s*([A-Za-z_$][\w$]*)\s*;",
        source,
    ):
        hook_name = hook_aliases.get(binding.group(2))
        if hook_name is not None:
            hook_bindings.append((binding.group(1), hook_name))

    resolved_states: set[str] = set()
    evidence: list[str] = []
    for props, hook_name in hook_bindings:
        returned_setters = setter_names.intersection(
            re.findall(r"[A-Za-z_$][\w$]*", props)
        )
        if not returned_setters:
            continue
        target = index.resolve_symbol(source_rel, hook_name)
        if target is None:
            continue
        hook_path = repo_root / target.source
        if not hook_path.is_file():
            continue
        hook_source = hook_path.read_text(encoding="utf-8", errors="replace")
        returned_set = {
            name
            for returned in re.finditer(
                r"\breturn\s*\{(?:(?!\}).)*\}", hook_source, re.DOTALL
            )
            for name in returned_setters
            if re.search(rf"\b{re.escape(name)}\b", returned.group(0))
        }
        for state, setter in STATE_PAIR.findall(hook_source):
            if setter not in returned_set:
                continue
            resolved_states.add(state)
            evidence.extend(
                [
                    f"custom-hook-binding:{source_rel}:{hook_name}.{setter}",
                    f"custom-hook-return:{target.source}:{setter}",
                    f"useState-binding:{state}:{setter}",
                ]
            )

    if not resolved_states:
        return None
    return ",".join(sorted(resolved_states)), evidence


def _custom_hook_callback_body(
    repo_root: Path,
    source_rel: str,
    source: str,
    name: str,
    line: int,
    index: ResolutionIndex,
    depth: int = 0,
) -> tuple[str, str, str, int] | None:
    if depth >= 4:
        return None
    hook_bindings = [
        (binding.group(1), binding.group(2))
        for binding in re.finditer(
            r"\b(?:const|let)\s*\{([^{}]*)\}\s*=\s*([A-Za-z_$][\w$]*)\s*\(",
            source,
        )
        if source[: binding.start()].count("\n") + 1 <= line
    ]
    hook_aliases = {
        alias.group(1): alias.group(2)
        for alias in re.finditer(
            r"\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\s*\(",
            source,
        )
        if source[: alias.start()].count("\n") + 1 <= line
    }
    for binding in re.finditer(
        r"\b(?:const|let)\s*\{([^{}]*)\}\s*=\s*([A-Za-z_$][\w$]*)\s*;",
        source,
    ):
        if source[: binding.start()].count("\n") + 1 > line:
            continue
        hook_name = hook_aliases.get(binding.group(2))
        if hook_name is not None:
            hook_bindings.append((binding.group(1), hook_name))

    for props, hook_name in hook_bindings:
        properties = {
            alias or key
            for key, alias in re.findall(
                r"(?:^|,)\s*([A-Za-z_$][\w$]*)(?:\s*:\s*([A-Za-z_$][\w$]*))?",
                props,
            )
        }
        if name not in properties:
            continue
        target = index.resolve_symbol(source_rel, hook_name)
        if target is None:
            continue
        hook_path = repo_root / target.source
        if not hook_path.is_file():
            continue
        hook_source = hook_path.read_text(encoding="utf-8", errors="replace")
        hook_body = _handler_body_for_line(
            hook_source, target.name, hook_source.count("\n") + 1
        )
        if hook_body is None:
            continue
        returned_objects = re.finditer(
            r"\breturn\s*\{(?:(?!\}).)*\}", hook_body, re.DOTALL
        )
        for returned in returned_objects:
            member = re.search(
                rf"(?:\{{|,)\s*{re.escape(name)}\s*(?::\s*([^,}}]+))?",
                returned.group(0),
            )
            if member is None:
                continue
            value = (member.group(1) or name).strip()
            mutation = re.fullmatch(
                r"([A-Za-z_$][\w$]*)\.mutateAsync", value
            )
            if mutation is not None:
                body = _mutation_callback_body(
                    hook_source,
                    mutation.group(1),
                    hook_source.count("\n") + 1,
                )
                if body is not None:
                    return (
                        target.source,
                        hook_source,
                        body,
                        hook_source.count("\n") + 1,
                    )
            callback_name = re.fullmatch(r"[A-Za-z_$][\w$]*", value)
            if callback_name is None:
                continue
            body = _handler_body_for_line(
                hook_source, callback_name.group(0), hook_source.count("\n") + 1
            )
            if body is not None:
                return (
                    target.source,
                    hook_source,
                    body,
                    hook_source.count("\n") + 1,
                )
            nested = _custom_hook_callback_body(
                repo_root,
                target.source,
                hook_source,
                callback_name.group(0),
                hook_source.count("\n") + 1,
                index,
                depth + 1,
            )
            if nested is not None:
                return nested
    return None


def _component_prop_state_target(
    source_rel: str,
    source: str,
    line: int,
    handler_body: str,
    repo_root: Path,
    index: ResolutionIndex,
    depth: int = 0,
) -> tuple[str, list[str]] | None:
    if depth >= 4:
        return None
    component = _component_declaration_before_line(source, line)
    if component is None:
        return None
    props = _component_props(source, component)
    if props is None:
        return None
    prop_names = [
        name
        for name in re.findall(r"[A-Za-z_$][\w$]*", props)
        if (name.startswith("on") or name.startswith("set"))
        and (
            re.fullmatch(re.escape(name), handler_body.strip())
            or _invokes_callback(handler_body, name)
        )
    ]
    if not prop_names:
        return None

    resolved_states: set[str] = set()
    evidence: list[str] = [
        f"component-prop:{component}.{name}" for name in prop_names
    ]
    usage_pattern = re.compile(rf"<{re.escape(component)}\b")
    for caller_path in iter_sources(repo_root):
        caller_rel = caller_path.relative_to(repo_root).as_posix()
        try:
            caller_source = caller_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if caller_rel != source_rel:
            target = index.resolve_symbol(caller_rel, component)
            binding = index.imports.get(caller_rel, {}).get(component)
            if not (
                (target is not None and target.source == source_rel)
                or (binding is not None and binding[0] == source_rel)
            ):
                continue
        for opening in usage_pattern.finditer(caller_source):
            end = _jsx_open_end(caller_source, opening.end())
            if end is None:
                continue
            attributes = caller_source[opening.end() : end]
            caller_line = caller_source[: opening.start()].count("\n") + 1
            for prop_name in prop_names:
                callsite_prop = _component_callsite_prop_value(
                    attributes,
                    prop_name,
                    caller_rel,
                    caller_source,
                    caller_line,
                    repo_root,
                    index,
                )
                if callsite_prop is None:
                    continue
                callback, callback_source_rel, callback_source, callback_line = (
                    callsite_prop
                )
                callback_body = callback
                callback_name = re.fullmatch(r"[A-Za-z_$][\w$]*", callback)
                if callback_name is not None:
                    name = callback_name.group(0)
                    local_body = _handler_body_for_line(
                        callback_source, name, callback_line
                    )
                    if local_body is not None:
                        callback_body = local_body
                    else:
                        target = index.resolve_symbol(callback_source_rel, name)
                        if target is not None:
                            target_path = repo_root / target.source
                            if target_path.is_file():
                                callback_source = target_path.read_text(
                                    encoding="utf-8", errors="replace"
                                )
                                callback_source_rel = target.source
                                callback_line = target.line
                                callback_body = (
                                    _handler_body_for_line(
                                        callback_source, target.name, target.line
                                    )
                                    or callback
                                )
                callback_body = _expand_local_calls(
                    repo_root,
                    callback_source_rel,
                    callback_source,
                    callback_body,
                    callback_line,
                    index,
                )
                for state, setter in STATE_PAIR.findall(callback_source):
                    passes_setter = callback == setter or re.search(
                        rf"\b{re.escape(setter)}\s*\(", callback_body
                    )
                    if not passes_setter or len(
                        re.findall(rf"\b{re.escape(setter)}\b", callback_source)
                    ) < 2:
                        continue
                    resolved_states.add(state)
                    evidence.extend(
                        [
                            f"component-callsite:{caller_rel}:{caller_line}:{prop_name}={callback}",
                            f"useState-binding:{state}:{setter}",
                        ]
                    )
                custom_hook_state = _custom_hook_state_target(
                    callback_source_rel,
                    callback_source,
                    callback_body,
                    repo_root,
                    index,
                )
                if custom_hook_state is not None:
                    state_names, hook_evidence = custom_hook_state
                    resolved_states.update(state_names.split(","))
                    evidence.extend(
                        [
                            f"component-callsite:{caller_rel}:{caller_line}:{prop_name}={callback}",
                            *hook_evidence,
                        ]
                    )
                if re.search(r"\bset[A-Z][\w$]*\s*\(", callback_body):
                    nested_state = _component_prop_state_target(
                        callback_source_rel,
                        callback_source,
                        callback_line,
                        callback_body,
                        repo_root,
                        index,
                        depth + 1,
                    )
                    nested_state = nested_state or _custom_hook_state_target(
                        callback_source_rel,
                        callback_source,
                        callback_body,
                        repo_root,
                        index,
                    )
                    if nested_state is not None:
                        state_names, nested_evidence = nested_state
                        resolved_states.update(state_names.split(","))
                        evidence.extend(
                            [
                                f"component-callsite:{caller_rel}:{caller_line}:{prop_name}",
                                *nested_evidence,
                            ]
                        )
    if not resolved_states:
        return None
    return ",".join(sorted(resolved_states)), evidence


def _component_prop_callback_body(
    source_rel: str,
    source: str,
    line: int,
    handler_body: str,
    repo_root: Path,
    index: ResolutionIndex,
    depth: int = 0,
) -> tuple[str, list[str]] | None:
    if depth >= 4:
        return None
    component = _component_declaration_before_line(source, line)
    if component is None:
        return None
    props = _component_props(source, component)
    if props is None:
        return None
    prop_names = [
        name
        for name in re.findall(r"[A-Za-z_$][\w$]*", props)
        if name.startswith("on")
        and (
            handler_body.strip() == name
            or _invokes_callback(handler_body, name)
        )
    ]
    if not prop_names:
        return None

    bodies: list[str] = []
    evidence: list[str] = []
    usage_pattern = re.compile(rf"<{re.escape(component)}\b")
    for caller_path in iter_sources(repo_root):
        caller_rel = caller_path.relative_to(repo_root).as_posix()
        try:
            caller_source = caller_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if caller_rel != source_rel:
            target = index.resolve_symbol(caller_rel, component)
            binding = index.imports.get(caller_rel, {}).get(component)
            if not (
                (target is not None and target.source == source_rel)
                or (binding is not None and binding[0] == source_rel)
            ):
                continue
        for opening in usage_pattern.finditer(caller_source):
            end = _jsx_open_end(caller_source, opening.end())
            if end is None:
                continue
            attributes = caller_source[opening.end() : end]
            caller_line = caller_source[: opening.start()].count("\n") + 1
            for prop_name in prop_names:
                callback = jsx_expression_attribute(
                    attributes, re.compile(rf"\b{re.escape(prop_name)}\s*=")
                )
                if callback is None:
                    continue
                if not re.fullmatch(r"[A-Za-z_$][\w$]*", callback):
                    continue
                callback_source = caller_source
                callback_rel = caller_rel
                callback_line = caller_line
                body = _handler_body_for_line(callback_source, callback, callback_line)
                if body is None:
                    nested_callback = _component_prop_callback_body(
                        caller_rel,
                        caller_source,
                        caller_line,
                        callback,
                        repo_root,
                        index,
                        depth + 1,
                    )
                    if nested_callback is not None:
                        bodies.append(nested_callback[0])
                        evidence.extend(nested_callback[1])
                        continue
                    target = index.resolve_symbol(caller_rel, callback)
                    if target is None:
                        continue
                    callback_path = repo_root / target.source
                    if not callback_path.is_file():
                        continue
                    callback_source = callback_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
                    callback_rel = target.source
                    callback_line = target.line
                    body = _handler_body_for_line(
                        callback_source, target.name, callback_line
                    )
                if body is None:
                    continue
                expanded = _expand_local_calls(
                    repo_root, callback_rel, callback_source, body, callback_line, index
                )
                if not network_intents(expanded):
                    nested_callback = _component_prop_callback_body(
                        caller_rel,
                        caller_source,
                        caller_line,
                        callback,
                        repo_root,
                        index,
                        depth + 1,
                    )
                    if nested_callback is not None:
                        bodies.append(nested_callback[0])
                        evidence.extend(nested_callback[1])
                    continue
                bodies.append(expanded)
                evidence.extend(
                    [
                        f"component-prop:{component}.{prop_name}",
                        f"component-callsite:{caller_rel}:{caller_line}:{prop_name}={callback}",
                    ]
                )
    if not bodies:
        return None
    return "\n".join(bodies), evidence


def _url_search_param_state(source: str, body: str) -> tuple[str, list[str]] | None:
    for params, setter in SEARCH_PARAMS_PAIR.findall(source):
        if (
            not re.search(rf"\b{re.escape(setter)}\s*\(", body)
            or not re.search(rf"\b{re.escape(params)}\s*\.\s*(?:get|has)\s*\(", source)
        ):
            continue
        keys = sorted(
            set(
                re.findall(
                    r"\.\s*(?:set|delete)\s*\(\s*['\"]([^'\"]+)['\"]",
                    body,
                )
            )
        )
        if not keys and re.search(r"\.\s*(?:set|delete)\s*\(", body):
            keys = sorted(
                set(
                    re.findall(
                        rf"\b{re.escape(params)}\s*\.\s*(?:get|has)\s*\(\s*['\"]([^'\"]+)['\"]",
                        source,
                    )
                )
            )
        if keys:
            return ",".join(keys), [
                f"useSearchParams-binding:{params}:{setter}",
                *(f"url-search-param-write:{key}" for key in keys),
            ]
    return None


def _component_prop_url_search_state_target(
    source_rel: str,
    source: str,
    line: int,
    handler_body: str,
    repo_root: Path,
    index: ResolutionIndex,
) -> tuple[str, list[str]] | None:
    component = _component_declaration_before_line(source, line)
    if component is None:
        return None
    props = _component_props(source, component)
    if props is None:
        return None
    prop_names = [
        name
        for name in re.findall(r"[A-Za-z_$][\w$]*", props)
        if name.startswith("on") and re.search(rf"\b{re.escape(name)}\b", handler_body)
    ]
    if not prop_names:
        return None

    usage_pattern = re.compile(rf"<{re.escape(component)}\b")
    for caller_path in iter_sources(repo_root):
        caller_rel = caller_path.relative_to(repo_root).as_posix()
        try:
            caller_source = caller_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if caller_rel != source_rel:
            target = index.resolve_symbol(caller_rel, component)
            binding = index.imports.get(caller_rel, {}).get(component)
            if not (
                (target is not None and target.source == source_rel)
                or (binding is not None and binding[0] == source_rel)
            ):
                continue
        for opening in usage_pattern.finditer(caller_source):
            end = _jsx_open_end(caller_source, opening.end())
            if end is None:
                continue
            attributes = caller_source[opening.end() : end]
            caller_line = caller_source[: opening.start()].count("\n") + 1
            for prop_name in prop_names:
                callback = jsx_expression_attribute(
                    attributes, re.compile(rf"\b{re.escape(prop_name)}\s*=")
                )
                if callback is None:
                    continue
                callback_body = callback
                if re.fullmatch(r"[A-Za-z_$][\w$]*", callback):
                    callback_body = _handler_body_for_line(
                        caller_source, callback, caller_line
                    ) or callback
                expanded = _expand_local_calls(
                    repo_root, caller_rel, caller_source, callback_body, caller_line, index
                )
                state = _url_search_param_state(caller_source, expanded)
                if state is not None:
                    keys, evidence = state
                    return keys, [
                        f"component-prop:{component}.{prop_name}",
                        f"component-callsite:{caller_rel}:{caller_line}:{prop_name}",
                        *evidence,
                    ]
    return None


def _context_state_target(
    source_rel: str,
    source: str,
    body: str,
    repo_root: Path,
    index: ResolutionIndex,
) -> tuple[str, list[str]] | None:
    for properties, hook_name in re.findall(
        r"(?:const|let)\s*\{([^}]*)\}\s*=\s*([A-Za-z_$][\w$]*)\s*\(",
        source,
    ):
        for property_text in properties.split(","):
            match = re.fullmatch(
                r"\s*([A-Za-z_$][\w$]*)(?:\s*:\s*([A-Za-z_$][\w$]*))?\s*",
                property_text,
            )
            if match is None:
                continue
            context_setter = match.group(2) or match.group(1)
            if not context_setter.startswith("set") or not re.search(
                rf"\b{re.escape(context_setter)}\s*\(", body
            ):
                continue
            target = index.resolve_symbol(source_rel, hook_name)
            if target is None:
                continue
            target_path = repo_root / target.source
            if not target_path.is_file():
                continue
            target_source = target_path.read_text(encoding="utf-8", errors="replace")
            hook_body = _handler_body_for_line(
                target_source, target.name, target.line
            )
            context = re.search(r"\buseContext\s*\(\s*([A-Za-z_$][\w$]*)\s*\)", hook_body or "")
            if context is None:
                continue
            context_name = context.group(1)
            provider = re.search(
                rf"<{re.escape(context_name)}\.Provider\b[^>]*\bvalue\s*=\s*\{{\s*\{{([^}}]*)\}}\s*\}}",
                target_source,
                re.S,
            )
            if provider is None or not re.search(
                rf"\b{re.escape(context_setter)}\b", provider.group(1)
            ):
                continue
            for state, setter in STATE_PAIR.findall(target_source):
                if setter != context_setter or not re.search(
                    rf"\b{re.escape(state)}\b", provider.group(1)
                ):
                    continue
                return state, [
                    f"context-hook-binding:{hook_name}:{state}:{setter}",
                    f"context-hook-useContext:{context_name}",
                    f"context-provider:{context_name}:{state}:{setter}",
                    f"useState-binding:{state}:{setter}",
                ]
    return None


def _query_cache_refetch_target(
    source: str, body: str
) -> tuple[str, list[str]] | None:
    for client in re.findall(
        r"(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*useQueryClient\s*\(",
        source,
    ):
        if re.search(
            rf"\b{re.escape(client)}\s*\.\s*refetchQueries\s*\(", body
        ):
            return "react-query-cache-refetch", [
                f"useQueryClient-binding:{client}",
                f"query-cache-refetch:{client}",
            ]
    return None


def _context_method_body(
    repo_root: Path,
    source_rel: str,
    source: str,
    method: str,
    body: str,
    line: int,
    index: ResolutionIndex,
) -> tuple[str, str, str, int] | None:
    bindings = re.compile(
        r"(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\s*\("
    )
    for match in bindings.finditer(source):
        if source[: match.start()].count("\n") + 1 > line:
            continue
        context_value, hook_name = match.groups()
        if not re.search(
            rf"\b{re.escape(context_value)}\s*\.\s*{re.escape(method)}\s*\(", body
        ):
            continue
        target = index.resolve_symbol(source_rel, hook_name)
        if target is None:
            continue
        target_path = repo_root / target.source
        if not target_path.is_file():
            continue
        target_source = target_path.read_text(encoding="utf-8", errors="replace")
        hook_body = _handler_body_for_line(target_source, target.name, target.line)
        context = re.search(
            r"\buseContext\s*\(\s*([A-Za-z_$][\w$]*)\s*\)", hook_body or ""
        )
        if context is None:
            continue
        provider = re.search(
            rf"<{re.escape(context.group(1))}\.Provider\b[^>]*\bvalue\s*=\s*\{{\s*\{{([^}}]*)\}}\s*\}}",
            target_source,
            re.S,
        )
        if provider is None or not re.search(
            rf"\b{re.escape(method)}\b", provider.group(1)
        ):
            continue
        provider_line = target_source[: provider.start()].count("\n") + 1
        method_body = _handler_body_for_line(target_source, method, provider_line)
        if method_body is not None:
            return target.source, target_source, method_body, provider_line
    return None


def _drawer_navigation_target(
    source_rel: str,
    source: str,
    body: str,
    repo_root: Path,
    index: ResolutionIndex,
) -> tuple[str, list[str]] | None:
    for properties, hook_name in re.findall(
        r"(?:const|let)\s*\{([^}]*)\}\s*=\s*([A-Za-z_$][\w$]*)\s*\(",
        source,
    ):
        for property_text in properties.split(","):
            navigation = re.fullmatch(
                r"\s*(open|go)(?:\s*:\s*([A-Za-z_$][\w$]*))?\s*",
                property_text,
            )
            if navigation is None:
                continue
            property_name = navigation.group(2) or navigation.group(1)
            call = re.search(
                rf"\b{re.escape(property_name)}\s*\.\s*([A-Za-z_$][\w$]*)\s*\(",
                body,
            )
            if call is None:
                continue
            kind = call.group(1)
            target = index.resolve_symbol(source_rel, hook_name)
            if target is None:
                continue
            target_path = repo_root / target.source
            if not target_path.is_file():
                continue
            target_source = target_path.read_text(encoding="utf-8", errors="replace")
            hook_body = _handler_body_for_line(target_source, target.name, target.line)
            context = re.search(
                r"\buseContext\s*\(\s*([A-Za-z_$][\w$]*)\s*\)", hook_body or ""
            )
            if context is None:
                continue
            drawer_map = re.search(
                rf"\b{re.escape(property_name)}\s*=\s*\{{([^}}]*)\}}",
                target_source,
                re.S,
            )
            if drawer_map is None or not re.search(
                rf"\b{re.escape(kind)}\s*:\s*\([^)]*\)\s*=>\s*"
                rf"(?:push|replace)\(\s*['\"]{re.escape(kind)}['\"]",
                drawer_map.group(1),
            ):
                continue
            if not re.search(
                rf"top\??\.\s*kind\s*===\s*['\"]{re.escape(kind)}['\"]",
                target_source,
            ):
                continue
            if not STATE_PAIR.search(target_source):
                continue
            return f"drawer:{kind}", [
                f"context-hook-binding:{hook_name}:{property_name}",
                f"context-hook-useContext:{context.group(1)}",
                f"drawer-navigation:{property_name}.{kind}",
                "drawer-provider-state:stack",
                f"drawer-render-branch:{kind}",
            ]
    return None


def _browser_clipboard_target(body: str) -> tuple[str, list[str]] | None:
    if re.search(r"\bnavigator\s*\.\s*clipboard\s*(?:\?\.|\.)\s*writeText\s*\(", body):
        return "clipboard", ["navigator-clipboard-writeText"]
    return None


def _browser_file_picker_target(
    source: str, body: str
) -> tuple[str, list[str]] | None:
    click = re.search(
        r"\b([A-Za-z_$][\w$]*)\s*\.\s*current\s*(?:\?\.)?\s*click\s*\(\s*\)",
        body,
    )
    if click is None:
        return None
    ref_name = click.group(1)
    for input_match in re.finditer(r"<input\b[^>]*>", source, re.DOTALL):
        input_tag = input_match.group(0)
        if not re.search(r"\btype\s*=\s*(['\"])file\1", input_tag):
            continue
        if not re.search(
            rf"\bref\s*=\s*\{{\s*{re.escape(ref_name)}\s*\}}", input_tag
        ):
            continue
        return "file-picker", [
            f"file-input-ref:{ref_name}",
            f"file-input-source-line:{source[:input_match.start()].count(chr(10)) + 1}",
        ]
    return None


def _browser_external_link_target(
    tag: str,
    attributes: str,
    navigation: tuple[str, bool] | None,
) -> tuple[str, list[str]] | None:
    if tag.lower() != "a" or navigation is None or not navigation[1]:
        return None
    if not re.fullmatch(
        r"[A-Za-z_$][\w$]*\.(?:source_url|html_url|url|href)",
        navigation[0],
    ):
        return None
    target = re.search(r"\btarget\s*=\s*(['\"])(.*?)\1", attributes)
    relation = re.search(r"\brel\s*=\s*(['\"])(.*?)\1", attributes)
    if target is None or target.group(2) != "_blank" or relation is None:
        return None
    rel_tokens = set(relation.group(2).split())
    if not rel_tokens.intersection({"noopener", "noreferrer"}):
        return None
    return "external-navigation", [
        f"dynamic-url-field:{navigation[0].rsplit('.', 1)[1]}",
        "anchor-target:_blank",
        "anchor-rel:noopener-or-noreferrer",
    ]


def _only_stops_event_propagation(body: str) -> bool:
    return re.fullmatch(
        r"(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{?\s*"
        r"[A-Za-z_$][\w$]*\.stopPropagation\(\)\s*;?\s*\}?",
        body.strip(),
    ) is not None


def _browser_download_route_target(
    source_rel: str,
    attributes: str,
    navigation: tuple[str, bool] | None,
    repo_root: Path,
    index: ResolutionIndex,
) -> tuple[str, list[str]] | None:
    if (
        navigation is None
        or not navigation[1]
        or not re.search(r"\bdownload(?:\s*=|\s|$)", attributes)
    ):
        return None
    method_call = re.fullmatch(
        r"([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\.htmlUrl\([^)]*\)",
        navigation[0],
    )
    if method_call is None:
        return None
    client_alias, service_name = method_call.groups()
    binding = index.imports.get(source_rel, {}).get(client_alias)
    if binding is None:
        return None
    client_path = repo_root / binding[0]
    if not client_path.is_file():
        return None
    client_source = client_path.read_text(encoding="utf-8", errors="replace")
    service = re.search(
        rf"\b(?:const|let)\s+{re.escape(service_name)}\s*=\s*\{{",
        client_source,
    )
    if service is None:
        return None
    service_start = service.end() - 1
    service_end = _balanced_brace_end(client_source, service_start)
    if service_end is None:
        return None
    service_body = client_source[service_start + 1 : service_end]
    method = re.search(
        r"\bhtmlUrl\s*:\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{",
        service_body,
    )
    if method is None:
        return None
    method_start = method.end() - 1
    method_end = _balanced_brace_end(service_body, method_start)
    if method_end is None:
        return None
    method_body = service_body[method_start + 1 : method_end]
    template = re.search(r"\breturn\s*`([^`]*)`", method_body)
    base_path = re.search(
        r"\bconst\s+base\s*=\s*trimSlash\([^;\n]*\|\|\s*(['\"])(/[^'\"]*)\1",
        method_body,
    )
    if (
        template is None
        or base_path is None
        or "${base}" not in template.group(1)
    ):
        return None
    candidate_path = template.group(1).replace("${base}", base_path.group(2))
    candidate_path = re.sub(r"\$\{[^}]+\}", "{}", candidate_path)
    candidate_shape = re.sub(r"\{[^{}]*\}", "{}", candidate_path)
    route = next(
        (
            route
            for route in index.routes
            if route.method == "GET"
            and re.sub(r"\{[^{}]*\}", "{}", route.path) == candidate_shape
        ),
        None,
    )
    if route is None:
        return None
    return f"{route.method} {route.path}", [
        f"browser-download-attribute:{source_rel}",
        f"client-url-builder:{binding[0]}:{service_name}.htmlUrl",
        f"backend-route:{route.source}:{route.line}",
    ]


def _control_at_line(source: str, line: int) -> tuple[str, str, str] | None:
    for control in iter_jsx_controls(source):
        match_line = source[: control.start].count("\n") + 1
        if match_line != line:
            continue
        return control.tag, control.attributes, control.body
    return None


def _route_for_intent(
    index: ResolutionIndex, method: str, target_path: str
) -> ResolvedRoute | None:
    exact = index.route(method, target_path)
    if exact is not None:
        return exact
    requested = target_path.strip("/").split("/")
    candidates = [
        route
        for route in index.routes
        if route.method == method.upper()
        and len(route.path.strip("/").split("/")) == len(requested)
        and all(
            actual == expected
            or actual.startswith("{") and actual.endswith("}")
            or expected.startswith("{") and expected.endswith("}")
            for actual, expected in zip(
                route.path.strip("/").split("/"), requested, strict=True
            )
        )
    ]
    return candidates[0] if len(candidates) == 1 else None


def _submit_handler_at_line(source: str, line: int, attributes: str) -> str | None:
    if not re.search(r"\btype\s*=\s*['\"]submit['\"]", attributes, re.I):
        return None
    control_start = next(
        (
            control.start
            for control in iter_jsx_controls(source)
            if source[: control.start].count("\n") + 1 == line
            and control.attributes == attributes
        ),
        None,
    )
    if control_start is None:
        return None
    form_open = next(
        reversed(list(re.finditer(r"<form\b", source[:control_start], re.I))),
        None,
    )
    if form_open is None:
        return None
    last_form_close = source.rfind("</form", 0, control_start)
    if last_form_close > form_open.start():
        return None
    form_end = _jsx_open_end(source, form_open.end())
    if form_end is None:
        return None
    form_attributes = source[form_open.end() : form_end]
    return jsx_expression_attribute(form_attributes, re.compile(r"\bonSubmit\s*=", re.I))


def _client_storage_target(
    source_rel: str,
    body: str,
    repo_root: Path,
    index: ResolutionIndex,
) -> tuple[str, str] | None:
    setter = re.search(r"\bsetWriteToken\s*\(", body)
    if setter is None:
        return None
    target = index.resolve_symbol(source_rel, "setWriteToken")
    if target is None:
        return None
    target_path = repo_root / target.source
    if not target_path.is_file():
        return None
    target_source = target_path.read_text(encoding="utf-8", errors="replace")
    key = re.search(
        r"""WRITE_TOKEN_STORAGE_KEY\s*=\s*['"]([^'"]+)['"]""",
        target_source,
    )
    if (
        key is None
        or not re.search(r"localStorage\.setItem\(WRITE_TOKEN_STORAGE_KEY", target_source)
        or not re.search(r"localStorage\.removeItem\(WRITE_TOKEN_STORAGE_KEY", target_source)
        or not re.search(r"appParams\.writeToken\s*=", target_source)
    ):
        return None
    storage_key = key.group(1)
    evidence = (
        f"local-handler-call:setWriteToken:{source_rel}",
        f"resolved-storage-helper:{target.source}:{target.line}",
        f"storage-key:{storage_key}",
    )
    receipt = index.receipt(
        "gui-to-client-storage",
        f"{source_rel}:{target.line}",
        storage_key,
        evidence,
    )
    digest = receipt.get("digest")
    if not isinstance(digest, str):
        return None
    return storage_key, digest


def _frontend_routes(repo_root: Path) -> set[str]:
    routes: set[str] = set()
    ignored = {".git", "node_modules", "dist", "build", ".venv", "venv", "tests"}
    suffixes = {".js", ".jsx", ".ts", ".tsx", ".vue"}
    for current, directories, files in os.walk(repo_root):
        directories[:] = sorted(directory for directory in directories if directory not in ignored)
        for filename in files:
            path = Path(current) / filename
            if path.suffix.lower() in suffixes:
                source = path.read_text(encoding="utf-8", errors="replace")
                routes.update(ROUTE_PATH.findall(source))
    return routes


def _validated_program_activity_routes(
    source_rel: str,
    source: str,
    repo_root: Path,
    index: ResolutionIndex,
    frontend_routes: set[str],
) -> set[str]:
    if not re.search(r"\bmergeProgramActivity\s*\(", source):
        return set()
    target = index.resolve_symbol(source_rel, "mergeProgramActivity")
    if target is None:
        return set()
    helper_path = repo_root / target.source
    if not helper_path.is_file():
        return set()
    helper = helper_path.read_text(encoding="utf-8", errors="replace")
    route_set = PROGRAM_ROUTE_SET.search(helper)
    valid_route = re.search(
        r"validRoute\s*=\s*\(value\)\s*=>\s*!value\s*\|\|\s*PROGRAM_ACTIVITY_ROUTE_PATHS\.has\(value\)",
        helper,
    )
    if (
        route_set is None
        or valid_route is None
        or "canonicalRoute: validRoute(item.href)" not in helper
        or "validRoute(event?.canonicalRoute)" not in helper
        or not re.search(r"validateProgramActivityEvent\(event\)", helper)
    ):
        return set()
    allowed = set(QUOTED_ROUTE.findall(route_set.group(1)))
    return allowed if allowed and allowed.issubset(frontend_routes) else set()


def _strictify(trace: Trace) -> Trace:
    for key in (
        "static_contract_resolved",
        "target_resolution_evidence",
        "resolved_target",
        "resolved_target_source",
        "t2_receipt",
        "runtime_isolated",
    ):
        trace.observations.pop(key, None)
    return classify_trace(trace)


def _promote_gui_trace(
    trace: Trace, repo_root: Path, index: ResolutionIndex, frontend_routes: set[str]
) -> Trace:
    source_rel = trace.surface.get("source")
    line = trace.surface.get("line")
    if not isinstance(source_rel, str) or not isinstance(line, int):
        return trace
    source_path = repo_root / source_rel
    if not source_path.is_file():
        return trace
    source = source_path.read_text(encoding="utf-8", errors="replace")
    control = _control_at_line(source, line)
    if control is None:
        return trace
    tag, attributes, _ = control
    event_expr = jsx_expression_attribute(
        attributes, re.compile(r"\bon[A-Z][A-Za-z0-9_$]*\s*=")
    )

    if event_expr is not None and _only_stops_event_propagation(event_expr):
        external_target = _browser_external_link_target(
            tag, attributes, jsx_navigation_attribute(attributes)
        )
        if external_target is not None:
            target_name, target_evidence = external_target
            receipt = index.receipt(
                "gui-browser-action",
                f"{source_rel}:{line}",
                f"browser:{target_name}",
                [f"surface:{source_rel}:{line}", *target_evidence],
            )
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": f"browser:{target_name}",
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt["digest"],
                }
            )
            trace.evidence.append(
                Evidence("T1", "resolver-receipt", str(receipt["digest"]))
            )
            return classify_trace(trace)

    if event_expr is None:
        event_expr = _submit_handler_at_line(source, line, attributes)

    if event_expr is None:
        navigation = jsx_navigation_attribute(attributes)
        if tag.lower() not in {"a", "link"} or navigation is None:
            return trace
        download_route = _browser_download_route_target(
            source_rel, attributes, navigation, repo_root, index
        )
        if download_route is not None:
            target_name, target_evidence = download_route
            receipt = index.receipt(
                "gui-browser-download",
                f"{source_rel}:{line}",
                target_name,
                [f"surface:{source_rel}:{line}", *target_evidence],
            )
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": f"browser:download:{target_name}",
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt["digest"],
                }
            )
            trace.evidence.append(
                Evidence("T1", "resolver-receipt", str(receipt["digest"]))
            )
            return classify_trace(trace)
        external_target = _browser_external_link_target(tag, attributes, navigation)
        if external_target is not None:
            target_name, target_evidence = external_target
            receipt = index.receipt(
                "gui-browser-action",
                f"{source_rel}:{line}",
                f"browser:{target_name}",
                [f"surface:{source_rel}:{line}", *target_evidence],
            )
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": f"browser:{target_name}",
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt["digest"],
                }
            )
            trace.evidence.append(
                Evidence("T1", "resolver-receipt", str(receipt["digest"]))
            )
            return classify_trace(trace)
        target_path, dynamic = navigation
        if not dynamic:
            if target_path not in frontend_routes:
                trace.observations["target_missing"] = True
                return classify_trace(trace)
            resolved_target = target_path
            navigation_evidence = [f"frontend-route:{target_path}"]
        else:
            valid_routes = _validated_program_activity_routes(
                source_rel, source, repo_root, index, frontend_routes
            )
            if (
                not re.fullmatch(r"[A-Za-z_$][\w$]*\.href", target_path)
                or not valid_routes
            ):
                return trace
            resolved_target = "PROGRAM_ACTIVITY_ROUTE_PATHS"
            navigation_evidence = [
                f"dynamic-navigation:{target_path}",
                f"validated-route-set:{','.join(sorted(valid_routes))}",
            ]
        receipt = index.receipt(
            "gui-navigation",
            f"{source_rel}:{line}",
            resolved_target,
            [f"surface:{source_rel}:{line}", *navigation_evidence],
        )
        for stale in ("target_missing", "contract_mismatch"):
            trace.observations.pop(stale, None)
        trace.observations.update(
            {
                "handler_bound": True,
                "handler_resolved": True,
                "intent_observed": True,
                "boundary_reached": True,
                "contract_matched": True,
                "target_resolution_evidence": True,
                "resolved_target": resolved_target,
                "resolved_target_source": source_rel,
                "resolver_receipt_digest": receipt["digest"],
            }
        )
        trace.evidence.append(Evidence("T1", "resolver-receipt", str(receipt["digest"])))
        return classify_trace(trace)

    handler_match = re.fullmatch(r"([A-Za-z_$][\w$]*)", event_expr)
    handler_name = handler_match.group(1) if handler_match else None
    handler_source = source_rel
    handler_body_source = source
    handler_body_line = line
    body: str | None = None
    evidence: list[str] = [f"surface:{source_rel}:{line}"]

    if handler_name:
        local_body = _handler_body_for_line(source, handler_name, line)
        if local_body is not None:
            body = local_body
            evidence.append(f"local-handler:{handler_name}")
        else:
            target = index.resolve_symbol(source_rel, handler_name)
            if target:
                target_source_path = repo_root / target.source
                target_source = target_source_path.read_text(encoding="utf-8", errors="replace")
                body = _handler_body_for_line(target_source, target.name, target.line)
                handler_source = target.source
                handler_body_source = target_source
                handler_body_line = target.line
                evidence.extend(
                    [
                        f"import-binding:{source_rel}:{handler_name}",
                        f"target-symbol:{target.source}:{target.line}:{target.name}",
                    ]
                )
    else:
        body = event_expr
        evidence.append("inline-event-expression")

    body = body or event_expr
    body = _expand_local_calls(
        repo_root, handler_source, handler_body_source, body, handler_body_line, index
    )
    intents = network_intents(body)
    if not intents:
        component_callback = _component_prop_callback_body(
            source_rel, source, line, body, repo_root, index
        )
        if component_callback:
            callback_body, callback_evidence = component_callback
            callback_intents = network_intents(callback_body)
            if callback_intents:
                body = callback_body
                intents = callback_intents
                evidence.extend(callback_evidence)
    if not intents:
        storage_target = _client_storage_target(source_rel, body, repo_root, index)
        if storage_target:
            storage_key, receipt_digest = storage_target
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": f"client-storage:{storage_key}",
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt_digest,
                }
            )
            trace.evidence.append(Evidence("T1", "resolver-receipt", receipt_digest))
            return classify_trace(trace)

        query_cache_target = _query_cache_refetch_target(source, body)
        if query_cache_target is not None:
            state_name, state_evidence = query_cache_target
            receipt = index.receipt(
                "gui-to-query-cache-refetch",
                f"{source_rel}:{line}",
                f"client-state:{state_name}",
                [f"surface:{source_rel}:{line}", *state_evidence],
            )
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": f"client-state:{state_name}",
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt["digest"],
                }
            )
            trace.evidence.append(
                Evidence("T1", "resolver-receipt", str(receipt["digest"]))
            )
            return classify_trace(trace)

        clipboard_target = _browser_clipboard_target(body)
        if clipboard_target is not None:
            target_name, target_evidence = clipboard_target
            receipt = index.receipt(
                "gui-to-browser-clipboard",
                f"{source_rel}:{line}",
                f"browser:{target_name}",
                [f"surface:{source_rel}:{line}", *target_evidence],
            )
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": f"browser:{target_name}",
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt["digest"],
                }
            )
            trace.evidence.append(
                Evidence("T1", "resolver-receipt", str(receipt["digest"]))
            )
            return classify_trace(trace)

        file_picker_target = _browser_file_picker_target(source, body)
        if file_picker_target is not None:
            target_name, target_evidence = file_picker_target
            receipt = index.receipt(
                "gui-browser-action",
                f"{source_rel}:{line}",
                f"browser:{target_name}",
                [f"surface:{source_rel}:{line}", *target_evidence],
            )
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": f"browser:{target_name}",
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt["digest"],
                }
            )
            trace.evidence.append(
                Evidence("T1", "resolver-receipt", str(receipt["digest"]))
            )
            return classify_trace(trace)

        state_target = _component_prop_state_target(
            source_rel, source, line, body, repo_root, index
        ) or _context_state_target(
            source_rel, source, body, repo_root, index
        ) or _custom_hook_state_target(
            source_rel, source, body, repo_root, index
        )
        if state_target:
            component_state_names, state_evidence = state_target
            receipt = index.receipt(
                "gui-to-component-state",
                f"{source_rel}:{line}",
                f"client-state:{component_state_names}",
                [f"surface:{source_rel}:{line}", *state_evidence],
            )
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": f"client-state:{component_state_names}",
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt["digest"],
                }
            )
            trace.evidence.append(
                Evidence("T1", "resolver-receipt", str(receipt["digest"]))
            )
            return classify_trace(trace)

        drawer_target = _drawer_navigation_target(
            source_rel, source, body, repo_root, index
        )
        if drawer_target is not None:
            target_name, target_evidence = drawer_target
            receipt = index.receipt(
                "gui-to-drawer-navigation",
                f"{source_rel}:{line}",
                f"client-state:{target_name}",
                [f"surface:{source_rel}:{line}", *target_evidence],
            )
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": f"client-state:{target_name}",
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt["digest"],
                }
            )
            trace.evidence.append(
                Evidence("T1", "resolver-receipt", str(receipt["digest"]))
            )
            return classify_trace(trace)

        component_search_state = _component_prop_url_search_state_target(
            source_rel, source, line, body, repo_root, index
        )
        if component_search_state is not None:
            query_param_names, state_evidence = component_search_state
            receipt = index.receipt(
                "gui-to-url-search-params",
                f"{source_rel}:{line}",
                f"client-state:url-search-params:{query_param_names}",
                [f"surface:{source_rel}:{line}", *state_evidence],
            )
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": f"client-state:url-search-params:{query_param_names}",
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt["digest"],
                }
            )
            trace.evidence.append(
                Evidence("T1", "resolver-receipt", str(receipt["digest"]))
            )
            return classify_trace(trace)

        search_param_state = _url_search_param_state(source, body)
        if search_param_state is not None:
            query_param_names, state_evidence = search_param_state
            receipt = index.receipt(
                "gui-to-url-search-params",
                f"{source_rel}:{line}",
                f"client-state:url-search-params:{query_param_names}",
                [f"surface:{source_rel}:{line}", *state_evidence],
            )
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": f"client-state:url-search-params:{query_param_names}",
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt["digest"],
                }
            )
            trace.evidence.append(
                Evidence("T1", "resolver-receipt", str(receipt["digest"]))
            )
            return classify_trace(trace)

        location_navigation = re.search(
            r"(?:window\.)?location\.(?:href\s*=\s*|(?:assign|replace)\s*\(\s*)"
            r"""(['"])(/[^'"?#]*)\1""",
            body,
        )
        navigate_call = re.search(
            r"\b([A-Za-z_$][\w$]*)\s*\(\s*(['\"])(/[^'\"?#]*)\2\s*\)",
            body,
        )
        navigate_hook = re.search(
            r"import\s*\{[^}]*\buseNavigate\b[^}]*\}\s*from\s*['\"]react-router-dom['\"]",
            source,
        )
        navigate_binding = re.search(
            r"\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*useNavigate\s*\(\s*\)",
            source,
        )
        browser_reload = re.search(r"(?:window\.)?location\.reload\s*\(\s*\)", body)
        browser_download = (
            re.search(r"\bURL\.createObjectURL\s*\(", body)
            and re.search(r"\.download\s*=", body)
            and re.search(r"\.click\s*\(", body)
        )
        if location_navigation or (
            navigate_call
            and navigate_hook
            and navigate_binding
            and navigate_call.group(1) == navigate_binding.group(1)
        ) or browser_reload or browser_download:
            if browser_download and not location_navigation and not navigate_call and not browser_reload:
                receipt = index.receipt(
                    "gui-browser-action",
                    f"{source_rel}:{line}",
                    "browser:download",
                    [f"surface:{source_rel}:{line}", "blob-object-url-download-click"],
                )
                download_receipt_digest = receipt.get("digest")
                if not isinstance(download_receipt_digest, str):
                    return trace
                trace.observations.update(
                    {
                        "handler_bound": True,
                        "handler_resolved": True,
                        "intent_observed": True,
                        "boundary_reached": True,
                        "contract_matched": True,
                        "target_resolution_evidence": True,
                        "resolved_target": "browser:download",
                        "resolved_target_source": source_rel,
                        "resolver_receipt_digest": download_receipt_digest,
                    }
                )
                trace.evidence.append(
                    Evidence("T1", "resolver-receipt", download_receipt_digest)
                )
                return classify_trace(trace)
            if browser_reload and not location_navigation and not navigate_call:
                receipt = index.receipt(
                    "gui-browser-action",
                    f"{source_rel}:{line}",
                    "browser:reload",
                    [f"surface:{source_rel}:{line}", "literal-location-reload"],
                )
                trace.observations.update(
                    {
                        "handler_bound": True,
                        "handler_resolved": True,
                        "intent_observed": True,
                        "boundary_reached": True,
                        "contract_matched": True,
                        "target_resolution_evidence": True,
                        "resolved_target": "browser:reload",
                        "resolved_target_source": source_rel,
                        "resolver_receipt_digest": receipt["digest"],
                    }
                )
                trace.evidence.append(Evidence("T1", "resolver-receipt", str(receipt["digest"])))
                return classify_trace(trace)

            navigation_target = (
                location_navigation.group(2)
                if location_navigation is not None
                else navigate_call.group(3) if navigate_call is not None else None
            )
            if navigation_target is None:
                return trace
            if navigation_target not in frontend_routes:
                trace.observations["target_missing"] = True
                return classify_trace(trace)
            receipt = index.receipt(
                "gui-navigation",
                f"{source_rel}:{line}",
                navigation_target,
                [
                    f"surface:{source_rel}:{line}",
                    f"internal-route:{navigation_target}",
                    "location-literal" if location_navigation else "react-router-useNavigate",
                ],
            )
            for stale in ("target_missing", "contract_mismatch"):
                trace.observations.pop(stale, None)
            trace.observations.update(
                {
                    "handler_bound": True,
                    "handler_resolved": True,
                    "intent_observed": True,
                    "boundary_reached": True,
                    "contract_matched": True,
                    "target_resolution_evidence": True,
                    "resolved_target": navigation_target,
                    "resolved_target_source": source_rel,
                    "resolver_receipt_digest": receipt["digest"],
                }
            )
            trace.evidence.append(Evidence("T1", "resolver-receipt", str(receipt["digest"])))
            return classify_trace(trace)

        class_state = re.search(
            r"\bthis\.setState\s*\(\s*\{\s*([A-Za-z_$][\w$]*)\s*:",
            body,
        )
        if class_state:
            state = class_state.group(1)
            state_read = re.search(
                rf"\bthis\.state\s*\.\s*{re.escape(state)}\b"
                rf"|\b(?:const|let)\s*\{{[^}}]*\b{re.escape(state)}\b[^}}]*\}}"
                r"\s*=\s*this\.state\b",
                source,
            )
            if state_read:
                receipt = index.receipt(
                    "gui-to-local-state",
                    f"{source_rel}:{line}",
                    f"client-state:{state}",
                    [f"surface:{source_rel}:{line}", f"class-state-setter:this.setState({state})"],
                )
                trace.observations.update(
                    {
                        "handler_bound": True,
                        "handler_resolved": True,
                        "intent_observed": True,
                        "boundary_reached": True,
                        "contract_matched": True,
                        "target_resolution_evidence": True,
                        "resolved_target": f"client-state:{state}",
                        "resolved_target_source": source_rel,
                        "resolver_receipt_digest": receipt["digest"],
                    }
                )
                trace.evidence.append(Evidence("T1", "resolver-receipt", str(receipt["digest"])))
                return classify_trace(trace)
        state_pairs = {
            setter: state
            for state, setter in STATE_PAIR.findall(source)
            if (
                re.search(rf"\b{re.escape(setter)}\s*\(", body)
                or re.fullmatch(re.escape(setter), body.strip())
            )
            and len(re.findall(rf"\b{re.escape(state)}\b", source)) > 1
        }
        if not state_pairs:
            return trace
        state_names = sorted(state_pairs.values())
        resolved_state = (
            state_names[0]
            if len(state_names) == 1
            else ",".join(state_names)
        )
        receipt = index.receipt(
            "gui-to-local-state",
            f"{source_rel}:{line}",
            f"client-state:{resolved_state}",
            [
                f"surface:{source_rel}:{line}",
                *(f"state-setter:{setter}" for setter in sorted(state_pairs)),
                "useState-binding",
            ],
        )
        trace.observations.update(
            {
                "handler_bound": True,
                "handler_resolved": True,
                "intent_observed": True,
                "boundary_reached": True,
                "contract_matched": True,
                "target_resolution_evidence": True,
                "resolved_target": f"client-state:{resolved_state}",
                "resolved_target_source": source_rel,
                "resolver_receipt_digest": receipt["digest"],
            }
        )
        trace.evidence.append(Evidence("T1", "resolver-receipt", str(receipt["digest"])))
        return classify_trace(trace)
    if not intents:
        return trace
    resolved_routes = []
    for method, target_path in intents:
        route = _route_for_intent(index, method, target_path)
        if route is None:
            same_path = [
                item
                for item in index.routes
                if item.path == target_path and item.method != method
            ]
            if same_path:
                trace.observations.pop("target_missing", None)
                trace.observations["handler_resolved"] = True
                trace.observations["contract_mismatch"] = True
                return classify_trace(trace)
            return trace
        resolved_routes.append(route)
    if not resolved_routes:
        return trace
    resolved_target = (
        f"{resolved_routes[0].method} {resolved_routes[0].path}"
        if len(resolved_routes) == 1
        else "multi-route:"
        + "|".join(
            f"{route.method} {route.path}" for route in resolved_routes
        )
    )
    receipt = index.receipt(
        "gui-to-api",
        f"{source_rel}:{line}",
        resolved_target,
        [
            *evidence,
            f"handler-source:{handler_source}",
            *(item for route in resolved_routes for item in route.evidence),
            *(f"route:{route.source}:{route.line}" for route in resolved_routes),
        ],
    )
    for stale in (
        "target_missing",
        "contract_mismatch",
        "blocked_precondition",
        "undeclared_precondition",
    ):
        trace.observations.pop(stale, None)
    trace.observations.update(
        {
            "handler_bound": True,
            "handler_resolved": True,
            "intent_observed": True,
            "boundary_reached": True,
            "contract_matched": True,
            "target_resolution_evidence": True,
            "resolved_target": resolved_target,
            "resolved_target_source": "|".join(
                f"{route.source}:{route.line}" for route in resolved_routes
            ),
            "resolver_receipt_digest": receipt["digest"],
        }
    )
    trace.evidence.append(Evidence("T1", "resolver-receipt", str(receipt["digest"])))
    return classify_trace(trace)


def strict_scan_repository(repo_root: Path, repo: dict) -> tuple[list[Trace], ResolutionIndex]:
    index = build_resolution_index(repo_root)
    frontend_routes = _frontend_routes(repo_root)
    traces = [_strictify(trace) for trace in scan_repository(repo_root, repo)]
    promoted: list[Trace] = []
    for trace in traces:
        if trace.surface.get("kind") == "gui-control":
            trace = _promote_gui_trace(trace, repo_root, index, frontend_routes)
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
            "surfaces_classified": sum(
                item["classification"] != "INDETERMINATE" for item in encoded
            ),
            "t1_or_t2_supported": sum(
                any(e["tier"] in {"T1", "T2"} for e in item["evidence"])
                for item in encoded
            ),
            "target_resolved": sum(
                bool(item["observations"].get("target_resolution_evidence"))
                for item in encoded
            ),
            "by_kind": {
                kind: sum(item["surface"]["kind"] == kind for item in encoded)
                for kind in kinds
            },
            "classification_counts": {
                status: sum(item["classification"] == status for item in encoded)
                for status in statuses
            },
            "repositories_present": len(manifest["repositories"]) - len(missing),
            "repositories_missing": len(missing),
        },
        "workspace_gaps": missing,
        "resolver_gaps": resolver_gaps,
    }
